"""
Main application entry point for Gmail Lead Sync & Response Engine.

This module provides the command-line interface for the Gmail Lead Sync system,
including commands for:
- Starting the watcher service
- Testing parser patterns
- Managing lead sources
- Managing email templates

Usage:
    python -m gmail_lead_sync <command> [options]

Commands:
    start               Start the email watcher service
    test-parser         Test regex patterns against sample emails
    add-source          Add a new lead source configuration
    list-sources        List all lead source configurations
    update-source       Update an existing lead source
    delete-source       Delete a lead source
    add-template        Add a new email template
    list-templates      List all email templates
    update-template     Update an existing email template
    delete-template     Delete an email template
"""

import argparse
import sys
import signal
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from gmail_lead_sync.models import Base, LeadSource
from gmail_lead_sync.credentials import CredentialsStore, EnvironmentCredentialsStore, EncryptedDBCredentialsStore
from gmail_lead_sync.watcher import GmailWatcher
from gmail_lead_sync.logging_config import setup_logging
from gmail_lead_sync.cli.config_manager import (
    add_source, list_sources, update_source, delete_source,
    add_template, list_templates, update_template, delete_template
)
from gmail_lead_sync.cli.parser_tester import main as parser_tester_main


# Global variables for graceful shutdown
watcher = None
shutdown_requested = False
logger = None


def signal_handler(signum: int, frame) -> None:
    """
    Handle SIGINT and SIGTERM signals for graceful shutdown.
    
    Args:
        signum: Signal number
        frame: Current stack frame
    """
    global shutdown_requested, watcher, logger
    
    if logger:
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    else:
        print(f"Received signal {signum}, initiating graceful shutdown...")
    
    shutdown_requested = True
    
    # Disconnect watcher if running
    if watcher:
        try:
            watcher.disconnect()
            if logger:
                logger.info("Watcher disconnected successfully")
        except Exception as e:
            if logger:
                logger.error(f"Error disconnecting watcher: {e}")


def get_db_session(db_path: str = 'gmail_lead_sync.db') -> Session:
    """
    Create and return a database session.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        SQLAlchemy Session object
    """
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def get_credentials_store(db_session: Session, use_env: bool = False) -> CredentialsStore:
    """
    Create and return a credentials store.
    
    Args:
        db_session: Database session for encrypted store
        use_env: If True, use environment variables; otherwise use encrypted DB
        
    Returns:
        CredentialsStore instance
    """
    if use_env:
        return EnvironmentCredentialsStore()
    else:
        return EncryptedDBCredentialsStore(db_session)


def start_watcher(args: argparse.Namespace) -> None:
    """
    Start the email watcher service.
    
    Monitors Gmail inbox for new emails from configured lead sources,
    extracts lead information, and sends automated responses.
    
    Args:
        args: Parsed command-line arguments containing:
            - db_path: Path to database file
            - agent_id: Agent identifier for credentials
            - use_env: Whether to use environment variables for credentials
            - log_file: Path to log file
            - log_level: Logging level
    """
    global watcher, shutdown_requested, logger
    
    # Set up logging
    logger = setup_logging(
        log_file=args.log_file,
        log_level=args.log_level
    )
    
    logger.info("=" * 80)
    logger.info("Gmail Lead Sync & Response Engine - Starting")
    logger.info("=" * 80)
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Main loop with restart logic
    while not shutdown_requested:
        try:
            # Initialize database session
            logger.info(f"Initializing database: {args.db_path}")
            db_session = get_db_session(args.db_path)
            
            # Initialize credentials store
            logger.info(f"Initializing credentials store (use_env={args.use_env})")
            credentials_store = get_credentials_store(db_session, args.use_env)
            
            # Get list of configured lead sources
            lead_sources = db_session.query(LeadSource).all()
            if not lead_sources:
                logger.warning("No lead sources configured. Add lead sources using 'add-source' command.")
                logger.info("Waiting 60 seconds before checking again...")
                time.sleep(60)
                continue
            
            sender_list = [source.sender_email for source in lead_sources]
            logger.info(f"Monitoring {len(sender_list)} lead source(s): {', '.join(sender_list)}")
            
            # Initialize watcher
            logger.info(f"Initializing watcher for agent: {args.agent_id}")
            watcher = GmailWatcher(credentials_store, db_session, args.agent_id)
            
            # Connect to Gmail
            logger.info("Connecting to Gmail IMAP server...")
            if not watcher.connect():
                logger.error("Failed to connect to Gmail. Retrying in 60 seconds...")
                time.sleep(60)
                continue
            
            logger.info("Successfully connected to Gmail")
            
            # Start monitoring loop
            logger.info("Starting email monitoring loop...")
            while not shutdown_requested:
                try:
                    # Check connection status
                    if not watcher.is_connected():
                        logger.warning("Connection lost, attempting to reconnect...")
                        if not watcher.connection.reconnect():
                            logger.error("Reconnection failed. Restarting in 60 seconds...")
                            break
                    
                    # Process unseen emails
                    logger.debug("Checking for unseen emails...")
                    watcher.process_unseen_emails(sender_list)
                    
                    # Wait before next check (avoid excessive polling)
                    logger.debug(f"Waiting {args.poll_interval} seconds before next check...")
                    time.sleep(args.poll_interval)
                    
                except KeyboardInterrupt:
                    # Handle Ctrl+C gracefully
                    logger.info("Keyboard interrupt received")
                    shutdown_requested = True
                    break
                    
                except Exception as e:
                    # Log error but continue monitoring
                    logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                    logger.info("Continuing monitoring after error...")
                    time.sleep(10)
            
            # Clean up
            if watcher:
                watcher.disconnect()
                logger.info("Watcher disconnected")
            
            if db_session:
                db_session.close()
                logger.info("Database session closed")
            
            # Exit if shutdown requested
            if shutdown_requested:
                logger.info("Shutdown complete")
                break
                
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received in main loop")
            shutdown_requested = True
            break
            
        except Exception as e:
            # Top-level exception handler with restart logic
            logger.critical(f"Unhandled exception in main loop: {e}", exc_info=True)
            logger.info("Restarting in 60 seconds...")
            
            # Clean up before restart
            if watcher:
                try:
                    watcher.disconnect()
                except Exception:
                    pass
            
            if not shutdown_requested:
                time.sleep(60)
    
    logger.info("Gmail Lead Sync Engine stopped")


def test_parser(args: argparse.Namespace) -> None:
    """
    Test regex patterns against sample email content.
    
    Delegates to the parser_tester CLI module.
    
    Args:
        args: Parsed command-line arguments
    """
    # The parser_tester module has its own main() function that handles
    # argument parsing. We need to modify sys.argv to pass the arguments.
    original_argv = sys.argv
    try:
        # Build new argv for parser_tester
        sys.argv = ['parser_tester', '--email-file', args.email_file]
        if args.name_regex:
            sys.argv.extend(['--name-regex', args.name_regex])
        if args.phone_regex:
            sys.argv.extend(['--phone-regex', args.phone_regex])
        
        # Call parser_tester main
        parser_tester_main()
    finally:
        # Restore original argv
        sys.argv = original_argv


def main() -> None:
    """
    Main entry point for the application.
    
    Parses command-line arguments and dispatches to appropriate command handler.
    """
    parser = argparse.ArgumentParser(
        description='Gmail Lead Sync & Response Engine',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start the watcher service
  python -m gmail_lead_sync start
  
  # Start with custom database and agent ID
  python -m gmail_lead_sync start --db-path /path/to/db.sqlite --agent-id my_agent
  
  # Test parser patterns
  python -m gmail_lead_sync test-parser --email-file sample.txt --name-regex "Name:\\s*(.+)"
  
  # Add a lead source
  python -m gmail_lead_sync add-source --sender leads@example.com \\
      --identifier "New Lead" --name-regex "Name:\\s*(.+)" --phone-regex "Phone:\\s*([\\d\\-]+)"
  
  # List all lead sources
  python -m gmail_lead_sync list-sources
        """
    )
    
    # Global options
    parser.add_argument(
        '--db-path',
        default='gmail_lead_sync.db',
        help='Path to SQLite database file (default: gmail_lead_sync.db)'
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Start command
    start_parser = subparsers.add_parser('start', help='Start the email watcher service')
    start_parser.add_argument(
        '--agent-id',
        default='default',
        help='Agent identifier for credentials (default: default)'
    )
    start_parser.add_argument(
        '--use-env',
        action='store_true',
        help='Use environment variables for credentials instead of encrypted database'
    )
    start_parser.add_argument(
        '--log-file',
        default='gmail_lead_sync.log',
        help='Path to log file (default: gmail_lead_sync.log)'
    )
    start_parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Logging level (default: INFO)'
    )
    start_parser.add_argument(
        '--poll-interval',
        type=int,
        default=60,
        help='Seconds to wait between email checks (default: 60)'
    )
    start_parser.set_defaults(func=start_watcher)
    
    # Test parser command
    test_parser_parser = subparsers.add_parser('test-parser', help='Test regex patterns')
    test_parser_parser.add_argument(
        '--email-file',
        required=True,
        help='Path to file containing email body text'
    )
    test_parser_parser.add_argument(
        '--name-regex',
        help='Regex pattern for extracting lead name'
    )
    test_parser_parser.add_argument(
        '--phone-regex',
        help='Regex pattern for extracting phone number'
    )
    test_parser_parser.set_defaults(func=test_parser)
    
    # Add source command
    add_source_parser = subparsers.add_parser('add-source', help='Add a new lead source')
    add_source_parser.add_argument('--sender', required=True, help='Sender email address')
    add_source_parser.add_argument('--identifier', required=True, help='Identifier snippet')
    add_source_parser.add_argument('--name-regex', required=True, help='Name regex pattern')
    add_source_parser.add_argument('--phone-regex', required=True, help='Phone regex pattern')
    add_source_parser.add_argument('--template-id', type=int, help='Template ID for auto-responses')
    add_source_parser.set_defaults(func=add_source)
    
    # List sources command
    list_sources_parser = subparsers.add_parser('list-sources', help='List all lead sources')
    list_sources_parser.set_defaults(func=list_sources)
    
    # Update source command
    update_source_parser = subparsers.add_parser('update-source', help='Update a lead source')
    update_source_parser.add_argument('--id', type=int, required=True, help='Lead source ID')
    update_source_parser.add_argument('--sender', help='New sender email')
    update_source_parser.add_argument('--identifier', help='New identifier snippet')
    update_source_parser.add_argument('--name-regex', help='New name regex pattern')
    update_source_parser.add_argument('--phone-regex', help='New phone regex pattern')
    update_source_parser.add_argument('--template-id', type=int, help='New template ID')
    update_source_parser.add_argument(
        '--auto-respond',
        type=lambda x: x.lower() == 'true',
        help='Enable/disable auto-respond (true/false)'
    )
    update_source_parser.set_defaults(func=update_source)
    
    # Delete source command
    delete_source_parser = subparsers.add_parser('delete-source', help='Delete a lead source')
    delete_source_parser.add_argument('--id', type=int, required=True, help='Lead source ID')
    delete_source_parser.set_defaults(func=delete_source)
    
    # Add template command
    add_template_parser = subparsers.add_parser('add-template', help='Add a new email template')
    add_template_parser.add_argument('--name', required=True, help='Template name')
    add_template_parser.add_argument('--subject', required=True, help='Email subject')
    add_template_parser.add_argument('--body-file', required=True, help='Path to template body file')
    add_template_parser.set_defaults(func=add_template)
    
    # List templates command
    list_templates_parser = subparsers.add_parser('list-templates', help='List all templates')
    list_templates_parser.set_defaults(func=list_templates)
    
    # Update template command
    update_template_parser = subparsers.add_parser('update-template', help='Update a template')
    update_template_parser.add_argument('--id', type=int, required=True, help='Template ID')
    update_template_parser.add_argument('--name', help='New template name')
    update_template_parser.add_argument('--subject', help='New email subject')
    update_template_parser.add_argument('--body-file', help='Path to new template body file')
    update_template_parser.set_defaults(func=update_template)
    
    # Delete template command
    delete_template_parser = subparsers.add_parser('delete-template', help='Delete a template')
    delete_template_parser.add_argument('--id', type=int, required=True, help='Template ID')
    delete_template_parser.set_defaults(func=delete_template)
    
    # Parse arguments
    args = parser.parse_args()
    
    # Show help if no command specified
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute the command
    args.func(args)


if __name__ == '__main__':
    main()

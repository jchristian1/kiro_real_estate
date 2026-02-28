"""
Configuration Manager CLI for Gmail Lead Sync Engine.

This module provides command-line interface commands for managing Lead_Source
and Template records in the database. It includes validation for regex patterns
and email formats before saving to ensure data integrity.
"""

import argparse
import sys
import re
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pydantic import ValidationError

from gmail_lead_sync.models import Base, LeadSource, Template
from gmail_lead_sync.validation import LeadSourceConfig, TemplateConfig
from gmail_lead_sync.error_handling import validate_regex_safety


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


def validate_email_format(email: str) -> bool:
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid, False otherwise
    """
    # Basic email regex pattern
    # Pattern breakdown:
    # - ^[a-zA-Z0-9._%+-]+ : Username part (alphanumeric and special chars)
    # - @ : Required @ symbol
    # - [a-zA-Z0-9.-]+ : Domain name (alphanumeric, dots, hyphens)
    # - \.[a-zA-Z]{2,}$ : Top-level domain (at least 2 letters)
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_pattern, email) is not None


def validate_regex_syntax(pattern: str) -> tuple[bool, Optional[str]]:
    """
    Validate regex pattern syntax and safety.
    
    Uses validate_regex_safety to check for:
    - Valid syntax
    - Catastrophic backtracking patterns
    - Execution time within limits
    
    Args:
        pattern: Regex pattern to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    return validate_regex_safety(pattern)


def add_source(args: argparse.Namespace) -> None:
    """
    Add a new Lead_Source record to the database.
    
    Args:
        args: Parsed command-line arguments containing:
            - sender: Sender email address
            - identifier: Identifier snippet to verify email relevance
            - name_regex: Regex pattern for extracting lead name
            - phone_regex: Regex pattern for extracting phone number
            - template_id: Optional template ID for auto-responses
            - db_path: Path to database file
    """
    # Validate email format
    if not validate_email_format(args.sender):
        print(f"Error: Invalid email format: {args.sender}", file=sys.stderr)
        sys.exit(1)
    
    # Validate name regex
    is_valid, error_msg = validate_regex_syntax(args.name_regex)
    if not is_valid:
        print(f"Error: Invalid name regex pattern: {error_msg}", file=sys.stderr)
        sys.exit(1)
    
    # Validate phone regex
    is_valid, error_msg = validate_regex_syntax(args.phone_regex)
    if not is_valid:
        print(f"Error: Invalid phone regex pattern: {error_msg}", file=sys.stderr)
        sys.exit(1)
    
    # Validate using Pydantic model
    try:
        config = LeadSourceConfig(
            sender_email=args.sender,
            identifier_snippet=args.identifier,
            name_regex=args.name_regex,
            phone_regex=args.phone_regex,
            template_id=args.template_id,
            auto_respond_enabled=False
        )
    except ValidationError as e:
        print(f"Error: Validation failed: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Create database record
    session = get_db_session(args.db_path)
    try:
        # Check if sender already exists
        existing = session.query(LeadSource).filter(
            LeadSource.sender_email == args.sender
        ).first()
        
        if existing:
            print(f"Error: Lead source with sender '{args.sender}' already exists (ID: {existing.id})", 
                  file=sys.stderr)
            sys.exit(1)
        
        lead_source = LeadSource(
            sender_email=config.sender_email,
            identifier_snippet=config.identifier_snippet,
            name_regex=config.name_regex,
            phone_regex=config.phone_regex,
            template_id=config.template_id,
            auto_respond_enabled=config.auto_respond_enabled
        )
        
        session.add(lead_source)
        session.commit()
        
        print(f"Successfully added lead source (ID: {lead_source.id})")
        print(f"  Sender: {lead_source.sender_email}")
        print(f"  Identifier: {lead_source.identifier_snippet}")
        print(f"  Name Regex: {lead_source.name_regex}")
        print(f"  Phone Regex: {lead_source.phone_regex}")
        if lead_source.template_id:
            print(f"  Template ID: {lead_source.template_id}")
        
    except Exception as e:
        session.rollback()
        print(f"Error: Failed to add lead source: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        session.close()


def list_sources(args: argparse.Namespace) -> None:
    """
    List all Lead_Source records in the database.
    
    Args:
        args: Parsed command-line arguments containing:
            - db_path: Path to database file
    """
    session = get_db_session(args.db_path)
    try:
        sources = session.query(LeadSource).order_by(LeadSource.id).all()
        
        if not sources:
            print("No lead sources found.")
            return
        
        print(f"\nFound {len(sources)} lead source(s):\n")
        print("=" * 80)
        
        for source in sources:
            print(f"ID: {source.id}")
            print(f"  Sender Email: {source.sender_email}")
            print(f"  Identifier Snippet: {source.identifier_snippet}")
            print(f"  Name Regex: {source.name_regex}")
            print(f"  Phone Regex: {source.phone_regex}")
            print(f"  Template ID: {source.template_id if source.template_id else 'None'}")
            print(f"  Auto-Respond: {'Enabled' if source.auto_respond_enabled else 'Disabled'}")
            print(f"  Created: {source.created_at}")
            print(f"  Updated: {source.updated_at}")
            print("-" * 80)
        
    except Exception as e:
        print(f"Error: Failed to list lead sources: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        session.close()


def update_source(args: argparse.Namespace) -> None:
    """
    Update an existing Lead_Source record.
    
    Args:
        args: Parsed command-line arguments containing:
            - id: Lead source ID to update
            - sender: Optional new sender email
            - identifier: Optional new identifier snippet
            - name_regex: Optional new name regex pattern
            - phone_regex: Optional new phone regex pattern
            - template_id: Optional new template ID
            - auto_respond: Optional auto-respond flag
            - db_path: Path to database file
    """
    session = get_db_session(args.db_path)
    try:
        # Find the lead source
        source = session.query(LeadSource).filter(LeadSource.id == args.id).first()
        
        if not source:
            print(f"Error: Lead source with ID {args.id} not found", file=sys.stderr)
            sys.exit(1)
        
        # Track if any updates were made
        updated = False
        
        # Update sender email if provided
        if args.sender:
            if not validate_email_format(args.sender):
                print(f"Error: Invalid email format: {args.sender}", file=sys.stderr)
                sys.exit(1)
            
            # Check if new sender already exists
            existing = session.query(LeadSource).filter(
                LeadSource.sender_email == args.sender,
                LeadSource.id != args.id
            ).first()
            
            if existing:
                print(f"Error: Lead source with sender '{args.sender}' already exists (ID: {existing.id})", 
                      file=sys.stderr)
                sys.exit(1)
            
            source.sender_email = args.sender
            updated = True
        
        # Update identifier snippet if provided
        if args.identifier:
            source.identifier_snippet = args.identifier
            updated = True
        
        # Update name regex if provided
        if args.name_regex:
            is_valid, error_msg = validate_regex_syntax(args.name_regex)
            if not is_valid:
                print(f"Error: Invalid name regex pattern: {error_msg}", file=sys.stderr)
                sys.exit(1)
            source.name_regex = args.name_regex
            updated = True
        
        # Update phone regex if provided
        if args.phone_regex:
            is_valid, error_msg = validate_regex_syntax(args.phone_regex)
            if not is_valid:
                print(f"Error: Invalid phone regex pattern: {error_msg}", file=sys.stderr)
                sys.exit(1)
            source.phone_regex = args.phone_regex
            updated = True
        
        # Update template ID if provided
        if args.template_id is not None:
            source.template_id = args.template_id if args.template_id > 0 else None
            updated = True
        
        # Update auto-respond flag if provided
        if args.auto_respond is not None:
            source.auto_respond_enabled = args.auto_respond
            updated = True
        
        if not updated:
            print("Warning: No fields specified for update", file=sys.stderr)
            return
        
        session.commit()
        
        print(f"Successfully updated lead source (ID: {source.id})")
        print(f"  Sender: {source.sender_email}")
        print(f"  Identifier: {source.identifier_snippet}")
        print(f"  Name Regex: {source.name_regex}")
        print(f"  Phone Regex: {source.phone_regex}")
        print(f"  Template ID: {source.template_id if source.template_id else 'None'}")
        print(f"  Auto-Respond: {'Enabled' if source.auto_respond_enabled else 'Disabled'}")
        
    except Exception as e:
        session.rollback()
        print(f"Error: Failed to update lead source: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        session.close()


def delete_source(args: argparse.Namespace) -> None:
    """
    Delete a Lead_Source record from the database.
    
    Args:
        args: Parsed command-line arguments containing:
            - id: Lead source ID to delete
            - db_path: Path to database file
    """
    session = get_db_session(args.db_path)
    try:
        # Find the lead source
        source = session.query(LeadSource).filter(LeadSource.id == args.id).first()
        
        if not source:
            print(f"Error: Lead source with ID {args.id} not found", file=sys.stderr)
            sys.exit(1)
        
        sender_email = source.sender_email
        
        # Delete the source
        session.delete(source)
        session.commit()
        
        print(f"Successfully deleted lead source (ID: {args.id}, Sender: {sender_email})")
        
    except Exception as e:
        session.rollback()
        print(f"Error: Failed to delete lead source: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        session.close()


def add_template(args: argparse.Namespace) -> None:
    """
    Add a new Template record to the database.
    
    Args:
        args: Parsed command-line arguments containing:
            - name: Template name/identifier
            - subject: Email subject line
            - body_file: Path to file containing template body
            - db_path: Path to database file
    """
    # Read body from file
    try:
        with open(args.body_file, 'r', encoding='utf-8') as f:
            body = f.read()
    except FileNotFoundError:
        print(f"Error: Body file not found: {args.body_file}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: Failed to read body file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Validate using Pydantic model
    try:
        config = TemplateConfig(
            name=args.name,
            subject=args.subject,
            body=body
        )
    except ValidationError as e:
        print(f"Error: Validation failed: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Create database record
    session = get_db_session(args.db_path)
    try:
        template = Template(
            name=config.name,
            subject=config.subject,
            body=config.body
        )
        
        session.add(template)
        session.commit()
        
        print(f"Successfully added template (ID: {template.id})")
        print(f"  Name: {template.name}")
        print(f"  Subject: {template.subject}")
        print(f"  Body length: {len(template.body)} characters")
        
    except Exception as e:
        session.rollback()
        print(f"Error: Failed to add template: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        session.close()


def list_templates(args: argparse.Namespace) -> None:
    """
    List all Template records in the database.
    
    Args:
        args: Parsed command-line arguments containing:
            - db_path: Path to database file
    """
    session = get_db_session(args.db_path)
    try:
        templates = session.query(Template).order_by(Template.id).all()
        
        if not templates:
            print("No templates found.")
            return
        
        print(f"\nFound {len(templates)} template(s):\n")
        print("=" * 80)
        
        for template in templates:
            print(f"ID: {template.id}")
            print(f"  Name: {template.name}")
            print(f"  Subject: {template.subject}")
            print(f"  Body Preview: {template.body[:100]}{'...' if len(template.body) > 100 else ''}")
            print(f"  Body Length: {len(template.body)} characters")
            print(f"  Created: {template.created_at}")
            print(f"  Updated: {template.updated_at}")
            print("-" * 80)
        
    except Exception as e:
        print(f"Error: Failed to list templates: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        session.close()


def update_template(args: argparse.Namespace) -> None:
    """
    Update an existing Template record.
    
    Args:
        args: Parsed command-line arguments containing:
            - id: Template ID to update
            - name: Optional new template name
            - subject: Optional new subject line
            - body_file: Optional path to file containing new template body
            - db_path: Path to database file
    """
    session = get_db_session(args.db_path)
    try:
        # Find the template
        template = session.query(Template).filter(Template.id == args.id).first()
        
        if not template:
            print(f"Error: Template with ID {args.id} not found", file=sys.stderr)
            sys.exit(1)
        
        # Track if any updates were made
        updated = False
        
        # Update name if provided
        if args.name:
            template.name = args.name
            updated = True
        
        # Update subject if provided
        if args.subject:
            template.subject = args.subject
            updated = True
        
        # Update body if body file provided
        if args.body_file:
            try:
                with open(args.body_file, 'r', encoding='utf-8') as f:
                    body = f.read()
            except FileNotFoundError:
                print(f"Error: Body file not found: {args.body_file}", file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                print(f"Error: Failed to read body file: {e}", file=sys.stderr)
                sys.exit(1)
            
            template.body = body
            updated = True
        
        if not updated:
            print("Warning: No fields specified for update", file=sys.stderr)
            return
        
        # Validate the updated template
        try:
            config = TemplateConfig(
                name=template.name,
                subject=template.subject,
                body=template.body
            )
        except ValidationError as e:
            print(f"Error: Validation failed: {e}", file=sys.stderr)
            sys.exit(1)
        
        session.commit()
        
        print(f"Successfully updated template (ID: {template.id})")
        print(f"  Name: {template.name}")
        print(f"  Subject: {template.subject}")
        print(f"  Body length: {len(template.body)} characters")
        
    except Exception as e:
        session.rollback()
        print(f"Error: Failed to update template: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        session.close()


def delete_template(args: argparse.Namespace) -> None:
    """
    Delete a Template record from the database.
    
    Args:
        args: Parsed command-line arguments containing:
            - id: Template ID to delete
            - db_path: Path to database file
    """
    session = get_db_session(args.db_path)
    try:
        # Find the template
        template = session.query(Template).filter(Template.id == args.id).first()
        
        if not template:
            print(f"Error: Template with ID {args.id} not found", file=sys.stderr)
            sys.exit(1)
        
        template_name = template.name
        
        # Check if any lead sources reference this template
        lead_sources = session.query(LeadSource).filter(
            LeadSource.template_id == args.id
        ).all()
        
        if lead_sources:
            print(f"Warning: {len(lead_sources)} lead source(s) reference this template:")
            for source in lead_sources:
                print(f"  - ID {source.id}: {source.sender_email}")
            print("These lead sources will have their template_id set to NULL.")
        
        # Delete the template
        session.delete(template)
        session.commit()
        
        print(f"Successfully deleted template (ID: {args.id}, Name: {template_name})")
        
    except Exception as e:
        session.rollback()
        print(f"Error: Failed to delete template: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        session.close()


def main() -> None:
    """
    Main entry point for the configuration manager CLI.
    """
    parser = argparse.ArgumentParser(
        description='Gmail Lead Sync Engine - Configuration Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--db-path',
        default='gmail_lead_sync.db',
        help='Path to SQLite database file (default: gmail_lead_sync.db)'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Add source command
    add_parser = subparsers.add_parser('add-source', help='Add a new lead source')
    add_parser.add_argument('--sender', required=True, help='Sender email address')
    add_parser.add_argument('--identifier', required=True, help='Identifier snippet to verify email')
    add_parser.add_argument('--name-regex', required=True, help='Regex pattern for extracting name')
    add_parser.add_argument('--phone-regex', required=True, help='Regex pattern for extracting phone')
    add_parser.add_argument('--template-id', type=int, help='Optional template ID for auto-responses')
    add_parser.set_defaults(func=add_source)
    
    # List sources command
    list_parser = subparsers.add_parser('list-sources', help='List all lead sources')
    list_parser.set_defaults(func=list_sources)
    
    # Update source command
    update_parser = subparsers.add_parser('update-source', help='Update an existing lead source')
    update_parser.add_argument('--id', type=int, required=True, help='Lead source ID to update')
    update_parser.add_argument('--sender', help='New sender email address')
    update_parser.add_argument('--identifier', help='New identifier snippet')
    update_parser.add_argument('--name-regex', help='New name regex pattern')
    update_parser.add_argument('--phone-regex', help='New phone regex pattern')
    update_parser.add_argument('--template-id', type=int, help='New template ID (0 to clear)')
    update_parser.add_argument('--auto-respond', type=lambda x: x.lower() == 'true', 
                              help='Enable/disable auto-respond (true/false)')
    update_parser.set_defaults(func=update_source)
    
    # Delete source command
    delete_parser = subparsers.add_parser('delete-source', help='Delete a lead source')
    delete_parser.add_argument('--id', type=int, required=True, help='Lead source ID to delete')
    delete_parser.set_defaults(func=delete_source)
    
    # Add template command
    add_template_parser = subparsers.add_parser('add-template', help='Add a new email template')
    add_template_parser.add_argument('--name', required=True, help='Template name/identifier')
    add_template_parser.add_argument('--subject', required=True, help='Email subject line')
    add_template_parser.add_argument('--body-file', required=True, help='Path to file containing template body')
    add_template_parser.set_defaults(func=add_template)
    
    # List templates command
    list_templates_parser = subparsers.add_parser('list-templates', help='List all email templates')
    list_templates_parser.set_defaults(func=list_templates)
    
    # Update template command
    update_template_parser = subparsers.add_parser('update-template', help='Update an existing email template')
    update_template_parser.add_argument('--id', type=int, required=True, help='Template ID to update')
    update_template_parser.add_argument('--name', help='New template name')
    update_template_parser.add_argument('--subject', help='New email subject line')
    update_template_parser.add_argument('--body-file', help='Path to file containing new template body')
    update_template_parser.set_defaults(func=update_template)
    
    # Delete template command
    delete_template_parser = subparsers.add_parser('delete-template', help='Delete an email template')
    delete_template_parser.add_argument('--id', type=int, required=True, help='Template ID to delete')
    delete_template_parser.set_defaults(func=delete_template)
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute the command
    args.func(args)


if __name__ == '__main__':
    main()

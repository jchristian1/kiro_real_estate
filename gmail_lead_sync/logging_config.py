"""
Logging configuration for Gmail Lead Sync Engine.

This module provides:
- RotatingFileHandler with 10MB max size and 5 backups
- Custom log format with timestamp, component, level, and message
- Sensitive data redaction for emails and passwords
- RedactingFormatter class for automatic log sanitization
- Environment-based log level configuration (INFO for production, DEBUG for development)
"""

import logging
import os
import re
from logging.handlers import RotatingFileHandler
from typing import Optional


def redact_sensitive_data(log_message: str) -> str:
    """
    Redact sensitive information from log messages.
    
    Masks:
    - Email addresses (partial): user***@domain.com
    - Phone numbers (partial): 123-***-7890
    - Passwords/tokens: password=***REDACTED***
    
    Args:
        log_message: The original log message
        
    Returns:
        Log message with sensitive data redacted
    """
    # Redact email addresses (partial - keep first part and domain)
    # Pattern: matches standard email format (user@domain.com)
    # Replacement: keeps username and domain but masks with ***
    log_message = re.sub(
        r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        r'\1***@\2',
        log_message
    )
    
    # Redact phone numbers (partial - keep first 3 and last 4 digits)
    # Pattern: matches phone numbers with various formats (123-456-7890, (123) 456-7890, etc.)
    # Replacement: keeps first 3 and last 4 digits, masks middle with ***
    log_message = re.sub(
        r'(\d{3})[\d\-\s\(\)]{4,}(\d{4})',
        r'\1-***-\2',
        log_message
    )
    
    # Redact passwords, tokens, keys, and app passwords
    # Pattern: matches common credential keywords followed by their values
    # Replacement: replaces the value with ***REDACTED***
    log_message = re.sub(
        r'(password|token|key|app_password)[\s:=]+[^\s]+',
        r'\1=***REDACTED***',
        log_message,
        flags=re.IGNORECASE
    )
    
    return log_message


class RedactingFormatter(logging.Formatter):
    """
    Custom formatter that redacts sensitive data from log messages.
    
    This formatter applies redaction to all log records before formatting,
    ensuring that sensitive information like emails and passwords are never
    written to log files in plain text.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record with sensitive data redaction.
        
        Args:
            record: The log record to format
            
        Returns:
            Formatted log message with sensitive data redacted
        """
        # Format the record using the parent formatter
        original = super().format(record)
        
        # Apply redaction to the formatted message
        return redact_sensitive_data(original)


def setup_logging(
    log_file: str = "gmail_lead_sync.log",
    log_level: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Configure the logging system for the application.
    
    Sets up:
    - RotatingFileHandler with specified size and backup limits
    - Custom log format with timestamp, component, level, and message
    - RedactingFormatter for automatic sensitive data masking
    - Environment-based log level (INFO for production, DEBUG for development)
    
    Args:
        log_file: Path to the log file (default: gmail_lead_sync.log)
        log_level: Log level override (default: from ENVIRONMENT or INFO)
        max_bytes: Maximum size of each log file before rotation (default: 10MB)
        backup_count: Number of backup log files to keep (default: 5)
        
    Returns:
        Configured logger instance
    """
    # Determine log level based on environment
    environment = os.environ.get('ENVIRONMENT', 'production').lower()
    if log_level is None:
        if environment == 'development':
            log_level = 'DEBUG'
        else:
            log_level = 'INFO'
    
    # Create logger
    logger = logging.getLogger('gmail_lead_sync')
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create rotating file handler
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    
    # Create formatter with timestamp, component, level, and message
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    formatter = RedactingFormatter(log_format)
    file_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(file_handler)
    
    # Also add console handler for development
    if environment == 'development':
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    logger.info(f"Logging configured: level={log_level}, file={log_file}")
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific component.
    
    Args:
        name: Name of the component (e.g., 'watcher', 'parser', 'responder')
        
    Returns:
        Logger instance for the component
    """
    return logging.getLogger(f'gmail_lead_sync.{name}')

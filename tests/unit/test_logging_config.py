"""
Unit tests for logging configuration module.

Tests cover:
- Sensitive data redaction (emails, phones, passwords)
- RedactingFormatter functionality
- RotatingFileHandler configuration
- Log level configuration based on environment
- Log format structure
"""

import logging
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from gmail_lead_sync.logging_config import (
    RedactingFormatter,
    get_logger,
    redact_sensitive_data,
    setup_logging,
)


class TestRedactSensitiveData:
    """Test the redact_sensitive_data function."""
    
    def test_redact_email_addresses(self):
        """Test that email addresses are partially redacted."""
        message = "User email is john.doe@example.com"
        redacted = redact_sensitive_data(message)
        assert "john.doe***@example.com" in redacted
        assert "john.doe@example.com" not in redacted
    
    def test_redact_multiple_emails(self):
        """Test redaction of multiple email addresses."""
        message = "Emails: alice@test.com and bob@example.org"
        redacted = redact_sensitive_data(message)
        assert "alice***@test.com" in redacted
        assert "bob***@example.org" in redacted
    
    def test_redact_phone_numbers(self):
        """Test that phone numbers are partially redacted."""
        message = "Contact: 123-456-7890"
        redacted = redact_sensitive_data(message)
        assert "123-***-7890" in redacted
        assert "456" not in redacted
    
    def test_redact_phone_with_spaces(self):
        """Test redaction of phone numbers with spaces."""
        message = "Phone: 555 123 4567"
        redacted = redact_sensitive_data(message)
        assert "555-***-4567" in redacted
    
    def test_redact_phone_with_parentheses(self):
        """Test redaction of phone numbers with parentheses."""
        message = "Call (555) 123-4567"
        redacted = redact_sensitive_data(message)
        assert "555-***-4567" in redacted
    
    def test_redact_password_field(self):
        """Test that password fields are redacted."""
        message = "password=secret123"
        redacted = redact_sensitive_data(message)
        assert "password=***REDACTED***" in redacted
        assert "secret123" not in redacted
    
    def test_redact_token_field(self):
        """Test that token fields are redacted."""
        message = "token: abc123xyz"
        redacted = redact_sensitive_data(message)
        assert "token=***REDACTED***" in redacted
        assert "abc123xyz" not in redacted
    
    def test_redact_app_password(self):
        """Test that app_password fields are redacted."""
        message = "app_password=abcdefghijklmnop"
        redacted = redact_sensitive_data(message)
        assert "app_password=***REDACTED***" in redacted
        assert "abcdefghijklmnop" not in redacted
    
    def test_redact_case_insensitive(self):
        """Test that redaction is case-insensitive for keywords."""
        message = "PASSWORD=secret TOKEN=xyz KEY=abc"
        redacted = redact_sensitive_data(message)
        assert "PASSWORD=***REDACTED***" in redacted
        assert "TOKEN=***REDACTED***" in redacted
        assert "KEY=***REDACTED***" in redacted
    
    def test_no_redaction_needed(self):
        """Test that messages without sensitive data are unchanged."""
        message = "Processing email from lead source"
        redacted = redact_sensitive_data(message)
        assert redacted == message


class TestRedactingFormatter:
    """Test the RedactingFormatter class."""
    
    def test_formatter_redacts_email(self):
        """Test that formatter redacts emails in log records."""
        formatter = RedactingFormatter('%(message)s')
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='Email: user@example.com',
            args=(),
            exc_info=None
        )
        formatted = formatter.format(record)
        assert "user***@example.com" in formatted
        assert "user@example.com" not in formatted
    
    def test_formatter_redacts_password(self):
        """Test that formatter redacts passwords in log records."""
        formatter = RedactingFormatter('%(message)s')
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='Credentials: password=secret123',
            args=(),
            exc_info=None
        )
        formatted = formatter.format(record)
        assert "password=***REDACTED***" in formatted
        assert "secret123" not in formatted
    
    def test_formatter_preserves_format(self):
        """Test that formatter preserves the log format structure."""
        formatter = RedactingFormatter('%(levelname)s - %(message)s')
        record = logging.LogRecord(
            name='test',
            level=logging.WARNING,
            pathname='',
            lineno=0,
            msg='Test message',
            args=(),
            exc_info=None
        )
        formatted = formatter.format(record)
        assert formatted.startswith('WARNING - ')
        assert 'Test message' in formatted


class TestSetupLogging:
    """Test the setup_logging function."""
    
    def test_creates_log_file(self):
        """Test that setup_logging creates a log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')
            logger = setup_logging(log_file=log_file)
            
            # Write a log message
            logger.info("Test message")
            
            # Verify file was created
            assert os.path.exists(log_file)
    
    def test_rotating_handler_configuration(self):
        """Test that RotatingFileHandler is configured correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')
            max_bytes = 5 * 1024 * 1024  # 5MB
            backup_count = 3
            
            logger = setup_logging(
                log_file=log_file,
                max_bytes=max_bytes,
                backup_count=backup_count
            )
            
            # Find the RotatingFileHandler
            handler = None
            for h in logger.handlers:
                if isinstance(h, logging.handlers.RotatingFileHandler):
                    handler = h
                    break
            
            assert handler is not None
            assert handler.maxBytes == max_bytes
            assert handler.backupCount == backup_count
    
    def test_log_level_production_default(self):
        """Test that production environment uses INFO log level."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')
            
            with patch.dict(os.environ, {'ENVIRONMENT': 'production'}):
                logger = setup_logging(log_file=log_file)
                assert logger.level == logging.INFO
    
    def test_log_level_development(self):
        """Test that development environment uses DEBUG log level."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')
            
            with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
                logger = setup_logging(log_file=log_file)
                assert logger.level == logging.DEBUG
    
    def test_log_level_override(self):
        """Test that log_level parameter overrides environment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')
            
            with patch.dict(os.environ, {'ENVIRONMENT': 'production'}):
                logger = setup_logging(log_file=log_file, log_level='DEBUG')
                assert logger.level == logging.DEBUG
    
    def test_log_format_structure(self):
        """Test that log messages have correct format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')
            logger = setup_logging(log_file=log_file)
            
            logger.info("Test message")
            
            # Read log file
            with open(log_file, 'r') as f:
                log_content = f.read()
            
            # Verify format: timestamp - component - level - message
            assert 'gmail_lead_sync' in log_content
            assert 'INFO' in log_content
            assert 'Test message' in log_content
    
    def test_sensitive_data_not_logged(self):
        """Test that sensitive data is redacted in log files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')
            logger = setup_logging(log_file=log_file)
            
            logger.info("Processing email from user@example.com with password=secret123")
            
            # Read log file
            with open(log_file, 'r') as f:
                log_content = f.read()
            
            # Verify sensitive data is redacted
            assert "user***@example.com" in log_content
            assert "user@example.com" not in log_content
            assert "password=***REDACTED***" in log_content
            assert "secret123" not in log_content
    
    def test_console_handler_in_development(self):
        """Test that console handler is added in development mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')
            
            with patch.dict(os.environ, {'ENVIRONMENT': 'development'}):
                logger = setup_logging(log_file=log_file)
                
                # Check for StreamHandler
                has_console_handler = any(
                    isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.RotatingFileHandler)
                    for h in logger.handlers
                )
                assert has_console_handler
    
    def test_no_console_handler_in_production(self):
        """Test that console handler is not added in production mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')
            
            with patch.dict(os.environ, {'ENVIRONMENT': 'production'}):
                logger = setup_logging(log_file=log_file)
                
                # Check for StreamHandler (excluding RotatingFileHandler)
                has_console_handler = any(
                    isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.RotatingFileHandler)
                    for h in logger.handlers
                )
                assert not has_console_handler


class TestGetLogger:
    """Test the get_logger function."""
    
    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger instance."""
        logger = get_logger('test_component')
        assert isinstance(logger, logging.Logger)
    
    def test_get_logger_naming(self):
        """Test that get_logger creates correctly named loggers."""
        logger = get_logger('watcher')
        assert logger.name == 'gmail_lead_sync.watcher'
    
    def test_get_logger_different_components(self):
        """Test that different components get different loggers."""
        watcher_logger = get_logger('watcher')
        parser_logger = get_logger('parser')
        
        assert watcher_logger.name != parser_logger.name
        assert 'watcher' in watcher_logger.name
        assert 'parser' in parser_logger.name


class TestLogRotation:
    """Test log file rotation behavior."""
    
    def test_log_rotation_creates_backup(self):
        """Test that log rotation creates backup files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')
            max_bytes = 100  # Small size to trigger rotation
            
            logger = setup_logging(
                log_file=log_file,
                max_bytes=max_bytes,
                backup_count=2
            )
            
            # Write enough data to trigger rotation
            for i in range(50):
                logger.info(f"Test message {i} with some padding to increase size")
            
            # Check for backup files
            log_dir = Path(tmpdir)
            log_files = list(log_dir.glob('test.log*'))
            
            # Should have main log file and at least one backup
            assert len(log_files) >= 1

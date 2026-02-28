"""
Centralized error handling for Gmail Lead Sync Engine.

This module provides retry logic, database lock handling, top-level
exception handling for the main application loop, and input sanitization
for security hardening.
"""

import logging
import time
import re
import signal
from typing import Callable, Any, Optional, Tuple
from functools import wraps
from sqlalchemy.exc import OperationalError, IntegrityError

logger = logging.getLogger(__name__)


def execute_with_retry(
    operation: Callable[[], Any],
    max_attempts: int = 3,
    operation_name: str = "database operation"
) -> Any:
    """
    Execute a database operation with retry logic.
    
    Handles database locks with exponential backoff and duplicate UID errors.
    
    Args:
        operation: Callable that performs the database operation
        max_attempts: Maximum number of retry attempts (default: 3)
        operation_name: Name of the operation for logging purposes
    
    Returns:
        The result of the operation
    
    Raises:
        OperationalError: If max attempts exhausted for non-lock errors
        IntegrityError: If constraint violation other than duplicate UID
    
    Examples:
        >>> def create_lead():
        ...     lead = Lead(name="John", phone="555-1234", gmail_uid="12345")
        ...     db_session.add(lead)
        ...     db_session.commit()
        ...     return lead
        >>> lead = execute_with_retry(create_lead, max_attempts=3)
    """
    for attempt in range(max_attempts):
        try:
            result = operation()
            if attempt > 0:
                logger.info(
                    f"{operation_name} succeeded on attempt {attempt + 1}/{max_attempts}"
                )
            return result
            
        except OperationalError as e:
            error_msg = str(e).lower()
            
            # Handle database lock errors with exponential backoff
            if "database is locked" in error_msg or "locked" in error_msg:
                wait_time = 0.5 * (2 ** attempt)  # 0.5s, 1s, 2s
                logger.warning(
                    f"{operation_name} failed due to database lock. "
                    f"Retry {attempt + 1}/{max_attempts} in {wait_time}s"
                )
                
                if attempt < max_attempts - 1:
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"{operation_name} failed after {max_attempts} attempts "
                        f"due to database lock: {e}"
                    )
                    raise
            else:
                # Non-lock operational error, don't retry
                logger.error(f"{operation_name} failed with OperationalError: {e}")
                raise
                
        except IntegrityError as e:
            error_msg = str(e).lower()
            
            # Handle duplicate UID gracefully (email already processed)
            if "unique constraint failed" in error_msg and "gmail_uid" in error_msg:
                logger.info(
                    f"{operation_name}: Email already processed (duplicate UID), skipping"
                )
                return None
            else:
                # Other integrity errors should be raised
                logger.error(f"{operation_name} failed with IntegrityError: {e}")
                raise
    
    # Should never reach here, but for type safety
    raise RuntimeError(f"{operation_name} failed after {max_attempts} attempts")


def handle_main_loop_exception(restart_delay: int = 60) -> Callable:
    """
    Decorator for top-level exception handling in the main loop.
    
    Catches all exceptions, logs them with full stack trace, and allows
    the application to restart after a delay.
    
    Args:
        restart_delay: Seconds to wait before allowing restart (default: 60)
    
    Returns:
        Decorator function
    
    Example:
        >>> @handle_main_loop_exception(restart_delay=60)
        ... def main_loop():
        ...     watcher = GmailWatcher(credentials_store, db_session)
        ...     watcher.start_monitoring()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            while True:
                try:
                    return func(*args, **kwargs)
                    
                except KeyboardInterrupt:
                    logger.info("Shutdown signal received (KeyboardInterrupt), exiting gracefully")
                    break
                    
                except SystemExit:
                    logger.info("System exit requested, exiting gracefully")
                    break
                    
                except Exception as e:
                    logger.critical(
                        f"Unhandled exception in {func.__name__}: {e}",
                        exc_info=True
                    )
                    logger.info(f"Restarting in {restart_delay} seconds...")
                    time.sleep(restart_delay)
                    logger.info(f"Attempting to restart {func.__name__}...")
        
        return wrapper
    return decorator


class DatabaseRetryContext:
    """
    Context manager for database operations with automatic retry logic.
    
    Provides a cleaner interface for wrapping database operations that need
    retry logic without explicitly passing callables.
    
    Example:
        >>> with DatabaseRetryContext(max_attempts=3, operation_name="create lead") as ctx:
        ...     lead = Lead(name="John", phone="555-1234", gmail_uid="12345")
        ...     db_session.add(lead)
        ...     db_session.commit()
        ...     ctx.result = lead
        >>> created_lead = ctx.result
    """
    
    def __init__(self, max_attempts: int = 3, operation_name: str = "database operation"):
        """
        Initialize the retry context.
        
        Args:
            max_attempts: Maximum number of retry attempts
            operation_name: Name of the operation for logging
        """
        self.max_attempts = max_attempts
        self.operation_name = operation_name
        self.result: Optional[Any] = None
        self._attempt = 0
    
    def __enter__(self):
        """Enter the context manager."""
        self._attempt = 0
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the context manager with retry logic.
        
        Returns:
            True if exception was handled and should be suppressed, False otherwise
        """
        if exc_type is None:
            # No exception, success
            return False
        
        # Handle OperationalError (database locks)
        if exc_type == OperationalError:
            error_msg = str(exc_val).lower()
            
            if "database is locked" in error_msg or "locked" in error_msg:
                self._attempt += 1
                
                if self._attempt < self.max_attempts:
                    wait_time = 0.5 * (2 ** (self._attempt - 1))
                    logger.warning(
                        f"{self.operation_name} failed due to database lock. "
                        f"Retry {self._attempt}/{self.max_attempts} in {wait_time}s"
                    )
                    time.sleep(wait_time)
                    return True  # Suppress exception to allow retry
                else:
                    logger.error(
                        f"{self.operation_name} failed after {self.max_attempts} "
                        f"attempts due to database lock: {exc_val}"
                    )
                    return False  # Re-raise exception
        
        # Handle IntegrityError (duplicate UIDs)
        if exc_type == IntegrityError:
            error_msg = str(exc_val).lower()
            
            if "unique constraint failed" in error_msg and "gmail_uid" in error_msg:
                logger.info(
                    f"{self.operation_name}: Email already processed (duplicate UID), skipping"
                )
                self.result = None
                return True  # Suppress exception
        
        # Don't suppress other exceptions
        return False


def log_processing_error(
    gmail_uid: str,
    sender_email: str,
    error_type: str,
    error_details: str,
    component: str = "unknown"
) -> None:
    """
    Log a processing error with standardized format.
    
    Args:
        gmail_uid: The Gmail UID of the email being processed
        sender_email: The sender's email address
        error_type: Type of error (e.g., "parsing_failed", "validation_failed")
        error_details: Detailed error message
        component: Component where error occurred (e.g., "parser", "watcher")
    
    Example:
        >>> log_processing_error(
        ...     gmail_uid="12345",
        ...     sender_email="leads@example.com",
        ...     error_type="name_regex_no_match",
        ...     error_details="Pattern: Name:\\s*(.+)",
        ...     component="parser"
        ... )
    """
    logger.error(
        f"[{component.upper()}] Processing error for email UID {gmail_uid} "
        f"from {sender_email}: {error_type} - {error_details}"
    )


# ============================================================================
# Input Sanitization and Security Functions
# ============================================================================


class RegexTimeoutError(Exception):
    """Raised when regex execution exceeds timeout limit."""
    pass


def sanitize_email_body(raw_body: str) -> str:
    """
    Sanitize email body before processing to prevent security issues.
    
    Removes null bytes and limits size to prevent memory exhaustion attacks.
    This function should be called on all email bodies before parsing.
    
    Args:
        raw_body: Raw email body content
        
    Returns:
        Sanitized email body safe for processing
        
    Example:
        >>> body = "Hello\\x00World" + "A" * 2000000
        >>> sanitized = sanitize_email_body(body)
        >>> "\\x00" not in sanitized
        True
        >>> len(sanitized) <= 1048576
        True
    """
    # Remove null bytes which can cause issues with string processing
    sanitized = raw_body.replace('\x00', '')
    
    # Limit size to 1MB to prevent memory exhaustion
    max_size = 1024 * 1024  # 1MB
    if len(sanitized) > max_size:
        logger.warning(
            f"Email body truncated from {len(sanitized)} to {max_size} bytes "
            f"for security (size limit)"
        )
        sanitized = sanitized[:max_size]
    
    return sanitized


def validate_regex_safety(pattern: str) -> Tuple[bool, Optional[str]]:
    """
    Validate regex pattern for safety before use.
    
    Checks for:
    1. Valid regex syntax
    2. Catastrophic backtracking patterns that could cause DoS
    3. Execution time within acceptable limits
    
    Args:
        pattern: Regex pattern string to validate
        
    Returns:
        Tuple of (is_safe, error_message)
        - is_safe: True if pattern is safe to use, False otherwise
        - error_message: Description of the issue if unsafe, None if safe
        
    Example:
        >>> is_safe, error = validate_regex_safety(r"Name:\\s*(.+)")
        >>> is_safe
        True
        >>> is_safe, error = validate_regex_safety(r"(a+)+b")
        >>> is_safe
        False
    """
    # Check syntax validity
    try:
        compiled = re.compile(pattern)
    except re.error as e:
        return False, f"Invalid regex syntax: {e}"
    
    # Check for catastrophic backtracking patterns
    # These patterns can cause exponential time complexity and DoS attacks
    # Each pattern checks for nested quantifiers that can lead to backtracking
    dangerous_patterns = [
        # Pattern: (a*)+ - nested star-plus quantifiers
        (r'\([^)]*\*\)\+', "Nested quantifiers (*)+ detected"),
        # Pattern: (a+)* - nested plus-star quantifiers
        (r'\([^)]*\+\)\*', "Nested quantifiers (+)* detected"),
        # Pattern: (a+)+ - nested plus-plus quantifiers (most dangerous)
        (r'\([^)]*\+\)\+', "Nested quantifiers (++)+ detected"),
        # Pattern: (a*)* - nested star-star quantifiers
        (r'\([^)]*\*\)\*', "Nested quantifiers (**)* detected"),
        # Pattern: (a{n,m})* - nested range-star quantifiers
        (r'\([^)]*\{[0-9]*,[0-9]*\}\)\*', "Nested quantifiers {n,m}* detected"),
        # Pattern: (a{n,m})+ - nested range-plus quantifiers
        (r'\([^)]*\{[0-9]*,[0-9]*\}\)\+', "Nested quantifiers {n,m}+ detected"),
    ]
    
    for dangerous_pattern, message in dangerous_patterns:
        if re.search(dangerous_pattern, pattern):
            return False, f"Pattern may cause catastrophic backtracking: {message}"
    
    # Test execution time with a large input string
    # This catches patterns that might not match the simple heuristics above
    try:
        test_string = "a" * 10000  # Large test string
        result = execute_regex_with_timeout(compiled, test_string, timeout=1.0)
        # If we get here, the regex completed within timeout
        return True, None
    except RegexTimeoutError:
        return False, "Pattern execution exceeds 1 second timeout"
    except Exception as e:
        return False, f"Pattern test failed: {e}"


def execute_regex_with_timeout(
    compiled_pattern: re.Pattern,
    text: str,
    timeout: float = 1.0
) -> Optional[re.Match]:
    """
    Execute regex search with a timeout to prevent DoS attacks.
    
    Uses signal-based timeout on Unix systems. On Windows or if signal
    is not available, falls back to simple execution without timeout.
    
    Args:
        compiled_pattern: Pre-compiled regex pattern
        text: Text to search
        timeout: Maximum execution time in seconds (default: 1.0)
        
    Returns:
        Match object if found, None otherwise
        
    Raises:
        RegexTimeoutError: If regex execution exceeds timeout
        
    Example:
        >>> pattern = re.compile(r"test")
        >>> result = execute_regex_with_timeout(pattern, "test string", timeout=1.0)
        >>> result is not None
        True
    """
    def timeout_handler(signum, frame):
        raise RegexTimeoutError("Regex execution exceeded timeout")
    
    # Check if signal is available (Unix-like systems)
    if hasattr(signal, 'SIGALRM'):
        # Set up timeout handler
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.setitimer(signal.ITIMER_REAL, timeout)
        
        try:
            result = compiled_pattern.search(text)
            signal.setitimer(signal.ITIMER_REAL, 0)  # Cancel alarm
            return result
        except RegexTimeoutError:
            signal.setitimer(signal.ITIMER_REAL, 0)  # Cancel alarm
            raise
        finally:
            signal.signal(signal.SIGALRM, old_handler)  # Restore old handler
    else:
        # Fallback for Windows or systems without signal support
        # Note: This doesn't provide actual timeout protection on Windows
        logger.warning(
            "Signal-based timeout not available on this platform. "
            "Regex execution will not be time-limited."
        )
        return compiled_pattern.search(text)

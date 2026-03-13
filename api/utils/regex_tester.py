"""
Regex testing utility with timeout protection.

This module provides safe regex testing functionality with timeout enforcement
to protect against ReDoS (Regular Expression Denial of Service) attacks.

Requirements:
- 2.4: Enforce timeout of 1000 milliseconds for regex execution
- 14.3: Enforce timeout of 1000 milliseconds for regex execution
- 14.4: Return timeout error if regex execution exceeds timeout
"""

import re
import signal
import platform
from typing import Optional, Tuple, List
from threading import Timer


class RegexTimeoutError(Exception):
    """Exception raised when regex execution exceeds timeout."""
    pass


def _timeout_handler(signum, frame):
    """Signal handler for regex timeout on Unix systems."""
    raise RegexTimeoutError("Regex execution timeout")


def test_regex_unix(pattern: str, text: str, timeout_ms: int = 1000) -> Tuple[bool, List[str], Optional[str]]:
    """
    Test regex pattern against text with timeout protection (Unix systems).
    
    Uses signal.alarm() for timeout enforcement on Unix-like systems.
    
    Args:
        pattern: Compiled regex pattern
        text: Text to test against
        timeout_ms: Timeout in milliseconds (default: 1000)
        
    Returns:
        Tuple of (matched, groups, match_text)
        - matched: Whether the pattern matched
        - groups: List of captured groups
        - match_text: The matched text (None if no match)
        
    Raises:
        RegexTimeoutError: If regex execution exceeds timeout
        
    Requirements:
        - 2.4: Enforce timeout of 1000 milliseconds
        - 14.3: Enforce timeout of 1000 milliseconds
    """
    # Convert milliseconds to seconds (signal.alarm uses seconds)
    timeout_seconds = max(1, timeout_ms // 1000)
    
    # Set up signal handler
    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(timeout_seconds)
    
    try:
        # Compile and execute regex
        compiled_pattern = re.compile(pattern)
        match = compiled_pattern.search(text)
        
        # Cancel alarm
        signal.alarm(0)
        
        if match:
            # Extract groups (excluding group 0 which is the full match)
            groups = list(match.groups())
            match_text = match.group(0)
            return True, groups, match_text
        else:
            return False, [], None
            
    except RegexTimeoutError:
        # Cancel alarm and re-raise
        signal.alarm(0)
        raise
    finally:
        # Restore old signal handler
        signal.signal(signal.SIGALRM, old_handler)


def test_regex_windows(pattern: str, text: str, timeout_ms: int = 1000) -> Tuple[bool, List[str], Optional[str]]:
    """
    Test regex pattern against text with timeout protection (Windows systems).
    
    Uses threading.Timer for timeout enforcement on Windows systems where
    signal.alarm() is not available.
    
    Args:
        pattern: Regex pattern string
        text: Text to test against
        timeout_ms: Timeout in milliseconds (default: 1000)
        
    Returns:
        Tuple of (matched, groups, match_text)
        - matched: Whether the pattern matched
        - groups: List of captured groups
        - match_text: The matched text (None if no match)
        
    Raises:
        RegexTimeoutError: If regex execution exceeds timeout
        
    Requirements:
        - 2.4: Enforce timeout of 1000 milliseconds
        - 14.3: Enforce timeout of 1000 milliseconds
    """
    import threading
    
    result = {'matched': False, 'groups': [], 'match_text': None, 'error': None}
    
    def run_regex():
        try:
            compiled_pattern = re.compile(pattern)
            match = compiled_pattern.search(text)
            
            if match:
                result['matched'] = True
                result['groups'] = list(match.groups())
                result['match_text'] = match.group(0)
        except Exception as e:
            result['error'] = e
    
    # Create and start thread
    thread = threading.Thread(target=run_regex)
    thread.daemon = True
    thread.start()
    
    # Wait for thread with timeout
    timeout_seconds = timeout_ms / 1000.0
    thread.join(timeout=timeout_seconds)
    
    # Check if thread is still alive (timeout occurred)
    if thread.is_alive():
        # Thread is still running, timeout occurred
        raise RegexTimeoutError("Regex execution timeout")
    
    # Check for errors during execution
    if result['error']:
        raise result['error']
    
    return result['matched'], result['groups'], result['match_text']


def test_regex_pattern(pattern: str, text: str, timeout_ms: int = 1000) -> Tuple[bool, List[str], Optional[str]]:
    """
    Test regex pattern against text with timeout protection.

    Automatically selects the appropriate timeout mechanism based on the
    operating system: ``signal.alarm`` on Unix (more precise, sub-second
    granularity via a 1-second minimum), thread-based on Windows.

    Args:
        pattern: Regex pattern string
        text: Text to test against
        timeout_ms: Timeout in milliseconds (default: 1000, reads from
            ``REGEX_TIMEOUT_MS`` env var when called from the router)

    Returns:
        Tuple of (matched, groups, match_text)
        - matched: Whether the pattern matched
        - groups: List of captured groups
        - match_text: The matched text (None if no match)

    Raises:
        RegexTimeoutError: If regex execution exceeds timeout
        re.error: If regex pattern is invalid

    Requirements:
        - 2.3: Test regex patterns against sample text
        - 2.4: Enforce timeout of 1000 milliseconds
        - 14.1: Provide endpoint for testing regex patterns
        - 14.2: Return match results and captured groups
        - 14.3: Enforce timeout of 1000 milliseconds
        - 14.4: Return timeout error if execution exceeds timeout
        - 11.7: Enforce REGEX_TIMEOUT_MS configurable timeout
    """
    # Validate pattern first (will raise re.error if invalid)
    try:
        re.compile(pattern)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern: {str(e)}")

    # Use signal.alarm on Unix (main thread only); fall back to thread-based
    # on Windows or when running in a non-main thread (e.g. async workers).
    import threading
    if platform.system() != "Windows" and threading.current_thread() is threading.main_thread():
        return test_regex_unix(pattern, text, timeout_ms)
    return test_regex_windows(pattern, text, timeout_ms)

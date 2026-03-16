"""
Rate limiting component for Gmail Lead Sync & Response Engine.

This module provides rate limiting functionality to prevent excessive
IMAP requests that could trigger Gmail's rate limits or cause performance issues.

Classes:
    RateLimiter: Token bucket rate limiter for IMAP requests
"""

import time
import logging


logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter for IMAP requests.
    
    Implements a token bucket algorithm to limit the rate of IMAP requests
    to prevent triggering Gmail's rate limits. The limiter allows bursts
    up to the maximum request count while maintaining an average rate over
    the time window.
    
    Features:
        - Token bucket algorithm for smooth rate limiting
        - Configurable request rate (default: 100 requests per minute)
        - Automatic waiting when rate limit is reached
        - Logging for rate limit hits
    
    Requirements: 11.1
    """
    
    def __init__(self, max_requests: int = 100, time_window: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed in time window (default: 100)
            time_window: Time window in seconds (default: 60 seconds = 1 minute)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        logger.info(
            f"RateLimiter initialized: {max_requests} requests per {time_window} seconds"
        )
    
    def allow_request(self) -> bool:
        """
        Check if request is allowed under rate limit.
        
        Removes expired requests from the tracking list and checks if
        the current request count is below the maximum. If allowed,
        records the request timestamp.
        
        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        now = time.time()
        
        # Remove requests outside the time window
        self.requests = [req for req in self.requests if now - req < self.time_window]
        
        # Check if we're under the limit
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True
        
        return False
    
    def wait_if_needed(self) -> None:
        """
        Wait if rate limit is exceeded.
        
        Blocks execution until a request slot becomes available.
        Logs when rate limiting is applied.
        """
        if not self.allow_request():
            # Calculate wait time until oldest request expires
            now = time.time()
            oldest_request = min(self.requests)
            wait_time = self.time_window - (now - oldest_request)
            
            # Add small buffer to ensure we're past the window
            wait_time = max(0.1, wait_time + 0.1)
            
            logger.warning(
                f"IMAP rate limit reached ({self.max_requests} requests per "
                f"{self.time_window}s). Waiting {wait_time:.2f} seconds..."
            )
            
            time.sleep(wait_time)
            
            # After waiting, record the request
            self.requests.append(time.time())
    
    def get_current_rate(self) -> int:
        """
        Get current number of requests in the time window.
        
        Returns:
            Number of requests made in the current time window
        """
        now = time.time()
        self.requests = [req for req in self.requests if now - req < self.time_window]
        return len(self.requests)
    
    def reset(self) -> None:
        """
        Reset the rate limiter by clearing all tracked requests.
        
        Useful for testing or when starting a new monitoring session.
        """
        self.requests = []
        logger.info("RateLimiter reset")

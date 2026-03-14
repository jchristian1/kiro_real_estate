"""
Unit tests for RateLimiter component.

Tests the rate limiting functionality for IMAP requests.
"""

import time
from gmail_lead_sync.rate_limiter import RateLimiter


class TestRateLimiter:
    """Test suite for RateLimiter class."""
    
    def test_init(self):
        """Test RateLimiter initialization."""
        limiter = RateLimiter(max_requests=100, time_window=60)
        assert limiter.max_requests == 100
        assert limiter.time_window == 60
        assert limiter.requests == []
    
    def test_allow_request_under_limit(self):
        """Test that requests are allowed when under the limit."""
        limiter = RateLimiter(max_requests=5, time_window=1)
        
        # First 5 requests should be allowed
        for i in range(5):
            assert limiter.allow_request() is True
        
        # 6th request should be denied
        assert limiter.allow_request() is False
    
    def test_allow_request_after_window_expires(self):
        """Test that requests are allowed after time window expires."""
        limiter = RateLimiter(max_requests=2, time_window=1)
        
        # Use up the limit
        assert limiter.allow_request() is True
        assert limiter.allow_request() is True
        assert limiter.allow_request() is False
        
        # Wait for window to expire
        time.sleep(1.1)
        
        # Should be allowed again
        assert limiter.allow_request() is True
    
    def test_wait_if_needed_blocks_when_limit_reached(self):
        """Test that wait_if_needed blocks when rate limit is reached."""
        limiter = RateLimiter(max_requests=2, time_window=1)
        
        # Use up the limit
        limiter.allow_request()
        limiter.allow_request()
        
        # This should block for ~1 second
        start_time = time.time()
        limiter.wait_if_needed()
        elapsed = time.time() - start_time
        
        # Should have waited at least 0.9 seconds (allowing some margin)
        assert elapsed >= 0.9
    
    def test_wait_if_needed_does_not_block_when_under_limit(self):
        """Test that wait_if_needed doesn't block when under limit."""
        limiter = RateLimiter(max_requests=5, time_window=1)
        
        # Should not block
        start_time = time.time()
        limiter.wait_if_needed()
        elapsed = time.time() - start_time
        
        # Should be nearly instant (less than 0.1 seconds)
        assert elapsed < 0.1
    
    def test_get_current_rate(self):
        """Test getting current request rate."""
        limiter = RateLimiter(max_requests=10, time_window=1)
        
        assert limiter.get_current_rate() == 0
        
        limiter.allow_request()
        assert limiter.get_current_rate() == 1
        
        limiter.allow_request()
        limiter.allow_request()
        assert limiter.get_current_rate() == 3
    
    def test_get_current_rate_after_window_expires(self):
        """Test that get_current_rate excludes expired requests."""
        limiter = RateLimiter(max_requests=10, time_window=1)
        
        limiter.allow_request()
        limiter.allow_request()
        assert limiter.get_current_rate() == 2
        
        # Wait for window to expire
        time.sleep(1.1)
        
        # Old requests should be excluded
        assert limiter.get_current_rate() == 0
    
    def test_reset(self):
        """Test resetting the rate limiter."""
        limiter = RateLimiter(max_requests=5, time_window=1)
        
        # Make some requests
        limiter.allow_request()
        limiter.allow_request()
        limiter.allow_request()
        assert limiter.get_current_rate() == 3
        
        # Reset
        limiter.reset()
        assert limiter.get_current_rate() == 0
        assert limiter.requests == []
    
    def test_default_parameters(self):
        """Test that default parameters are 100 requests per 60 seconds."""
        limiter = RateLimiter()
        assert limiter.max_requests == 100
        assert limiter.time_window == 60
    
    def test_sliding_window_behavior(self):
        """Test that rate limiter uses sliding window (not fixed window)."""
        limiter = RateLimiter(max_requests=3, time_window=2)
        
        # Make 3 requests at t=0
        limiter.allow_request()
        limiter.allow_request()
        limiter.allow_request()
        
        # Should be at limit
        assert limiter.allow_request() is False
        
        # Wait 1 second (half the window)
        time.sleep(1.0)
        
        # Still at limit (requests haven't expired yet)
        assert limiter.allow_request() is False
        
        # Wait another 1.1 seconds (total 2.1 seconds)
        time.sleep(1.1)
        
        # Now requests should have expired
        assert limiter.allow_request() is True

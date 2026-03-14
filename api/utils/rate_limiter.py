"""
Shared rate limiter instance for the API.

Import this module to access the limiter for applying rate limit decorators.
The limiter is registered on the FastAPI app in api/main.py.

Requirements: 11.6
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Single shared limiter instance — registered on app.state.limiter in main.py
limiter = Limiter(key_func=get_remote_address)

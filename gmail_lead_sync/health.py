"""
Health check API for Gmail Lead Sync & Response Engine.

This module provides a Flask-based health check endpoint that monitors:
- Database connectivity
- Last successful sync time (within 1 hour)
- IMAP connection status

The endpoint returns:
- 200 OK for healthy status (all checks pass)
- 503 Service Unavailable for degraded status (any check fails)

Requirements: 11.5
"""

from flask import Flask, jsonify
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

from gmail_lead_sync.models import ProcessingLog
from gmail_lead_sync.watcher import GmailWatcher


logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global references to be set by the application
_db_session: Optional[Session] = None
_watcher: Optional[GmailWatcher] = None


def init_health_check(db_session: Session, watcher: Optional[GmailWatcher] = None) -> None:
    """
    Initialize health check with database session and watcher instance.
    
    This function must be called before the health check endpoint can be used.
    It sets up the global references needed for health monitoring.
    
    Args:
        db_session: SQLAlchemy database session for health checks
        watcher: Optional GmailWatcher instance for IMAP connection checks
    """
    global _db_session, _watcher
    _db_session = db_session
    _watcher = watcher
    logger.info("Health check initialized")


def check_database_connectivity() -> bool:
    """
    Check if database is accessible and responsive.
    
    Executes a simple SELECT query to verify database connectivity.
    
    Returns:
        True if database is accessible, False otherwise
    """
    if not _db_session:
        logger.error("Health check: Database session not initialized")
        return False
    
    try:
        # Execute simple query to test connectivity
        _db_session.execute(text("SELECT 1"))
        logger.debug("Health check: Database connectivity OK")
        return True
    except Exception as e:
        logger.error(f"Health check: Database connectivity failed: {e}")
        return False


def check_last_successful_sync(max_age_hours: int = 1) -> tuple[bool, Optional[datetime]]:
    """
    Check if a successful sync occurred within the specified time window.
    
    Queries the ProcessingLog table for the most recent successful processing
    and verifies it occurred within the last hour (by default).
    
    Args:
        max_age_hours: Maximum age in hours for considering sync healthy (default: 1)
        
    Returns:
        Tuple of (is_healthy, last_sync_timestamp)
        - is_healthy: True if recent successful sync exists, False otherwise
        - last_sync_timestamp: Datetime of last successful sync, or None if no sync found
    """
    if not _db_session:
        logger.error("Health check: Database session not initialized")
        return False, None
    
    try:
        # Query for most recent successful processing
        last_log = _db_session.query(ProcessingLog)\
            .filter(ProcessingLog.status == 'success')\
            .order_by(ProcessingLog.timestamp.desc())\
            .first()
        
        if not last_log:
            logger.warning("Health check: No successful sync found in processing logs")
            return False, None
        
        last_sync = last_log.timestamp
        time_since_sync = datetime.utcnow() - last_sync
        max_age = timedelta(hours=max_age_hours)
        
        is_healthy = time_since_sync < max_age
        
        if is_healthy:
            logger.debug(
                f"Health check: Last successful sync {time_since_sync.total_seconds():.0f}s ago"
            )
        else:
            logger.warning(
                f"Health check: Last successful sync {time_since_sync.total_seconds():.0f}s ago "
                f"(exceeds {max_age_hours} hour threshold)"
            )
        
        return is_healthy, last_sync
        
    except Exception as e:
        logger.error(f"Health check: Error checking last sync: {e}", exc_info=True)
        return False, None


def check_imap_connection() -> bool:
    """
    Check if IMAP connection is active and responsive.
    
    Verifies that the watcher's IMAP connection is established and can
    respond to commands.
    
    Returns:
        True if IMAP connection is healthy, False otherwise
    """
    if not _watcher:
        logger.debug("Health check: Watcher not initialized, skipping IMAP check")
        # Not having a watcher is not necessarily unhealthy (might not be running yet)
        return True
    
    try:
        is_connected = _watcher.is_connected()
        
        if is_connected:
            logger.debug("Health check: IMAP connection OK")
        else:
            logger.warning("Health check: IMAP connection not established")
        
        return is_connected
        
    except Exception as e:
        logger.error(f"Health check: Error checking IMAP connection: {e}", exc_info=True)
        return False


@app.route('/health')
def health_check() -> tuple[Dict[str, Any], int]:
    """
    Health check endpoint.
    
    Returns system health status including:
    - Overall status: 'healthy' or 'degraded'
    - Database connectivity status
    - IMAP connection status
    - Last successful sync timestamp
    - Current timestamp
    
    Returns:
        Tuple of (JSON response dict, HTTP status code)
        - 200 OK if all checks pass (healthy)
        - 503 Service Unavailable if any check fails (degraded)
        
    Requirements: 11.5
    """
    try:
        # Perform health checks
        db_healthy = check_database_connectivity()
        sync_healthy, last_sync = check_last_successful_sync()
        imap_healthy = check_imap_connection()
        
        # Determine overall status
        overall_healthy = db_healthy and sync_healthy and imap_healthy
        
        # Build response
        status = {
            'status': 'healthy' if overall_healthy else 'degraded',
            'database': 'connected' if db_healthy else 'disconnected',
            'imap': 'connected' if imap_healthy else 'disconnected',
            'last_successful_sync': last_sync.isoformat() if last_sync else None,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Determine HTTP status code
        http_status = 200 if overall_healthy else 503
        
        # Log health check result
        if overall_healthy:
            logger.info("Health check: System healthy")
        else:
            logger.warning(
                f"Health check: System degraded - "
                f"DB: {db_healthy}, Sync: {sync_healthy}, IMAP: {imap_healthy}"
            )
        
        return jsonify(status), http_status
        
    except Exception as e:
        # Unexpected error during health check
        logger.error(f"Health check: Unexpected error: {e}", exc_info=True)
        
        error_status = {
            'status': 'degraded',
            'database': 'unknown',
            'imap': 'unknown',
            'last_successful_sync': None,
            'timestamp': datetime.utcnow().isoformat(),
            'error': str(e)
        }
        
        return jsonify(error_status), 503


def run_health_server(host: str = '0.0.0.0', port: int = 5000, debug: bool = False) -> None:
    """
    Run the Flask health check server.
    
    This function starts the Flask development server for the health check endpoint.
    For production use, consider using a production WSGI server like Gunicorn.
    
    Args:
        host: Host address to bind to (default: '0.0.0.0' for all interfaces)
        port: Port number to listen on (default: 5000)
        debug: Enable Flask debug mode (default: False)
        
    Example:
        >>> from gmail_lead_sync.health import init_health_check, run_health_server
        >>> init_health_check(db_session, watcher)
        >>> run_health_server(port=8080)
    """
    logger.info(f"Starting health check server on {host}:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    # For testing purposes only
    # In production, use init_health_check() and run_health_server() from main application
    import sys
    print("Health check module - use init_health_check() and run_health_server() to start")
    print("Example usage:")
    print("  from gmail_lead_sync.health import init_health_check, run_health_server")
    print("  init_health_check(db_session, watcher)")
    print("  run_health_server(port=8080)")
    sys.exit(0)

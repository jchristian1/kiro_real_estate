"""
Configuration management for Gmail Lead Sync API.

This module provides:
- Configuration parsing from environment variables
- Configuration validation on startup
- Configuration validation command for pre-deployment checks
- Secure logging of configuration (excluding sensitive values)

Environment Variables:
- DATABASE_URL: SQLite database path (required)
- ENCRYPTION_KEY: Key for credential encryption (required)
- SECRET_KEY: Key for session signing (required)
- API_HOST: Host to bind to (default: 0.0.0.0)
- API_PORT: Port to bind to (default: 8000)
- CORS_ORIGINS: Comma-separated allowed origins (default: http://localhost:5173,http://localhost:3000)
- CORS_ALLOW_CREDENTIALS: Enable credentials in CORS (default: true)
- SESSION_TIMEOUT_HOURS: Session expiration time (default: 24)
- SYNC_INTERVAL_SECONDS: Default sync interval (default: 300)
- REGEX_TIMEOUT_MS: Regex execution timeout (default: 1000)
- MAX_LEADS_PER_PAGE: Pagination limit (default: 50)
- ENABLE_AUTO_RESTART: Auto-restart failed watchers (default: true)
- STATIC_FILES_DIR: Directory for frontend static files (default: ../frontend/dist)
- LOG_LEVEL: Logging level (default: INFO)
"""

import os
import sys
import logging
from typing import List
from dataclasses import dataclass, field
from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()


@dataclass
class Config:
    """
    Application configuration loaded from environment variables.
    
    Attributes:
        database_url: SQLite database path
        encryption_key: Key for credential encryption
        secret_key: Key for session signing
        api_host: Host to bind to
        api_port: Port to bind to
        cors_origins: List of allowed CORS origins
        cors_allow_credentials: Enable credentials in CORS
        session_timeout_hours: Session expiration time in hours
        sync_interval_seconds: Default sync interval in seconds
        regex_timeout_ms: Regex execution timeout in milliseconds
        max_leads_per_page: Maximum leads per page for pagination
        enable_auto_restart: Enable auto-restart for failed watchers
        static_files_dir: Directory for frontend static files
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    
    # Required configuration
    database_url: str
    encryption_key: str
    secret_key: str
    
    # Server configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # CORS configuration
    cors_origins: List[str] = field(default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"])
    cors_allow_credentials: bool = True
    
    # Session configuration
    session_timeout_hours: int = 24
    
    # Application settings
    sync_interval_seconds: int = 300
    regex_timeout_ms: int = 1000
    max_leads_per_page: int = 50
    enable_auto_restart: bool = True
    
    # Static files
    static_files_dir: str = "../frontend/dist"
    
    # Logging
    log_level: str = "INFO"
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate()
    
    def _validate(self):
        """
        Validate configuration values.
        
        Raises:
            ValueError: If any configuration value is invalid
        """
        errors = []
        
        # Validate required fields
        if not self.database_url:
            errors.append("DATABASE_URL is required")
        
        if not self.encryption_key:
            errors.append("ENCRYPTION_KEY is required")
        elif len(self.encryption_key) < 32:
            errors.append("ENCRYPTION_KEY must be at least 32 characters")
        
        if not self.secret_key:
            errors.append("SECRET_KEY is required")
        elif len(self.secret_key) < 32:
            errors.append("SECRET_KEY must be at least 32 characters")
        
        # Validate port
        if not (1 <= self.api_port <= 65535):
            errors.append(f"API_PORT must be between 1 and 65535, got {self.api_port}")
        
        # Validate session timeout
        if self.session_timeout_hours < 1:
            errors.append(f"SESSION_TIMEOUT_HOURS must be at least 1, got {self.session_timeout_hours}")
        
        # Validate sync interval
        if self.sync_interval_seconds < 1:
            errors.append(f"SYNC_INTERVAL_SECONDS must be at least 1, got {self.sync_interval_seconds}")
        
        # Validate regex timeout
        if self.regex_timeout_ms < 1:
            errors.append(f"REGEX_TIMEOUT_MS must be at least 1, got {self.regex_timeout_ms}")
        
        # Validate max leads per page
        if not (1 <= self.max_leads_per_page <= 1000):
            errors.append(f"MAX_LEADS_PER_PAGE must be between 1 and 1000, got {self.max_leads_per_page}")
        
        # Validate log level
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_log_levels:
            errors.append(f"LOG_LEVEL must be one of {valid_log_levels}, got {self.log_level}")
        
        # Validate CORS origins
        if not self.cors_origins:
            errors.append("CORS_ORIGINS must contain at least one origin")
        
        if errors:
            raise ValueError("Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors))
    
    def log_config(self, logger: logging.Logger):
        """
        Log configuration values, excluding sensitive data.
        
        Args:
            logger: Logger instance to use for logging
        """
        logger.info("Configuration loaded:")
        logger.info(f"  DATABASE_URL: {self._mask_sensitive(self.database_url)}")
        logger.info(f"  ENCRYPTION_KEY: {'*' * 8} (masked)")
        logger.info(f"  SECRET_KEY: {'*' * 8} (masked)")
        logger.info(f"  API_HOST: {self.api_host}")
        logger.info(f"  API_PORT: {self.api_port}")
        logger.info(f"  CORS_ORIGINS: {', '.join(self.cors_origins)}")
        logger.info(f"  CORS_ALLOW_CREDENTIALS: {self.cors_allow_credentials}")
        logger.info(f"  SESSION_TIMEOUT_HOURS: {self.session_timeout_hours}")
        logger.info(f"  SYNC_INTERVAL_SECONDS: {self.sync_interval_seconds}")
        logger.info(f"  REGEX_TIMEOUT_MS: {self.regex_timeout_ms}")
        logger.info(f"  MAX_LEADS_PER_PAGE: {self.max_leads_per_page}")
        logger.info(f"  ENABLE_AUTO_RESTART: {self.enable_auto_restart}")
        logger.info(f"  STATIC_FILES_DIR: {self.static_files_dir}")
        logger.info(f"  LOG_LEVEL: {self.log_level}")
    
    @staticmethod
    def _mask_sensitive(value: str) -> str:
        """
        Mask sensitive values for logging.
        
        Args:
            value: Value to mask
            
        Returns:
            Masked value showing only first and last 4 characters
        """
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}...{value[-4:]}"


def load_config() -> Config:
    """
    Load configuration from environment variables.
    
    Returns:
        Config instance with validated configuration
        
    Raises:
        ValueError: If configuration validation fails
    """
    # Parse CORS origins
    cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
    cors_origins = [origin.strip() for origin in cors_origins_str.split(",") if origin.strip()]
    
    # Parse boolean values
    cors_allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() in ("true", "1", "yes")
    enable_auto_restart = os.getenv("ENABLE_AUTO_RESTART", "true").lower() in ("true", "1", "yes")
    
    # Parse integer values
    try:
        api_port = int(os.getenv("API_PORT", "8000"))
    except ValueError:
        raise ValueError("API_PORT must be a valid integer")
    
    try:
        session_timeout_hours = int(os.getenv("SESSION_TIMEOUT_HOURS", "24"))
    except ValueError:
        raise ValueError("SESSION_TIMEOUT_HOURS must be a valid integer")
    
    try:
        sync_interval_seconds = int(os.getenv("SYNC_INTERVAL_SECONDS", "300"))
    except ValueError:
        raise ValueError("SYNC_INTERVAL_SECONDS must be a valid integer")
    
    try:
        regex_timeout_ms = int(os.getenv("REGEX_TIMEOUT_MS", "1000"))
    except ValueError:
        raise ValueError("REGEX_TIMEOUT_MS must be a valid integer")
    
    try:
        max_leads_per_page = int(os.getenv("MAX_LEADS_PER_PAGE", "50"))
    except ValueError:
        raise ValueError("MAX_LEADS_PER_PAGE must be a valid integer")
    
    # Create config instance
    config = Config(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./gmail_lead_sync.db"),
        encryption_key=os.getenv("ENCRYPTION_KEY", ""),
        secret_key=os.getenv("SECRET_KEY", ""),
        api_host=os.getenv("API_HOST", "0.0.0.0"),
        api_port=api_port,
        cors_origins=cors_origins,
        cors_allow_credentials=cors_allow_credentials,
        session_timeout_hours=session_timeout_hours,
        sync_interval_seconds=sync_interval_seconds,
        regex_timeout_ms=regex_timeout_ms,
        max_leads_per_page=max_leads_per_page,
        enable_auto_restart=enable_auto_restart,
        static_files_dir=os.getenv("STATIC_FILES_DIR", "../frontend/dist"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper()
    )
    
    return config


def validate_config_command():
    """
    Command-line tool for validating configuration.
    
    This function can be called from the command line to validate
    configuration before deployment:
    
        python -m api.config
    
    Exits with code 0 if configuration is valid, 1 if invalid.
    """
    print("Validating configuration...")
    print()
    
    try:
        config = load_config()
        print("✓ Configuration is valid!")
        print()
        
        # Print non-sensitive configuration
        print("Configuration summary:")
        print(f"  DATABASE_URL: {config._mask_sensitive(config.database_url)}")
        print(f"  ENCRYPTION_KEY: {'*' * 8} (masked)")
        print(f"  SECRET_KEY: {'*' * 8} (masked)")
        print(f"  API_HOST: {config.api_host}")
        print(f"  API_PORT: {config.api_port}")
        print(f"  CORS_ORIGINS: {', '.join(config.cors_origins)}")
        print(f"  CORS_ALLOW_CREDENTIALS: {config.cors_allow_credentials}")
        print(f"  SESSION_TIMEOUT_HOURS: {config.session_timeout_hours}")
        print(f"  SYNC_INTERVAL_SECONDS: {config.sync_interval_seconds}")
        print(f"  REGEX_TIMEOUT_MS: {config.regex_timeout_ms}")
        print(f"  MAX_LEADS_PER_PAGE: {config.max_leads_per_page}")
        print(f"  ENABLE_AUTO_RESTART: {config.enable_auto_restart}")
        print(f"  STATIC_FILES_DIR: {config.static_files_dir}")
        print(f"  LOG_LEVEL: {config.log_level}")
        
        sys.exit(0)
        
    except ValueError as e:
        print("✗ Configuration validation failed:")
        print(f"  {e}")
        print()
        print("Please check your environment variables and try again.")
        sys.exit(1)
    
    except Exception as e:
        print("✗ Unexpected error during validation:")
        print(f"  {e}")
        sys.exit(1)


if __name__ == "__main__":
    validate_config_command()

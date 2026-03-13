"""
Unit tests for configuration management.

Tests configuration parsing, validation, and logging.
"""

import os
import pytest
import logging
from unittest.mock import patch, MagicMock

from api.config import Config, load_config


class TestConfig:
    """Test suite for Config class."""
    
    def test_valid_config(self):
        """Test creating a valid configuration."""
        config = Config(
            database_url="sqlite:///./test.db",
            encryption_key="a" * 32,
            secret_key="b" * 32,
            api_host="127.0.0.1",
            api_port=8080,
            cors_origins=["http://localhost:3000"],
            cors_allow_credentials=True,
            session_timeout_hours=12,
            sync_interval_seconds=600,
            regex_timeout_ms=2000,
            max_leads_per_page=100,
            enable_auto_restart=False,
            static_files_dir="./dist",
            log_level="DEBUG"
        )
        
        assert config.database_url == "sqlite:///./test.db"
        assert config.encryption_key == "a" * 32
        assert config.secret_key == "b" * 32
        assert config.api_host == "127.0.0.1"
        assert config.api_port == 8080
        assert config.cors_origins == ["http://localhost:3000"]
        assert config.cors_allow_credentials is True
        assert config.session_timeout_hours == 12
        assert config.sync_interval_seconds == 600
        assert config.regex_timeout_ms == 2000
        assert config.max_leads_per_page == 100
        assert config.enable_auto_restart is False
        assert config.static_files_dir == "./dist"
        assert config.log_level == "DEBUG"
    
    def test_missing_database_url(self):
        """Test that missing DATABASE_URL raises ValueError."""
        with pytest.raises(ValueError, match="DATABASE_URL is required"):
            Config(
                database_url="",
                encryption_key="a" * 32,
                secret_key="b" * 32
            )
    
    def test_missing_encryption_key(self):
        """Test that missing ENCRYPTION_KEY raises ValueError."""
        with pytest.raises(ValueError, match="ENCRYPTION_KEY is required"):
            Config(
                database_url="sqlite:///./test.db",
                encryption_key="",
                secret_key="b" * 32
            )
    
    def test_short_encryption_key(self):
        """Test that short ENCRYPTION_KEY raises ValueError."""
        with pytest.raises(ValueError, match="ENCRYPTION_KEY must be at least 32 characters"):
            Config(
                database_url="sqlite:///./test.db",
                encryption_key="short",
                secret_key="b" * 32
            )
    
    def test_missing_secret_key(self):
        """Test that missing SECRET_KEY raises ValueError."""
        with pytest.raises(ValueError, match="SECRET_KEY is required"):
            Config(
                database_url="sqlite:///./test.db",
                encryption_key="a" * 32,
                secret_key=""
            )
    
    def test_short_secret_key(self):
        """Test that short SECRET_KEY raises ValueError."""
        with pytest.raises(ValueError, match="SECRET_KEY must be at least 32 characters"):
            Config(
                database_url="sqlite:///./test.db",
                encryption_key="a" * 32,
                secret_key="short"
            )
    
    def test_invalid_port_too_low(self):
        """Test that port < 1 raises ValueError."""
        with pytest.raises(ValueError, match="API_PORT must be between 1 and 65535"):
            Config(
                database_url="sqlite:///./test.db",
                encryption_key="a" * 32,
                secret_key="b" * 32,
                api_port=0
            )
    
    def test_invalid_port_too_high(self):
        """Test that port > 65535 raises ValueError."""
        with pytest.raises(ValueError, match="API_PORT must be between 1 and 65535"):
            Config(
                database_url="sqlite:///./test.db",
                encryption_key="a" * 32,
                secret_key="b" * 32,
                api_port=70000
            )
    
    def test_invalid_session_timeout(self):
        """Test that session timeout < 1 raises ValueError."""
        with pytest.raises(ValueError, match="SESSION_TIMEOUT_HOURS must be at least 1"):
            Config(
                database_url="sqlite:///./test.db",
                encryption_key="a" * 32,
                secret_key="b" * 32,
                session_timeout_hours=0
            )
    
    def test_invalid_sync_interval(self):
        """Test that sync interval < 1 raises ValueError."""
        with pytest.raises(ValueError, match="SYNC_INTERVAL_SECONDS must be at least 1"):
            Config(
                database_url="sqlite:///./test.db",
                encryption_key="a" * 32,
                secret_key="b" * 32,
                sync_interval_seconds=0
            )
    
    def test_invalid_regex_timeout(self):
        """Test that regex timeout < 1 raises ValueError."""
        with pytest.raises(ValueError, match="REGEX_TIMEOUT_MS must be at least 1"):
            Config(
                database_url="sqlite:///./test.db",
                encryption_key="a" * 32,
                secret_key="b" * 32,
                regex_timeout_ms=0
            )
    
    def test_invalid_max_leads_per_page_too_low(self):
        """Test that max leads per page < 1 raises ValueError."""
        with pytest.raises(ValueError, match="MAX_LEADS_PER_PAGE must be between 1 and 1000"):
            Config(
                database_url="sqlite:///./test.db",
                encryption_key="a" * 32,
                secret_key="b" * 32,
                max_leads_per_page=0
            )
    
    def test_invalid_max_leads_per_page_too_high(self):
        """Test that max leads per page > 1000 raises ValueError."""
        with pytest.raises(ValueError, match="MAX_LEADS_PER_PAGE must be between 1 and 1000"):
            Config(
                database_url="sqlite:///./test.db",
                encryption_key="a" * 32,
                secret_key="b" * 32,
                max_leads_per_page=1001
            )
    
    def test_invalid_log_level(self):
        """Test that invalid log level raises ValueError."""
        with pytest.raises(ValueError, match="LOG_LEVEL must be one of"):
            Config(
                database_url="sqlite:///./test.db",
                encryption_key="a" * 32,
                secret_key="b" * 32,
                log_level="INVALID"
            )
    
    def test_empty_cors_origins(self):
        """Test that empty CORS origins raises ValueError."""
        with pytest.raises(ValueError, match="CORS_ORIGINS must contain at least one origin"):
            Config(
                database_url="sqlite:///./test.db",
                encryption_key="a" * 32,
                secret_key="b" * 32,
                cors_origins=[]
            )
    
    def test_log_config(self):
        """Test that log_config logs configuration without sensitive data."""
        config = Config(
            database_url="sqlite:///./test.db",
            encryption_key="a" * 32,
            secret_key="b" * 32
        )
        
        # Create a mock logger
        mock_logger = MagicMock(spec=logging.Logger)
        
        # Log configuration
        config.log_config(mock_logger)
        
        # Verify logger was called
        assert mock_logger.info.call_count > 0
        
        # Verify sensitive data is masked
        calls = [str(call) for call in mock_logger.info.call_args_list]
        log_output = " ".join(calls)
        
        # Encryption key should be masked
        assert "aaaa" not in log_output or "masked" in log_output
        # Secret key should be masked
        assert "bbbb" not in log_output or "masked" in log_output
    
    def test_mask_sensitive_short_value(self):
        """Test masking of short sensitive values."""
        masked = Config._mask_sensitive("short")
        assert masked == "*****"
        assert "short" not in masked
    
    def test_mask_sensitive_long_value(self):
        """Test masking of long sensitive values."""
        masked = Config._mask_sensitive("this_is_a_long_secret_key_value")
        assert masked.startswith("this")
        assert masked.endswith("alue")
        assert "..." in masked
        assert "secret" not in masked


class TestLoadConfig:
    """Test suite for load_config function."""
    
    @patch.dict(os.environ, {
        "DATABASE_URL": "sqlite:///./test.db",
        "ENCRYPTION_KEY": "a" * 32,
        "SECRET_KEY": "b" * 32,
        "API_HOST": "127.0.0.1",
        "API_PORT": "9000",
        "CORS_ORIGINS": "http://localhost:3000,http://localhost:5173",
        "CORS_ALLOW_CREDENTIALS": "true",
        "SESSION_TIMEOUT_HOURS": "48",
        "SYNC_INTERVAL_SECONDS": "600",
        "REGEX_TIMEOUT_MS": "2000",
        "MAX_LEADS_PER_PAGE": "100",
        "ENABLE_AUTO_RESTART": "false",
        "STATIC_FILES_DIR": "./dist",
        "LOG_LEVEL": "DEBUG"
    })
    def test_load_config_from_env(self):
        """Test loading configuration from environment variables."""
        config = load_config()
        
        assert config.database_url == "sqlite:///./test.db"
        assert config.encryption_key == "a" * 32
        assert config.secret_key == "b" * 32
        assert config.api_host == "127.0.0.1"
        assert config.api_port == 9000
        assert config.cors_origins == ["http://localhost:3000", "http://localhost:5173"]
        assert config.cors_allow_credentials is True
        assert config.session_timeout_hours == 48
        assert config.sync_interval_seconds == 600
        assert config.regex_timeout_ms == 2000
        assert config.max_leads_per_page == 100
        assert config.enable_auto_restart is False
        assert config.static_files_dir == "./dist"
        assert config.log_level == "DEBUG"
    
    @patch.dict(os.environ, {
        "DATABASE_URL": "sqlite:///./test.db",
        "ENCRYPTION_KEY": "a" * 32,
        "SECRET_KEY": "b" * 32
    }, clear=True)
    def test_load_config_with_defaults(self):
        """Test loading configuration with default values."""
        config = load_config()
        
        assert config.api_host == "0.0.0.0"
        assert config.api_port == 8000
        assert config.cors_origins == ["http://localhost:5173", "http://localhost:3000"]
        assert config.cors_allow_credentials is True
        assert config.session_timeout_hours == 24
        assert config.sync_interval_seconds == 300
        assert config.regex_timeout_ms == 1000
        assert config.max_leads_per_page == 50
        assert config.enable_auto_restart is True
        assert config.static_files_dir == "../frontend/dist"
        assert config.log_level == "INFO"
    
    @patch.dict(os.environ, {
        "DATABASE_URL": "sqlite:///./test.db",
        "ENCRYPTION_KEY": "a" * 32,
        "SECRET_KEY": "b" * 32,
        "API_PORT": "invalid"
    })
    def test_load_config_invalid_port(self):
        """Test that invalid port raises ValueError."""
        with pytest.raises(ValueError, match="API_PORT must be a valid integer"):
            load_config()
    
    @patch.dict(os.environ, {
        "DATABASE_URL": "sqlite:///./test.db",
        "ENCRYPTION_KEY": "a" * 32,
        "SECRET_KEY": "b" * 32,
        "SESSION_TIMEOUT_HOURS": "invalid"
    })
    def test_load_config_invalid_session_timeout(self):
        """Test that invalid session timeout raises ValueError."""
        with pytest.raises(ValueError, match="SESSION_TIMEOUT_HOURS must be a valid integer"):
            load_config()
    
    @patch.dict(os.environ, {
        "DATABASE_URL": "sqlite:///./test.db",
        "ENCRYPTION_KEY": "a" * 32,
        "SECRET_KEY": "b" * 32,
        "CORS_ALLOW_CREDENTIALS": "false"
    })
    def test_load_config_cors_credentials_false(self):
        """Test parsing CORS credentials as false."""
        config = load_config()
        assert config.cors_allow_credentials is False
    
    @patch.dict(os.environ, {
        "DATABASE_URL": "sqlite:///./test.db",
        "ENCRYPTION_KEY": "a" * 32,
        "SECRET_KEY": "b" * 32,
        "ENABLE_AUTO_RESTART": "0"
    })
    def test_load_config_auto_restart_false(self):
        """Test parsing auto restart as false."""
        config = load_config()
        assert config.enable_auto_restart is False
    
    @patch.dict(os.environ, {
        "DATABASE_URL": "sqlite:///./test.db",
        "ENCRYPTION_KEY": "a" * 32,
        "SECRET_KEY": "b" * 32,
        "CORS_ORIGINS": "  http://localhost:3000  ,  , http://localhost:5173  "
    })
    def test_load_config_cors_origins_with_whitespace(self):
        """Test parsing CORS origins with whitespace."""
        config = load_config()
        assert config.cors_origins == ["http://localhost:3000", "http://localhost:5173"]
    
    @patch.dict(os.environ, {
        "DATABASE_URL": "sqlite:///./test.db",
        "ENCRYPTION_KEY": "short",
        "SECRET_KEY": "b" * 32
    }, clear=True)
    def test_load_config_missing_required(self):
        """Test that invalid configuration raises ValueError."""
        with pytest.raises(ValueError, match="ENCRYPTION_KEY must be at least 32 characters"):
            load_config()

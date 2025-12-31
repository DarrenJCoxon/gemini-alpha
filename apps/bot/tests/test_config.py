"""
Tests for config.py - Configuration management.

Story 1.3: Kraken Data Ingestor - Configuration tests.
"""

import os
import pytest
from unittest.mock import patch


class TestDatabaseConfig:
    """Tests for DatabaseConfig class."""

    def test_database_config_defaults(self):
        """Test DatabaseConfig with default values when env vars missing."""
        # Test that defaults work by using patch on the os.getenv function
        import config as config_module

        # Test individual fields with patched getenv
        with patch.object(os, 'getenv', side_effect=lambda key, default="": default):
            db_config = config_module.DatabaseConfig()
            assert db_config.url == ""
            assert db_config.pool_size == 10
            assert db_config.debug is False

    def test_database_config_from_env(self):
        """Test DatabaseConfig reads from environment."""
        env_vars = {
            "DATABASE_URL": "postgresql://user:pass@host:5432/db",
            "DATABASE_POOL_SIZE": "20",
            "DEBUG": "true",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            db_config = config_module.DatabaseConfig()
            assert db_config.url == "postgresql://user:pass@host:5432/db"
            assert db_config.pool_size == 20
            assert db_config.debug is True

    def test_get_async_url_postgres(self):
        """Test URL conversion for postgres:// scheme."""
        import config as config_module

        db_config = config_module.DatabaseConfig()
        db_config.url = "postgres://user:pass@host:5432/db"

        result = db_config.get_async_url()
        assert result == "postgresql+asyncpg://user:pass@host:5432/db"

    def test_get_async_url_postgresql(self):
        """Test URL conversion for postgresql:// scheme."""
        import config as config_module

        db_config = config_module.DatabaseConfig()
        db_config.url = "postgresql://user:pass@host:5432/db"

        result = db_config.get_async_url()
        assert result == "postgresql+asyncpg://user:pass@host:5432/db"


class TestKrakenConfig:
    """Tests for KrakenConfig class."""

    def test_kraken_config_defaults(self):
        """Test KrakenConfig with default values."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            kraken_config = config_module.KrakenConfig()
            assert kraken_config.api_key is None
            assert kraken_config.api_secret is None
            assert kraken_config.rate_limit_ms == 500
            assert kraken_config.enable_rate_limit is True
            assert kraken_config.retry_count == 3
            assert kraken_config.retry_min_wait == 2
            assert kraken_config.retry_max_wait == 10

    def test_kraken_config_from_env(self):
        """Test KrakenConfig reads API credentials from environment."""
        env_vars = {
            "KRAKEN_API_KEY": "test_api_key",
            "KRAKEN_API_SECRET": "test_api_secret",
            "KRAKEN_RATE_LIMIT_MS": "1000",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            kraken_config = config_module.KrakenConfig()
            assert kraken_config.api_key == "test_api_key"
            assert kraken_config.api_secret == "test_api_secret"
            assert kraken_config.rate_limit_ms == 1000


class TestSchedulerConfig:
    """Tests for SchedulerConfig class."""

    def test_scheduler_config_defaults(self):
        """Test SchedulerConfig with default values."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            scheduler_config = config_module.SchedulerConfig()
            assert scheduler_config.timezone == "UTC"
            assert scheduler_config.ingest_cron_minutes == "0,15,30,45"
            assert scheduler_config.run_on_startup is False

    def test_scheduler_config_run_on_startup(self):
        """Test SchedulerConfig run_on_startup from environment."""
        env_vars = {"RUN_INGESTION_ON_STARTUP": "true"}
        with patch.dict(os.environ, env_vars, clear=True):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            scheduler_config = config_module.SchedulerConfig()
            assert scheduler_config.run_on_startup is True


class TestConfig:
    """Tests for main Config class."""

    def test_config_contains_all_sections(self):
        """Test Config aggregates all sub-configurations."""
        import config as config_module

        cfg = config_module.Config()
        assert hasattr(cfg, "database")
        assert hasattr(cfg, "kraken")
        assert hasattr(cfg, "scheduler")
        assert hasattr(cfg, "web_url")
        assert hasattr(cfg, "debug")

    def test_get_config_returns_singleton(self):
        """Test get_config returns the same instance."""
        import config as config_module

        cfg1 = config_module.get_config()
        cfg2 = config_module.get_config()
        assert cfg1 is cfg2

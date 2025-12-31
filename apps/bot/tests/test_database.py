"""
Tests for database.py - Database connection and session management.

Story 1.3: Tests for async session maker added for Kraken ingestion.
"""

import os
import pytest
from unittest.mock import patch, MagicMock


class TestDatabaseUrlConversion:
    """Tests for database URL conversion."""

    def test_postgres_url_converted(self):
        """Test postgres:// URL is converted to postgresql+asyncpg://"""
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgres://user:pass@host:5432/db"},
            clear=True,
        ):
            import importlib
            import database

            importlib.reload(database)

            assert database.DATABASE_URL == "postgresql+asyncpg://user:pass@host:5432/db"

    def test_postgresql_url_converted(self):
        """Test postgresql:// URL is converted to postgresql+asyncpg://"""
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://user:pass@host:5432/db"},
            clear=True,
        ):
            import importlib
            import database

            importlib.reload(database)

            assert database.DATABASE_URL == "postgresql+asyncpg://user:pass@host:5432/db"


class TestGetEngine:
    """Tests for get_engine function."""

    def test_get_engine_creates_engine(self):
        """Test get_engine creates engine when DATABASE_URL is set."""
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://user:pass@host:5432/db"},
            clear=True,
        ):
            import importlib
            import database

            importlib.reload(database)
            database.engine = None  # Reset singleton

            with patch("database.create_async_engine") as mock_create:
                mock_engine = MagicMock()
                mock_create.return_value = mock_engine

                engine = database.get_engine()

                assert engine is mock_engine
                mock_create.assert_called_once()

    def test_get_engine_returns_existing(self):
        """Test get_engine returns existing engine if already created."""
        import database

        mock_engine = MagicMock()
        database.engine = mock_engine

        result = database.get_engine()
        assert result is mock_engine

    def test_get_engine_raises_without_url(self):
        """Test get_engine raises ValueError when DATABASE_URL is not set."""
        import database

        # Save original values
        original_url = database.DATABASE_URL
        original_engine = database.engine

        try:
            # Set DATABASE_URL to empty and reset engine
            database.DATABASE_URL = ""
            database.engine = None

            with pytest.raises(ValueError, match="DATABASE_URL"):
                database.get_engine()
        finally:
            # Restore original values
            database.DATABASE_URL = original_url
            database.engine = original_engine


class TestGetSessionMaker:
    """Tests for get_session_maker function."""

    def test_get_session_maker_creates_session_maker(self):
        """Test get_session_maker creates async session maker."""
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://user:pass@host:5432/db"},
            clear=True,
        ):
            import importlib
            import database

            importlib.reload(database)
            database.engine = None
            database._session_maker = None

            with patch("database.create_async_engine") as mock_create_engine:
                with patch("database.async_sessionmaker") as mock_session_maker:
                    mock_engine = MagicMock()
                    mock_create_engine.return_value = mock_engine

                    mock_maker = MagicMock()
                    mock_session_maker.return_value = mock_maker

                    result = database.get_session_maker()

                    assert result is mock_maker
                    mock_session_maker.assert_called_once()

    def test_get_session_maker_returns_existing(self):
        """Test get_session_maker returns existing maker if already created."""
        import database

        mock_maker = MagicMock()
        database._session_maker = mock_maker

        result = database.get_session_maker()
        assert result is mock_maker


class TestInitDb:
    """Tests for init_db function."""

    @pytest.mark.asyncio
    async def test_init_db_success(self):
        """Test init_db establishes connection successfully."""
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://user:pass@host:5432/db"},
            clear=True,
        ):
            import importlib
            import database

            importlib.reload(database)
            database.engine = None

            with patch("database.create_async_engine") as mock_create:
                mock_engine = MagicMock()
                mock_conn = MagicMock()
                mock_conn.__aenter__ = MagicMock(return_value=mock_conn)
                mock_conn.__aexit__ = MagicMock(return_value=None)
                mock_conn.run_sync = MagicMock()
                mock_engine.begin.return_value = mock_conn
                mock_create.return_value = mock_engine

                # The function uses async context manager, need to mock properly
                from unittest.mock import AsyncMock

                mock_conn_context = AsyncMock()
                mock_engine.begin = MagicMock(return_value=mock_conn_context)
                mock_conn_context.__aenter__ = AsyncMock(return_value=mock_conn)
                mock_conn_context.__aexit__ = AsyncMock(return_value=None)

                await database.init_db()

    @pytest.mark.asyncio
    async def test_init_db_handles_connection_error(self):
        """Test init_db handles connection errors gracefully."""
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://user:pass@host:5432/db"},
            clear=True,
        ):
            import importlib
            import database

            importlib.reload(database)
            database.engine = None

            with patch("database.create_async_engine") as mock_create:
                mock_engine = MagicMock()
                mock_engine.begin.side_effect = Exception("Connection failed")
                mock_create.return_value = mock_engine

                # Should not raise, just log warning
                await database.init_db()


class TestGetSession:
    """Tests for get_session async generator."""

    @pytest.mark.asyncio
    async def test_get_session_yields_session(self):
        """Test get_session yields async session."""
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://user:pass@host:5432/db"},
            clear=True,
        ):
            import importlib
            import database

            importlib.reload(database)
            database.engine = None

            with patch("database.create_async_engine") as mock_create:
                with patch("database.AsyncSession") as mock_session_class:
                    from unittest.mock import AsyncMock

                    mock_engine = MagicMock()
                    mock_create.return_value = mock_engine

                    mock_session = AsyncMock()
                    mock_session_class.return_value.__aenter__ = AsyncMock(
                        return_value=mock_session
                    )
                    mock_session_class.return_value.__aexit__ = AsyncMock()

                    async for session in database.get_session():
                        assert session is not None
                        break

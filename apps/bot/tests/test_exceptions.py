"""
Tests for services/exceptions.py - Custom execution exceptions.

Story 3.1: Kraken Order Execution Service

Unit tests for all custom exception classes used in the
execution service.
"""

import pytest


class TestExecutionError:
    """Tests for base ExecutionError class."""

    def test_execution_error_basic(self):
        """Test basic exception creation."""
        from services.exceptions import ExecutionError

        error = ExecutionError("Test error message")
        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.details == {}

    def test_execution_error_with_details(self):
        """Test exception with additional details."""
        from services.exceptions import ExecutionError

        details = {"key": "value", "count": 42}
        error = ExecutionError("Test error", details=details)
        assert error.details == details
        assert error.details["key"] == "value"
        assert error.details["count"] == 42


class TestInsufficientFundsError:
    """Tests for InsufficientFundsError class."""

    def test_insufficient_funds_basic(self):
        """Test basic creation with default message."""
        from services.exceptions import InsufficientFundsError, ExecutionError

        error = InsufficientFundsError()
        assert "Insufficient funds" in str(error)
        assert isinstance(error, ExecutionError)

    def test_insufficient_funds_with_amounts(self):
        """Test with required and available amounts."""
        from services.exceptions import InsufficientFundsError

        error = InsufficientFundsError(
            message="Not enough USD",
            required_amount=100.0,
            available_amount=50.0,
            currency="USD",
        )
        assert error.required_amount == 100.0
        assert error.available_amount == 50.0
        assert error.currency == "USD"
        assert error.details["required_amount"] == 100.0
        assert error.details["available_amount"] == 50.0
        assert error.details["currency"] == "USD"

    def test_insufficient_funds_partial_params(self):
        """Test with only some parameters provided."""
        from services.exceptions import InsufficientFundsError

        error = InsufficientFundsError(currency="SOL")
        assert error.currency == "SOL"
        assert error.required_amount is None
        assert error.available_amount is None
        assert "currency" in error.details
        assert "required_amount" not in error.details


class TestDuplicatePositionError:
    """Tests for DuplicatePositionError class."""

    def test_duplicate_position_basic(self):
        """Test basic creation with default message."""
        from services.exceptions import DuplicatePositionError, ExecutionError

        error = DuplicatePositionError()
        assert "open position already exists" in str(error)
        assert isinstance(error, ExecutionError)

    def test_duplicate_position_with_asset_info(self):
        """Test with asset information."""
        from services.exceptions import DuplicatePositionError

        error = DuplicatePositionError(
            message="Position exists",
            asset_id="asset-123",
            asset_symbol="SOLUSD",
            existing_trade_id="trade-456",
        )
        assert error.asset_id == "asset-123"
        assert error.asset_symbol == "SOLUSD"
        assert error.existing_trade_id == "trade-456"
        assert error.details["asset_id"] == "asset-123"
        assert error.details["asset_symbol"] == "SOLUSD"
        assert error.details["existing_trade_id"] == "trade-456"


class TestRateLimitError:
    """Tests for RateLimitError class."""

    def test_rate_limit_basic(self):
        """Test basic creation with default message."""
        from services.exceptions import RateLimitError, ExecutionError

        error = RateLimitError()
        assert "rate limit exceeded" in str(error).lower()
        assert isinstance(error, ExecutionError)

    def test_rate_limit_with_retry_after(self):
        """Test with retry_after_seconds."""
        from services.exceptions import RateLimitError

        error = RateLimitError(
            message="Rate limited",
            retry_after_seconds=60,
        )
        assert error.retry_after_seconds == 60
        assert error.details["retry_after_seconds"] == 60


class TestOrderRejectedError:
    """Tests for OrderRejectedError class."""

    def test_order_rejected_basic(self):
        """Test basic creation with default message."""
        from services.exceptions import OrderRejectedError, ExecutionError

        error = OrderRejectedError()
        assert "rejected" in str(error).lower()
        assert isinstance(error, ExecutionError)

    def test_order_rejected_with_reason(self):
        """Test with rejection reason and order details."""
        from services.exceptions import OrderRejectedError

        order_details = {"symbol": "SOL/USD", "quantity": 10}
        error = OrderRejectedError(
            message="Order rejected by exchange",
            rejection_reason="Insufficient margin",
            order_details=order_details,
        )
        assert error.rejection_reason == "Insufficient margin"
        assert error.order_details == order_details
        assert error.details["rejection_reason"] == "Insufficient margin"
        assert error.details["symbol"] == "SOL/USD"


class TestConnectionError:
    """Tests for ConnectionError class."""

    def test_connection_error_basic(self):
        """Test basic creation with default message."""
        from services.exceptions import ConnectionError, ExecutionError

        error = ConnectionError()
        assert "connect" in str(error).lower()
        assert isinstance(error, ExecutionError)

    def test_connection_error_with_exchange(self):
        """Test with specific exchange."""
        from services.exceptions import ConnectionError

        error = ConnectionError(
            message="Connection failed",
            exchange="Kraken",
        )
        assert error.exchange == "Kraken"
        assert error.details["exchange"] == "Kraken"


class TestInvalidSymbolError:
    """Tests for InvalidSymbolError class."""

    def test_invalid_symbol_basic(self):
        """Test basic creation with default message."""
        from services.exceptions import InvalidSymbolError, ExecutionError

        error = InvalidSymbolError()
        assert "symbol" in str(error).lower()
        assert isinstance(error, ExecutionError)

    def test_invalid_symbol_with_symbol(self):
        """Test with specific symbol."""
        from services.exceptions import InvalidSymbolError

        error = InvalidSymbolError(
            message="Symbol not found",
            symbol="INVALID/USD",
        )
        assert error.symbol == "INVALID/USD"
        assert error.details["symbol"] == "INVALID/USD"


class TestPositionNotFoundError:
    """Tests for PositionNotFoundError class."""

    def test_position_not_found_basic(self):
        """Test basic creation with default message."""
        from services.exceptions import PositionNotFoundError, ExecutionError

        error = PositionNotFoundError()
        assert "not found" in str(error).lower()
        assert isinstance(error, ExecutionError)

    def test_position_not_found_with_ids(self):
        """Test with trade and asset IDs."""
        from services.exceptions import PositionNotFoundError

        error = PositionNotFoundError(
            message="Trade not found",
            trade_id="trade-123",
            asset_id="asset-456",
        )
        assert error.trade_id == "trade-123"
        assert error.asset_id == "asset-456"
        assert error.details["trade_id"] == "trade-123"
        assert error.details["asset_id"] == "asset-456"


class TestExceptionInheritance:
    """Tests for exception inheritance hierarchy."""

    def test_all_exceptions_inherit_from_execution_error(self):
        """Test all custom exceptions inherit from ExecutionError."""
        from services.exceptions import (
            ExecutionError,
            InsufficientFundsError,
            DuplicatePositionError,
            RateLimitError,
            OrderRejectedError,
            ConnectionError,
            InvalidSymbolError,
            PositionNotFoundError,
        )

        exceptions = [
            InsufficientFundsError(),
            DuplicatePositionError(),
            RateLimitError(),
            OrderRejectedError(),
            ConnectionError(),
            InvalidSymbolError(),
            PositionNotFoundError(),
        ]

        for exc in exceptions:
            assert isinstance(exc, ExecutionError)
            assert isinstance(exc, Exception)

    def test_can_catch_specific_exception(self):
        """Test specific exceptions can be caught separately."""
        from services.exceptions import (
            ExecutionError,
            InsufficientFundsError,
            DuplicatePositionError,
        )

        # Test catching InsufficientFundsError specifically
        try:
            raise InsufficientFundsError("Not enough USD")
        except InsufficientFundsError as e:
            assert "Not enough USD" in str(e)
        except ExecutionError:
            pytest.fail("Should have caught InsufficientFundsError specifically")

        # Test catching via base class
        try:
            raise DuplicatePositionError("Position exists")
        except ExecutionError as e:
            assert "Position exists" in str(e)

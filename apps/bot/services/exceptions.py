"""
Custom exceptions for the execution service.

Story 3.1: Kraken Order Execution Service

These exceptions provide clear error handling for trading operations,
allowing for proper error recovery and user feedback.
"""


class ExecutionError(Exception):
    """
    Base exception for all execution-related errors.

    All trading execution errors inherit from this class,
    making it easy to catch all execution failures.
    """

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InsufficientFundsError(ExecutionError):
    """
    Raised when account has insufficient funds for the requested trade.

    This typically occurs when:
    - USD balance is too low for a buy order
    - Token balance is too low for a sell order
    """

    def __init__(
        self,
        message: str = "Insufficient funds for this trade",
        required_amount: float | None = None,
        available_amount: float | None = None,
        currency: str | None = None,
    ):
        details = {}
        if required_amount is not None:
            details["required_amount"] = required_amount
        if available_amount is not None:
            details["available_amount"] = available_amount
        if currency is not None:
            details["currency"] = currency

        super().__init__(message, details)
        self.required_amount = required_amount
        self.available_amount = available_amount
        self.currency = currency


class DuplicatePositionError(ExecutionError):
    """
    Raised when trying to open a position that already exists.

    The system enforces ONE open position per asset. This error
    is raised when attempting to buy an asset that already has
    an OPEN trade in the database.
    """

    def __init__(
        self,
        message: str = "An open position already exists for this asset",
        asset_id: str | None = None,
        asset_symbol: str | None = None,
        existing_trade_id: str | None = None,
    ):
        details = {}
        if asset_id is not None:
            details["asset_id"] = asset_id
        if asset_symbol is not None:
            details["asset_symbol"] = asset_symbol
        if existing_trade_id is not None:
            details["existing_trade_id"] = existing_trade_id

        super().__init__(message, details)
        self.asset_id = asset_id
        self.asset_symbol = asset_symbol
        self.existing_trade_id = existing_trade_id


class RateLimitError(ExecutionError):
    """
    Raised when the exchange API rate limit is exceeded.

    Kraken has rate limits of approximately 15 calls per 3 seconds
    for private endpoints. This error should trigger retry logic
    with exponential backoff.
    """

    def __init__(
        self,
        message: str = "API rate limit exceeded",
        retry_after_seconds: int | None = None,
    ):
        details = {}
        if retry_after_seconds is not None:
            details["retry_after_seconds"] = retry_after_seconds

        super().__init__(message, details)
        self.retry_after_seconds = retry_after_seconds


class OrderRejectedError(ExecutionError):
    """
    Raised when the exchange rejects an order.

    This can occur due to:
    - Invalid order parameters
    - Trading pair not available
    - Market closed or in maintenance
    - Order size below minimum
    - Price moved too far from quote
    """

    def __init__(
        self,
        message: str = "Order was rejected by the exchange",
        rejection_reason: str | None = None,
        order_details: dict | None = None,
    ):
        details = order_details or {}
        if rejection_reason is not None:
            details["rejection_reason"] = rejection_reason

        super().__init__(message, details)
        self.rejection_reason = rejection_reason
        self.order_details = order_details


class ConnectionError(ExecutionError):
    """
    Raised when unable to connect to the exchange.

    This typically indicates network issues or exchange
    maintenance. Should trigger retry with backoff.
    """

    def __init__(
        self,
        message: str = "Unable to connect to exchange",
        exchange: str = "Kraken",
    ):
        details = {"exchange": exchange}
        super().__init__(message, details)
        self.exchange = exchange


class InvalidSymbolError(ExecutionError):
    """
    Raised when the trading symbol is invalid or not supported.

    This occurs when:
    - Symbol format is incorrect
    - Trading pair doesn't exist on the exchange
    - Symbol mapping is missing
    """

    def __init__(
        self,
        message: str = "Invalid trading symbol",
        symbol: str | None = None,
    ):
        details = {}
        if symbol is not None:
            details["symbol"] = symbol

        super().__init__(message, details)
        self.symbol = symbol


class PositionNotFoundError(ExecutionError):
    """
    Raised when attempting to close a position that doesn't exist.

    This can occur when:
    - Trade ID is invalid
    - Trade was already closed
    - Trade belongs to a different asset
    """

    def __init__(
        self,
        message: str = "Position not found",
        trade_id: str | None = None,
        asset_id: str | None = None,
    ):
        details = {}
        if trade_id is not None:
            details["trade_id"] = trade_id
        if asset_id is not None:
            details["asset_id"] = asset_id

        super().__init__(message, details)
        self.trade_id = trade_id
        self.asset_id = asset_id

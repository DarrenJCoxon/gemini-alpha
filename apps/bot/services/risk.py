"""
Dynamic Risk Engine for ATR-based Stop Loss Calculation.

Story 3.2: Dynamic Risk Engine (ATR Stop Loss)

This module provides risk management functions:
- calculate_atr(): Calculate Average True Range from candle data
- calculate_stop_loss(): Calculate dynamic stop loss based on ATR
- calculate_position_size(): (Optional) Risk-based position sizing

The engine adapts position risk to market volatility. During calm markets,
stops are tighter; during volatile periods, stops are wider to avoid
premature stop-outs.
"""

import logging
from decimal import Decimal
from typing import List, Optional, Tuple

import pandas as pd
import pandas_ta as ta

from config import get_config

# Configure logging
logger = logging.getLogger("risk_engine")


def calculate_atr(
    candles: List[dict],
    period: int = 14
) -> Optional[float]:
    """
    Calculate Average True Range (ATR) from OHLCV candle data.

    ATR measures market volatility by decomposing the entire range of an
    asset price for that period. The True Range is the greatest of:
    - Current High - Current Low
    - abs(Current High - Previous Close)
    - abs(Current Low - Previous Close)

    ATR is the moving average (EMA) of the True Range over the period.

    Args:
        candles: List of candle dicts with 'high', 'low', 'close' keys.
                 Each candle should contain at minimum:
                 - high: Highest price in the period
                 - low: Lowest price in the period
                 - close: Closing price
        period: ATR period (default: 14). Industry standard for crypto.

    Returns:
        Current ATR value as float, or None if insufficient data or error.

    Example:
        >>> candles = [{"high": 105.0, "low": 95.0, "close": 100.0}, ...]
        >>> atr = calculate_atr(candles, period=14)
        >>> print(f"ATR: ${atr:.4f}")
    """
    # Validate candle count
    if len(candles) < period + 1:
        logger.warning(
            f"Insufficient candles for ATR calculation. "
            f"Need {period + 1}, got {len(candles)}"
        )
        return None

    # Convert to DataFrame
    try:
        df = pd.DataFrame(candles)
    except Exception as e:
        logger.error(f"Failed to create DataFrame from candles: {e}")
        return None

    # Ensure required columns exist
    required_cols = ['high', 'low', 'close']
    if not all(col in df.columns for col in required_cols):
        logger.error(
            f"Missing required columns. Have: {df.columns.tolist()}, "
            f"Need: {required_cols}"
        )
        return None

    # Convert columns to numeric (handles string values)
    for col in required_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Check for NaN values after conversion
    if df[required_cols].isna().any().any():
        logger.warning("Candle data contains non-numeric values")
        # Drop rows with NaN and continue if we still have enough data
        df = df.dropna(subset=required_cols)
        if len(df) < period + 1:
            logger.error(f"Insufficient valid data after cleaning. Have: {len(df)}")
            return None

    # Calculate ATR using pandas-ta
    try:
        atr_series = ta.atr(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            length=period
        )
    except Exception as e:
        logger.error(f"pandas-ta ATR calculation failed: {e}")
        return None

    if atr_series is None or atr_series.empty:
        logger.error("ATR calculation returned empty result")
        return None

    # Get the most recent ATR value
    current_atr = atr_series.iloc[-1]

    if pd.isna(current_atr):
        logger.warning("ATR is NaN - likely insufficient data for calculation")
        return None

    # Validate ATR is positive
    if current_atr <= 0:
        logger.error(f"ATR calculation resulted in non-positive value: {current_atr}")
        return None

    logger.info(
        f"Calculated ATR({period}): {current_atr:.6f} "
        f"from {len(df)} candles"
    )
    return float(current_atr)


def calculate_stop_loss(
    entry_price: float,
    candles: List[dict],
    atr_multiplier: float = 2.0,
    atr_period: int = 14,
    max_stop_loss_percentage: float = 0.20,
    min_stop_loss_percentage: float = 0.02,
) -> Tuple[Optional[float], Optional[float]]:
    """
    Calculate dynamic stop loss based on ATR.

    Formula: Stop Loss = Entry Price - (ATR_Multiplier * ATR)

    The stop loss adapts to market volatility:
    - Low volatility: Tighter stops (less room for price movement)
    - High volatility: Wider stops (more breathing room)

    Args:
        entry_price: The trade entry price
        candles: Recent OHLCV candle data (at least period + 1 candles)
        atr_multiplier: Multiplier for ATR distance (default: 2.0)
        atr_period: ATR calculation period (default: 14)
        max_stop_loss_percentage: Maximum allowed stop loss percentage (default: 0.20 = 20%)
        min_stop_loss_percentage: Minimum allowed stop loss percentage (default: 0.02 = 2%)

    Returns:
        Tuple of (stop_loss_price, atr_value) or (None, None) on error.

    Example:
        >>> stop_loss, atr = calculate_stop_loss(
        ...     entry_price=100.0,
        ...     candles=candle_data,
        ...     atr_multiplier=2.0
        ... )
        >>> print(f"Entry: $100, Stop: ${stop_loss:.2f}, ATR: ${atr:.4f}")
        Entry: $100, Stop: $90.00, ATR: $5.0000
    """
    # Validate entry price
    if entry_price <= 0:
        logger.error(f"Invalid entry price: {entry_price}")
        return None, None

    # Calculate ATR
    atr = calculate_atr(candles, period=atr_period)

    if atr is None:
        logger.error("Cannot calculate stop loss - ATR calculation failed")
        return None, None

    # Calculate stop distance
    stop_distance = atr_multiplier * atr
    stop_loss_price = entry_price - stop_distance

    # Calculate percentage from entry
    stop_percentage = (entry_price - stop_loss_price) / entry_price

    # Check if stop loss is reasonable
    # If ATR gives unreasonable stop (too wide or negative), use fallback
    if stop_loss_price <= 0:
        logger.warning(
            f"Calculated stop loss is negative or zero: {stop_loss_price}. "
            f"Entry: {entry_price}, ATR: {atr}, Multiplier: {atr_multiplier}"
        )
        # Fall back to max stop loss percentage
        stop_loss_price = entry_price * (1 - max_stop_loss_percentage)
        logger.warning(
            f"Using fallback {max_stop_loss_percentage * 100:.0f}% stop loss: "
            f"${stop_loss_price:.4f}"
        )
        stop_percentage = max_stop_loss_percentage

    elif stop_percentage > max_stop_loss_percentage:
        # Stop is too wide - cap it
        logger.warning(
            f"ATR-based stop ({stop_percentage * 100:.2f}%) exceeds max "
            f"({max_stop_loss_percentage * 100:.0f}%). Capping."
        )
        stop_loss_price = entry_price * (1 - max_stop_loss_percentage)
        stop_percentage = max_stop_loss_percentage

    elif stop_percentage < min_stop_loss_percentage:
        # Stop is too tight - use minimum
        logger.warning(
            f"ATR-based stop ({stop_percentage * 100:.2f}%) is below min "
            f"({min_stop_loss_percentage * 100:.0f}%). Using minimum."
        )
        stop_loss_price = entry_price * (1 - min_stop_loss_percentage)
        stop_percentage = min_stop_loss_percentage

    logger.info(
        f"Stop Loss calculated: ${stop_loss_price:.4f} "
        f"({stop_percentage * 100:.2f}% below entry of ${entry_price:.4f})"
    )

    return stop_loss_price, atr


def calculate_stop_loss_with_config(
    entry_price: float,
    candles: List[dict],
) -> Tuple[Optional[float], Optional[float]]:
    """
    Calculate stop loss using configuration from environment variables.

    This is a convenience wrapper that loads RiskSettings from config
    and passes them to calculate_stop_loss().

    Args:
        entry_price: The trade entry price
        candles: Recent OHLCV candle data

    Returns:
        Tuple of (stop_loss_price, atr_value) or (None, None) on error.
    """
    config = get_config()

    # Access risk settings from config if available
    # Default values if RiskConfig not yet added
    atr_period = getattr(config, 'risk', None)
    if atr_period and hasattr(atr_period, 'atr_period'):
        return calculate_stop_loss(
            entry_price=entry_price,
            candles=candles,
            atr_multiplier=config.risk.atr_multiplier,
            atr_period=config.risk.atr_period,
            max_stop_loss_percentage=config.risk.max_stop_loss_percentage,
            min_stop_loss_percentage=config.risk.min_stop_loss_percentage,
        )
    else:
        # Use defaults
        return calculate_stop_loss(
            entry_price=entry_price,
            candles=candles,
        )


def calculate_position_size(
    account_balance: float,
    entry_price: float,
    stop_loss_price: float,
    risk_percentage: float = 0.02,
) -> Optional[float]:
    """
    Calculate position size based on risk per trade.

    This is an optional enhancement (V2) for risk-based position sizing.
    Instead of using a fixed USD amount, position size is calculated
    based on how much of the account we're willing to risk.

    Formula: Position Size = (Account * Risk%) / (Entry - Stop)

    Args:
        account_balance: Total account balance in USD
        entry_price: The trade entry price
        stop_loss_price: The calculated stop loss price
        risk_percentage: Percentage of account to risk per trade (default: 2%)

    Returns:
        Position size in base currency units, or None on error.

    Example:
        >>> size = calculate_position_size(
        ...     account_balance=10000.0,
        ...     entry_price=100.0,
        ...     stop_loss_price=90.0,
        ...     risk_percentage=0.02
        ... )
        >>> print(f"Position size: {size} units")
        Position size: 20.0 units  # Risk $200, $10 risk per unit
    """
    # Validate inputs
    if account_balance <= 0:
        logger.error(f"Invalid account balance: {account_balance}")
        return None

    if entry_price <= 0:
        logger.error(f"Invalid entry price: {entry_price}")
        return None

    if stop_loss_price <= 0:
        logger.error(f"Invalid stop loss price: {stop_loss_price}")
        return None

    if stop_loss_price >= entry_price:
        logger.error(
            f"Stop loss ({stop_loss_price}) must be below entry price ({entry_price})"
        )
        return None

    if not (0 < risk_percentage <= 0.10):
        logger.warning(
            f"Risk percentage {risk_percentage * 100:.1f}% is outside safe range. "
            f"Capping at 10%"
        )
        risk_percentage = min(risk_percentage, 0.10)

    # Calculate risk amount
    risk_amount = account_balance * risk_percentage

    # Calculate risk per unit (how much we lose per unit if stopped out)
    risk_per_unit = entry_price - stop_loss_price

    # Calculate position size
    position_size = risk_amount / risk_per_unit

    logger.info(
        f"Position size: {position_size:.4f} units "
        f"(risking ${risk_amount:.2f} of ${account_balance:.2f} account, "
        f"${risk_per_unit:.4f} risk per unit)"
    )

    return position_size


def validate_stop_loss(
    entry_price: float,
    stop_loss_price: float,
    max_percentage: float = 0.20,
    min_percentage: float = 0.02,
) -> Tuple[bool, str]:
    """
    Validate that a stop loss price is reasonable.

    Args:
        entry_price: The trade entry price
        stop_loss_price: The proposed stop loss price
        max_percentage: Maximum allowed stop loss percentage
        min_percentage: Minimum allowed stop loss percentage

    Returns:
        Tuple of (is_valid, reason_if_invalid)
    """
    if stop_loss_price <= 0:
        return False, "Stop loss price must be positive"

    if stop_loss_price >= entry_price:
        return False, "Stop loss must be below entry price for long positions"

    percentage = (entry_price - stop_loss_price) / entry_price

    if percentage > max_percentage:
        return False, f"Stop loss ({percentage * 100:.1f}%) exceeds maximum ({max_percentage * 100:.0f}%)"

    if percentage < min_percentage:
        return False, f"Stop loss ({percentage * 100:.1f}%) is below minimum ({min_percentage * 100:.0f}%)"

    return True, ""

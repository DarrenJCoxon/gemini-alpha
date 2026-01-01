#!/usr/bin/env python3
"""
Verification script for ATR-based stop loss calculation.

Story 3.2: Dynamic Risk Engine (ATR Stop Loss)

This script demonstrates and tests ATR-based stop loss calculation
with sample market data. Can be run manually to verify functionality.

Usage:
    python scripts/test_atr.py

For testing with real Kraken data (requires API credentials):
    python scripts/test_atr.py --live
"""

import argparse
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.risk import (
    calculate_atr,
    calculate_stop_loss,
    calculate_position_size,
    validate_stop_loss,
)


def generate_sample_candles(count: int = 50, base_price: float = 100.0) -> list:
    """Generate sample candle data for demonstration."""
    import random
    random.seed(42)

    candles = []
    close = base_price

    for i in range(count):
        volatility = 0.05
        change = random.uniform(-volatility, volatility)
        close = close * (1 + change)

        high = close * (1 + random.uniform(0.01, 0.03))
        low = close * (1 - random.uniform(0.01, 0.03))
        open_price = close * (1 + random.uniform(-0.02, 0.02))

        candles.append({
            "timestamp": 1704067200000 + (i * 900000),
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": random.uniform(1000, 10000),
        })

    return candles


def test_with_sample_data():
    """Test ATR and stop loss calculation with sample data."""
    print("=" * 60)
    print("ATR Stop Loss Calculation Test (Sample Data)")
    print("=" * 60)

    # Generate sample candles
    print("\n[1] Generating sample candles...")
    candles = generate_sample_candles(count=50, base_price=100.0)
    print(f"    Generated {len(candles)} candles")
    print(f"    Price range: ${min(c['low'] for c in candles):.2f} - ${max(c['high'] for c in candles):.2f}")

    # Calculate ATR
    print("\n[2] Calculating ATR(14)...")
    atr = calculate_atr(candles, period=14)
    if atr:
        print(f"    ATR: ${atr:.4f}")
    else:
        print("    ERROR: ATR calculation failed")
        return False

    # Calculate stop loss at current price
    current_price = candles[-1]['close']
    print(f"\n[3] Calculating stop loss...")
    print(f"    Current price: ${current_price:.4f}")

    stop_loss, _ = calculate_stop_loss(current_price, candles)
    if stop_loss:
        print(f"    Stop Loss (2x ATR): ${stop_loss:.4f}")
        stop_pct = ((current_price - stop_loss) / current_price) * 100
        print(f"    Distance: {stop_pct:.2f}%")
    else:
        print("    ERROR: Stop loss calculation failed")
        return False

    # Validate stop loss
    is_valid, reason = validate_stop_loss(current_price, stop_loss)
    print(f"\n[4] Validating stop loss...")
    print(f"    Valid: {is_valid}")
    if not is_valid:
        print(f"    Reason: {reason}")

    # Show different ATR scenarios
    print("\n[5] ATR Multiplier Scenarios:")
    for mult in [1.0, 1.5, 2.0, 2.5, 3.0]:
        sl, _ = calculate_stop_loss(current_price, candles, atr_multiplier=mult)
        if sl:
            pct = ((current_price - sl) / current_price) * 100
            print(f"    {mult}x ATR: ${sl:.4f} ({pct:.2f}% below entry)")

    # Calculate position size
    print("\n[6] Position Sizing Example:")
    account_balance = 10000.0
    size = calculate_position_size(
        account_balance=account_balance,
        entry_price=current_price,
        stop_loss_price=stop_loss,
        risk_percentage=0.02,
    )
    if size:
        risk_amount = account_balance * 0.02
        print(f"    Account Balance: ${account_balance:.2f}")
        print(f"    Risk per Trade: 2% (${risk_amount:.2f})")
        print(f"    Position Size: {size:.4f} units")
        print(f"    Position Value: ${size * current_price:.2f}")

    print("\n" + "=" * 60)
    print("Test Complete - All calculations successful")
    print("=" * 60)
    return True


def test_with_live_data():
    """Test with live Kraken data (requires API credentials)."""
    print("=" * 60)
    print("ATR Stop Loss Calculation Test (Live Kraken Data)")
    print("=" * 60)

    try:
        from services.kraken import KrakenClient
    except ImportError as e:
        print(f"\nERROR: Could not import KrakenClient: {e}")
        print("Make sure you're running from the apps/bot directory")
        return False

    try:
        client = KrakenClient()
    except Exception as e:
        print(f"\nERROR: Could not initialize Kraken client: {e}")
        print("Check your API credentials in .env file")
        return False

    # Test with SOL/USD
    symbol = "SOL/USD"
    print(f"\n[1] Fetching candles for {symbol}...")

    try:
        ohlcv = client.exchange.fetch_ohlcv(symbol, '15m', limit=50)
    except Exception as e:
        print(f"    ERROR: {e}")
        return False

    candles = [
        {
            "timestamp": c[0],
            "open": c[1],
            "high": c[2],
            "low": c[3],
            "close": c[4],
            "volume": c[5]
        }
        for c in ohlcv
    ]
    print(f"    Fetched {len(candles)} candles")

    # Calculate ATR
    print("\n[2] Calculating ATR(14)...")
    atr = calculate_atr(candles, period=14)
    if atr:
        print(f"    ATR: ${atr:.4f}")
    else:
        print("    ERROR: ATR calculation failed")
        return False

    # Calculate stop loss at current price
    current_price = candles[-1]['close']
    print(f"\n[3] Calculating stop loss...")
    print(f"    Current price: ${current_price:.4f}")

    stop_loss, _ = calculate_stop_loss(current_price, candles)
    if stop_loss:
        print(f"    Stop Loss (2x ATR): ${stop_loss:.4f}")
        stop_pct = ((current_price - stop_loss) / current_price) * 100
        print(f"    Distance: {stop_pct:.2f}%")
    else:
        print("    ERROR: Stop loss calculation failed")
        return False

    # Show different ATR scenarios
    print("\n[4] ATR Multiplier Scenarios:")
    for mult in [1.0, 1.5, 2.0, 2.5, 3.0]:
        sl, _ = calculate_stop_loss(current_price, candles, atr_multiplier=mult)
        if sl:
            pct = ((current_price - sl) / current_price) * 100
            print(f"    {mult}x ATR: ${sl:.4f} ({pct:.2f}% below entry)")

    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)
    return True


def test_edge_cases():
    """Test edge cases and error handling."""
    print("\n" + "=" * 60)
    print("Edge Case Tests")
    print("=" * 60)

    # Test 1: Insufficient data
    print("\n[1] Testing insufficient data handling...")
    candles = generate_sample_candles(count=5)
    atr = calculate_atr(candles, period=14)
    print(f"    ATR with 5 candles (need 15): {atr}")
    assert atr is None, "Should return None for insufficient data"
    print("    PASSED: Returns None as expected")

    # Test 2: Empty candle list
    print("\n[2] Testing empty candle list...")
    atr = calculate_atr([], period=14)
    print(f"    ATR with empty list: {atr}")
    assert atr is None, "Should return None for empty list"
    print("    PASSED: Returns None as expected")

    # Test 3: Invalid entry price
    print("\n[3] Testing invalid entry price...")
    candles = generate_sample_candles(count=20)
    sl, atr = calculate_stop_loss(entry_price=0, candles=candles)
    print(f"    Stop loss with zero entry: {sl}")
    assert sl is None, "Should return None for zero entry"
    print("    PASSED: Returns None as expected")

    # Test 4: Position size with stop above entry
    print("\n[4] Testing invalid stop loss for position sizing...")
    size = calculate_position_size(
        account_balance=10000,
        entry_price=100,
        stop_loss_price=110,  # Stop above entry (invalid)
    )
    print(f"    Position size with stop > entry: {size}")
    assert size is None, "Should return None for invalid stop"
    print("    PASSED: Returns None as expected")

    print("\n" + "=" * 60)
    print("All Edge Case Tests PASSED")
    print("=" * 60)
    return True


def main():
    parser = argparse.ArgumentParser(description="ATR Stop Loss Calculation Test")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Test with live Kraken data (requires API credentials)"
    )
    parser.add_argument(
        "--edge-cases",
        action="store_true",
        help="Run edge case tests"
    )
    args = parser.parse_args()

    success = True

    if args.live:
        success = test_with_live_data()
    else:
        success = test_with_sample_data()

    if args.edge_cases or not args.live:
        success = success and test_edge_cases()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

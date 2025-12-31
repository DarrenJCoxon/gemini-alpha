"""
Tests for SQLModel classes.

These tests verify that the Python SQLModel classes correctly mirror
the Prisma schema with proper field mappings and validations.
"""

import pytest
from datetime import datetime
from decimal import Decimal

from models import (
    Asset,
    Candle,
    SentimentLog,
    CouncilSession,
    Trade,
    Decision,
    TradeStatus,
    generate_cuid,
)


class TestDecisionEnum:
    """Tests for the Decision enum."""

    def test_decision_values_exist(self):
        """Test that all expected decision values exist."""
        assert Decision.BUY == "BUY"
        assert Decision.HOLD == "HOLD"
        assert Decision.SELL == "SELL"

    def test_decision_is_string_enum(self):
        """Test that Decision values are strings."""
        assert isinstance(Decision.BUY.value, str)
        assert isinstance(Decision.HOLD.value, str)
        assert isinstance(Decision.SELL.value, str)

    def test_decision_count(self):
        """Test that there are exactly 3 decision values."""
        assert len(Decision) == 3


class TestTradeStatusEnum:
    """Tests for the TradeStatus enum."""

    def test_trade_status_values_exist(self):
        """Test that all expected status values exist."""
        assert TradeStatus.PENDING == "PENDING"
        assert TradeStatus.OPEN == "OPEN"
        assert TradeStatus.CLOSED == "CLOSED"
        assert TradeStatus.CANCELLED == "CANCELLED"

    def test_trade_status_is_string_enum(self):
        """Test that TradeStatus values are strings."""
        assert isinstance(TradeStatus.PENDING.value, str)
        assert isinstance(TradeStatus.OPEN.value, str)
        assert isinstance(TradeStatus.CLOSED.value, str)
        assert isinstance(TradeStatus.CANCELLED.value, str)

    def test_trade_status_count(self):
        """Test that there are exactly 4 status values."""
        assert len(TradeStatus) == 4


class TestGenerateCuid:
    """Tests for the CUID generation function."""

    def test_generates_string(self):
        """Test that generate_cuid returns a string."""
        cuid = generate_cuid()
        assert isinstance(cuid, str)

    def test_starts_with_c(self):
        """Test that generated CUIDs start with 'c'."""
        cuid = generate_cuid()
        assert cuid.startswith("c")

    def test_generates_unique_values(self):
        """Test that each call generates a unique value."""
        cuids = [generate_cuid() for _ in range(100)]
        assert len(set(cuids)) == 100

    def test_reasonable_length(self):
        """Test that generated CUIDs have reasonable length."""
        cuid = generate_cuid()
        assert len(cuid) >= 10


class TestAssetModel:
    """Tests for the Asset model."""

    def test_asset_instantiation(self):
        """Test that Asset can be instantiated with required fields."""
        asset = Asset(
            id="test-id",
            symbol="BTCUSD",
        )
        assert asset.symbol == "BTCUSD"
        assert asset.id == "test-id"

    def test_asset_optional_fields(self):
        """Test that optional fields can be set."""
        asset = Asset(
            id="test-id",
            symbol="ETHUSD",
            name="Ethereum",
            is_active=True,
            last_price=Decimal("3500.00"),
            last_updated=datetime.utcnow(),
        )
        assert asset.name == "Ethereum"
        assert asset.is_active is True
        assert asset.last_price == Decimal("3500.00")
        assert asset.last_updated is not None

    def test_asset_default_values(self):
        """Test that default values are applied."""
        asset = Asset(
            symbol="SOLUSD",
        )
        assert asset.is_active is True
        assert asset.name is None
        assert asset.last_price is None
        assert asset.last_updated is None

    def test_asset_table_name(self):
        """Test that the table name is correctly set."""
        assert Asset.__tablename__ == "Asset"


class TestCandleModel:
    """Tests for the Candle model."""

    def test_candle_instantiation(self):
        """Test that Candle can be instantiated with required fields."""
        candle = Candle(
            id="test-candle-id",
            asset_id="test-asset-id",
            timestamp=datetime.utcnow(),
            timeframe="15m",
            open=Decimal("100.00000000"),
            high=Decimal("105.00000000"),
            low=Decimal("99.00000000"),
            close=Decimal("102.00000000"),
            volume=Decimal("1000000.00000000"),
        )
        assert candle.timeframe == "15m"
        assert candle.open == Decimal("100.00000000")
        assert candle.high == Decimal("105.00000000")
        assert candle.low == Decimal("99.00000000")
        assert candle.close == Decimal("102.00000000")
        assert candle.volume == Decimal("1000000.00000000")

    def test_candle_table_name(self):
        """Test that the table name is correctly set."""
        assert Candle.__tablename__ == "Candle"

    def test_candle_default_timeframe(self):
        """Test that default timeframe is 15m."""
        candle = Candle(
            asset_id="test-asset-id",
            timestamp=datetime.utcnow(),
            open=Decimal("100.00"),
            high=Decimal("105.00"),
            low=Decimal("99.00"),
            close=Decimal("102.00"),
            volume=Decimal("1000000.00"),
        )
        assert candle.timeframe == "15m"


class TestSentimentLogModel:
    """Tests for the SentimentLog model."""

    def test_sentiment_log_instantiation(self):
        """Test that SentimentLog can be instantiated."""
        sentiment = SentimentLog(
            id="test-sentiment-id",
            asset_id="test-asset-id",
            timestamp=datetime.utcnow(),
            source="lunarcrush",
            galaxy_score=75,
            alt_rank=10,
            social_volume=5000,
            sentiment_score=80,
        )
        assert sentiment.source == "lunarcrush"
        assert sentiment.galaxy_score == 75
        assert sentiment.alt_rank == 10
        assert sentiment.social_volume == 5000
        assert sentiment.sentiment_score == 80

    def test_sentiment_log_optional_fields(self):
        """Test that optional fields can be None."""
        sentiment = SentimentLog(
            id="test-sentiment-id",
            asset_id="test-asset-id",
            timestamp=datetime.utcnow(),
            source="bluesky",
        )
        assert sentiment.galaxy_score is None
        assert sentiment.alt_rank is None
        assert sentiment.social_volume is None
        assert sentiment.raw_text is None
        assert sentiment.sentiment_score is None

    def test_sentiment_log_table_name(self):
        """Test that the table name is correctly set."""
        assert SentimentLog.__tablename__ == "SentimentLog"


class TestCouncilSessionModel:
    """Tests for the CouncilSession model."""

    def test_council_session_instantiation(self):
        """Test that CouncilSession can be instantiated."""
        session = CouncilSession(
            id="test-session-id",
            asset_id="test-asset-id",
            timestamp=datetime.utcnow(),
            sentiment_score=75,
            technical_signal="BUY",
            final_decision=Decision.BUY,
            reasoning_log="Market conditions favorable for entry.",
        )
        assert session.sentiment_score == 75
        assert session.technical_signal == "BUY"
        assert session.final_decision == Decision.BUY
        assert "Market conditions" in session.reasoning_log

    def test_council_session_with_technical_details(self):
        """Test that technical_details can store JSON data."""
        technical_data = {
            "rsi": 45.5,
            "sma_20": 50000.0,
            "sma_50": 48000.0,
            "macd": {"value": 100, "signal": 80},
        }
        session = CouncilSession(
            id="test-session-id",
            asset_id="test-asset-id",
            timestamp=datetime.utcnow(),
            sentiment_score=75,
            technical_signal="NEUTRAL",
            technical_details=technical_data,
            final_decision=Decision.HOLD,
            reasoning_log="Technical indicators neutral.",
        )
        assert session.technical_details == technical_data
        assert session.technical_details["rsi"] == 45.5

    def test_council_session_table_name(self):
        """Test that the table name is correctly set."""
        assert CouncilSession.__tablename__ == "CouncilSession"


class TestTradeModel:
    """Tests for the Trade model."""

    def test_trade_instantiation(self):
        """Test that Trade can be instantiated."""
        trade = Trade(
            id="test-trade-id",
            asset_id="test-asset-id",
            status=TradeStatus.PENDING,
            side="BUY",
            entry_price=Decimal("50000.00000000"),
            size=Decimal("0.10000000"),
            entry_time=datetime.utcnow(),
            stop_loss_price=Decimal("48000.00000000"),
        )
        assert trade.status == TradeStatus.PENDING
        assert trade.side == "BUY"
        assert trade.entry_price == Decimal("50000.00000000")
        assert trade.size == Decimal("0.10000000")
        assert trade.stop_loss_price == Decimal("48000.00000000")

    def test_trade_with_optional_fields(self):
        """Test that optional trade fields can be set."""
        entry_time = datetime.utcnow()
        exit_time = datetime.utcnow()
        trade = Trade(
            id="test-trade-id",
            asset_id="test-asset-id",
            status=TradeStatus.CLOSED,
            side="BUY",
            entry_price=Decimal("50000.00000000"),
            size=Decimal("0.10000000"),
            entry_time=entry_time,
            stop_loss_price=Decimal("48000.00000000"),
            take_profit_price=Decimal("55000.00000000"),
            exit_price=Decimal("54000.00000000"),
            exit_time=exit_time,
            pnl=Decimal("400.00000000"),
            pnl_percent=Decimal("8.0000"),
            exit_reason="TAKE_PROFIT",
            kraken_order_id="KRAKEN-ORDER-123",
        )
        assert trade.take_profit_price == Decimal("55000.00000000")
        assert trade.exit_price == Decimal("54000.00000000")
        assert trade.pnl == Decimal("400.00000000")
        assert trade.pnl_percent == Decimal("8.0000")
        assert trade.exit_reason == "TAKE_PROFIT"
        assert trade.kraken_order_id == "KRAKEN-ORDER-123"

    def test_trade_default_values(self):
        """Test that default values are applied."""
        trade = Trade(
            asset_id="test-asset-id",
            entry_price=Decimal("50000.00000000"),
            size=Decimal("0.10000000"),
            entry_time=datetime.utcnow(),
            stop_loss_price=Decimal("48000.00000000"),
        )
        assert trade.status == TradeStatus.PENDING
        assert trade.side == "BUY"

    def test_trade_table_name(self):
        """Test that the table name is correctly set."""
        assert Trade.__tablename__ == "Trade"


class TestDecimalPrecision:
    """Tests for decimal precision in models."""

    def test_price_decimal_precision(self):
        """Test that prices support 18,8 precision."""
        # Large price with 8 decimal places
        price = Decimal("12345678901.12345678")
        asset = Asset(
            symbol="TEST",
            last_price=price,
        )
        assert asset.last_price == price

    def test_volume_decimal_precision(self):
        """Test that volume supports high precision."""
        volume = Decimal("123456789012345.12345678")
        candle = Candle(
            asset_id="test",
            timestamp=datetime.utcnow(),
            open=Decimal("100"),
            high=Decimal("100"),
            low=Decimal("100"),
            close=Decimal("100"),
            volume=volume,
        )
        assert candle.volume == volume

    def test_pnl_percent_precision(self):
        """Test that pnl_percent supports 8,4 precision."""
        percent = Decimal("1234.5678")
        trade = Trade(
            asset_id="test",
            entry_price=Decimal("50000"),
            size=Decimal("0.1"),
            entry_time=datetime.utcnow(),
            stop_loss_price=Decimal("48000"),
            pnl_percent=percent,
        )
        assert trade.pnl_percent == percent

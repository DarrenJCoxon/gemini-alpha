"""
Tests for Story 5.6: On-Chain Data Integration.

Comprehensive unit tests for on-chain data modules:
- config.py (OnChainConfig)
- models/onchain.py (ExchangeFlow, WhaleActivity, FundingRate, StablecoinReserves)
- services/cryptoquant_client.py
- services/onchain_ingestor.py
- services/onchain_analyzer.py
- services/signal_factors.py
- services/factor_checkers.py
"""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock, AsyncMock
import os


# =============================================================================
# Test OnChainConfig
# =============================================================================

class TestOnChainConfig:
    """Tests for OnChainConfig class."""

    def test_onchain_config_defaults(self):
        """Test OnChainConfig with default values."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            onchain_config = config_module.OnChainConfig()
            assert onchain_config.cryptoquant_api_key is None
            assert onchain_config.santiment_api_key is None
            assert onchain_config.glassnode_api_key is None
            assert onchain_config.cache_ttl_minutes == 15
            assert onchain_config.lookback_days == 7
            assert onchain_config.exchange_flow_spike_mult == 2.0
            assert onchain_config.whale_activity_threshold == 100
            assert onchain_config.funding_rate_extreme_threshold == 0.1

    def test_onchain_config_from_env(self):
        """Test OnChainConfig reads from environment."""
        env_vars = {
            "CRYPTOQUANT_API_KEY": "test_cq_key",
            "SANTIMENT_API_KEY": "test_san_key",
            "GLASSNODE_API_KEY": "test_gn_key",
            "ONCHAIN_CACHE_TTL_MINUTES": "30",
            "ONCHAIN_LOOKBACK_DAYS": "14",
            "EXCHANGE_FLOW_SPIKE_MULT": "3.0",
            "WHALE_ACTIVITY_THRESHOLD": "200",
            "FUNDING_RATE_EXTREME_THRESHOLD": "0.2",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            onchain_config = config_module.OnChainConfig()
            assert onchain_config.cryptoquant_api_key == "test_cq_key"
            assert onchain_config.santiment_api_key == "test_san_key"
            assert onchain_config.glassnode_api_key == "test_gn_key"
            assert onchain_config.cache_ttl_minutes == 30
            assert onchain_config.lookback_days == 14
            assert onchain_config.exchange_flow_spike_mult == 3.0
            assert onchain_config.whale_activity_threshold == 200
            assert onchain_config.funding_rate_extreme_threshold == 0.2

    def test_is_configured_false_when_no_keys(self):
        """Test is_configured returns False when no API keys are set."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            onchain_config = config_module.OnChainConfig()
            assert onchain_config.is_configured() is False

    def test_is_configured_true_with_cryptoquant(self):
        """Test is_configured returns True with CryptoQuant key."""
        with patch.dict(os.environ, {"CRYPTOQUANT_API_KEY": "test_key"}, clear=True):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            onchain_config = config_module.OnChainConfig()
            assert onchain_config.is_configured() is True

    def test_is_configured_true_with_santiment(self):
        """Test is_configured returns True with Santiment key."""
        with patch.dict(os.environ, {"SANTIMENT_API_KEY": "test_key"}, clear=True):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            onchain_config = config_module.OnChainConfig()
            assert onchain_config.is_configured() is True

    def test_is_configured_true_with_glassnode(self):
        """Test is_configured returns True with Glassnode key."""
        with patch.dict(os.environ, {"GLASSNODE_API_KEY": "test_key"}, clear=True):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            onchain_config = config_module.OnChainConfig()
            assert onchain_config.is_configured() is True


# =============================================================================
# Test On-Chain Models
# =============================================================================

class TestOnChainModels:
    """Tests for on-chain data models."""

    def test_exchange_flow_model(self):
        """Test ExchangeFlow model creation."""
        from models.onchain import ExchangeFlow

        flow = ExchangeFlow(
            asset_symbol="BTCUSD",
            timestamp=datetime.now(timezone.utc),
            inflow_usd=Decimal("1000000.00"),
            outflow_usd=Decimal("1500000.00"),
            net_flow_usd=Decimal("-500000.00"),
            source="cryptoquant"
        )

        assert flow.asset_symbol == "BTCUSD"
        assert flow.inflow_usd == Decimal("1000000.00")
        assert flow.outflow_usd == Decimal("1500000.00")
        assert flow.net_flow_usd == Decimal("-500000.00")
        assert flow.source == "cryptoquant"
        assert flow.id is not None

    def test_whale_activity_model(self):
        """Test WhaleActivity model creation."""
        from models.onchain import WhaleActivity

        activity = WhaleActivity(
            asset_symbol="ETHUSD",
            timestamp=datetime.now(timezone.utc),
            large_tx_count=50,
            total_whale_volume_usd=Decimal("50000000.00"),
            whale_buy_volume=Decimal("30000000.00"),
            whale_sell_volume=Decimal("20000000.00"),
            source="cryptoquant"
        )

        assert activity.asset_symbol == "ETHUSD"
        assert activity.large_tx_count == 50
        assert activity.total_whale_volume_usd == Decimal("50000000.00")
        assert activity.whale_buy_volume == Decimal("30000000.00")
        assert activity.whale_sell_volume == Decimal("20000000.00")

    def test_funding_rate_model(self):
        """Test FundingRate model creation."""
        from models.onchain import FundingRate

        rate = FundingRate(
            asset_symbol="BTCUSD",
            timestamp=datetime.now(timezone.utc),
            exchange="binance",
            funding_rate=Decimal("0.0001"),
            open_interest_usd=Decimal("5000000000.00"),
            source="cryptoquant"
        )

        assert rate.asset_symbol == "BTCUSD"
        assert rate.exchange == "binance"
        assert rate.funding_rate == Decimal("0.0001")
        assert rate.open_interest_usd == Decimal("5000000000.00")

    def test_stablecoin_reserves_model(self):
        """Test StablecoinReserves model creation."""
        from models.onchain import StablecoinReserves

        reserves = StablecoinReserves(
            timestamp=datetime.now(timezone.utc),
            total_reserves_usd=Decimal("30000000000.00"),
            usdt_reserves=Decimal("20000000000.00"),
            usdc_reserves=Decimal("10000000000.00"),
            change_24h_pct=Decimal("2.5"),
            change_7d_pct=Decimal("5.0"),
            source="cryptoquant"
        )

        assert reserves.total_reserves_usd == Decimal("30000000000.00")
        assert reserves.usdt_reserves == Decimal("20000000000.00")
        assert reserves.usdc_reserves == Decimal("10000000000.00")
        assert reserves.change_24h_pct == Decimal("2.5")
        assert reserves.change_7d_pct == Decimal("5.0")


# =============================================================================
# Test Signal Factors
# =============================================================================

class TestSignalFactors:
    """Tests for signal_factors.py module."""

    def test_buy_factor_enum_values(self):
        """Test BuyFactor enum has correct values."""
        from services.signal_factors import BuyFactor

        assert BuyFactor.ONCHAIN_ACCUMULATION.value == "ONCHAIN_ACCUMULATION"
        assert BuyFactor.FUNDING_SHORT_SQUEEZE.value == "FUNDING_SHORT_SQUEEZE"
        assert BuyFactor.STABLECOIN_DRY_POWDER.value == "STABLECOIN_DRY_POWDER"

    def test_sell_factor_enum_values(self):
        """Test SellFactor enum has correct values."""
        from services.signal_factors import SellFactor

        assert SellFactor.ONCHAIN_DISTRIBUTION.value == "ONCHAIN_DISTRIBUTION"
        assert SellFactor.FUNDING_LONG_SQUEEZE.value == "FUNDING_LONG_SQUEEZE"

    def test_factor_result_dataclass(self):
        """Test FactorResult dataclass."""
        from services.signal_factors import FactorResult

        result = FactorResult(
            factor="TEST_FACTOR",
            triggered=True,
            value=75.0,
            threshold=50.0,
            weight=1.5,
            reasoning="Test reasoning"
        )

        assert result.factor == "TEST_FACTOR"
        assert result.triggered is True
        assert result.value == 75.0
        assert result.threshold == 50.0
        assert result.weight == 1.5
        assert result.reasoning == "Test reasoning"

    def test_factor_weights_onchain(self):
        """Test on-chain factor weights are configured."""
        from services.signal_factors import FACTOR_WEIGHTS, BuyFactor, SellFactor

        assert BuyFactor.ONCHAIN_ACCUMULATION.value in FACTOR_WEIGHTS
        assert FACTOR_WEIGHTS[BuyFactor.ONCHAIN_ACCUMULATION.value] == 1.5

        assert SellFactor.ONCHAIN_DISTRIBUTION.value in FACTOR_WEIGHTS
        assert FACTOR_WEIGHTS[SellFactor.ONCHAIN_DISTRIBUTION.value] == 1.5

    def test_get_factor_weight(self):
        """Test get_factor_weight function."""
        from services.signal_factors import get_factor_weight, BuyFactor

        weight = get_factor_weight(BuyFactor.ONCHAIN_ACCUMULATION.value)
        assert weight == 1.5

        # Unknown factor should return 1.0
        weight = get_factor_weight("UNKNOWN_FACTOR")
        assert weight == 1.0

    def test_calculate_multi_factor_score_buy(self):
        """Test multi-factor scoring for buy signal."""
        from services.signal_factors import (
            calculate_multi_factor_score,
            FactorResult
        )

        buy_factors = [
            FactorResult("F1", True, 80, 50, 1.0, ""),
            FactorResult("F2", True, 90, 50, 1.5, ""),
            FactorResult("F3", False, 30, 50, 1.0, ""),
        ]
        sell_factors = [
            FactorResult("F4", False, 20, 50, 1.0, ""),
        ]

        result = calculate_multi_factor_score(buy_factors, sell_factors)

        assert result.signal == "BUY"
        assert result.buy_score == 2.5  # 1.0 + 1.5
        assert result.sell_score == 0.0
        assert result.confidence > 0

    def test_calculate_multi_factor_score_sell(self):
        """Test multi-factor scoring for sell signal."""
        from services.signal_factors import (
            calculate_multi_factor_score,
            FactorResult
        )

        buy_factors = [
            FactorResult("F1", False, 30, 50, 1.0, ""),
        ]
        sell_factors = [
            FactorResult("F2", True, 80, 50, 1.5, ""),
            FactorResult("F3", True, 90, 50, 1.0, ""),
        ]

        result = calculate_multi_factor_score(buy_factors, sell_factors)

        assert result.signal == "SELL"
        assert result.sell_score == 2.5  # 1.5 + 1.0
        assert result.buy_score == 0.0

    def test_calculate_multi_factor_score_hold(self):
        """Test multi-factor scoring for hold signal."""
        from services.signal_factors import (
            calculate_multi_factor_score,
            FactorResult
        )

        buy_factors = [
            FactorResult("F1", True, 60, 50, 1.0, ""),
        ]
        sell_factors = [
            FactorResult("F2", True, 60, 50, 1.0, ""),
        ]

        result = calculate_multi_factor_score(buy_factors, sell_factors)

        assert result.signal == "HOLD"
        assert result.buy_score == 1.0
        assert result.sell_score == 1.0


# =============================================================================
# Test On-Chain Signal Enum
# =============================================================================

class TestOnChainSignal:
    """Tests for OnChainSignal enum."""

    def test_onchain_signal_values(self):
        """Test OnChainSignal enum values."""
        from services.onchain_analyzer import OnChainSignal

        assert OnChainSignal.STRONG_ACCUMULATION.value == "STRONG_ACCUMULATION"
        assert OnChainSignal.ACCUMULATION.value == "ACCUMULATION"
        assert OnChainSignal.NEUTRAL.value == "NEUTRAL"
        assert OnChainSignal.DISTRIBUTION.value == "DISTRIBUTION"
        assert OnChainSignal.STRONG_DISTRIBUTION.value == "STRONG_DISTRIBUTION"

    def test_onchain_signal_is_string_enum(self):
        """Test OnChainSignal is a string enum."""
        from services.onchain_analyzer import OnChainSignal

        assert isinstance(OnChainSignal.NEUTRAL, str)
        assert OnChainSignal.NEUTRAL == "NEUTRAL"


# =============================================================================
# Test OnChainAnalysis Dataclass
# =============================================================================

class TestOnChainAnalysis:
    """Tests for OnChainAnalysis dataclass."""

    def test_onchain_analysis_creation(self):
        """Test OnChainAnalysis dataclass creation."""
        from services.onchain_analyzer import OnChainAnalysis, OnChainSignal

        analysis = OnChainAnalysis(
            signal=OnChainSignal.ACCUMULATION,
            confidence=75.0,
            net_flow_signal="accumulation",
            net_flow_value_usd=Decimal("-500000"),
            net_flow_vs_avg=1.5,
            whale_signal="buying",
            whale_buy_sell_ratio=1.8,
            whale_activity_level="high",
            funding_signal="neutral",
            avg_funding_rate=Decimal("0.0001"),
            funding_extreme=False,
            stablecoin_signal="neutral",
            reserves_change_7d_pct=3.5,
            reasoning="Test reasoning",
            factors=["Factor 1", "Factor 2"]
        )

        assert analysis.signal == OnChainSignal.ACCUMULATION
        assert analysis.confidence == 75.0
        assert analysis.net_flow_signal == "accumulation"
        assert analysis.whale_signal == "buying"
        assert len(analysis.factors) == 2


# =============================================================================
# Test CryptoQuant Client
# =============================================================================

class TestCryptoQuantClient:
    """Tests for CryptoQuantClient."""

    def test_client_raises_without_api_key(self):
        """Test client raises ValueError without API key."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            from services.cryptoquant_client import CryptoQuantClient
            with pytest.raises(ValueError, match="CRYPTOQUANT_API_KEY not configured"):
                CryptoQuantClient()

    def test_client_init_with_api_key(self):
        """Test client initializes with API key."""
        with patch.dict(os.environ, {"CRYPTOQUANT_API_KEY": "test_key"}, clear=True):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            from services.cryptoquant_client import CryptoQuantClient
            client = CryptoQuantClient()

            assert client.api_key == "test_key"
            assert client.client is not None

    def test_client_parse_datetime_iso(self):
        """Test datetime parsing with ISO format."""
        with patch.dict(os.environ, {"CRYPTOQUANT_API_KEY": "test_key"}, clear=True):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            from services.cryptoquant_client import CryptoQuantClient
            client = CryptoQuantClient()

            # ISO format
            result = client._parse_datetime("2024-01-15T10:30:00Z")
            assert isinstance(result, datetime)

    def test_client_parse_datetime_none(self):
        """Test datetime parsing with None returns current time."""
        with patch.dict(os.environ, {"CRYPTOQUANT_API_KEY": "test_key"}, clear=True):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            from services.cryptoquant_client import CryptoQuantClient
            client = CryptoQuantClient()

            result = client._parse_datetime(None)
            assert isinstance(result, datetime)


# =============================================================================
# Test On-Chain Ingestor
# =============================================================================

class TestOnChainIngestor:
    """Tests for OnChainIngestor."""

    def test_symbol_mapping_btc(self):
        """Test symbol mapping for BTC."""
        from services.onchain_ingestor import OnChainIngestor

        ingestor = OnChainIngestor()

        assert ingestor._map_symbol("BTCUSD") == "btc"
        assert ingestor._map_symbol("XBTUSD") == "btc"
        assert ingestor._map_symbol("BTC") == "btc"

    def test_symbol_mapping_eth(self):
        """Test symbol mapping for ETH."""
        from services.onchain_ingestor import OnChainIngestor

        ingestor = OnChainIngestor()

        assert ingestor._map_symbol("ETHUSD") == "eth"
        assert ingestor._map_symbol("ETH") == "eth"

    def test_symbol_mapping_unknown(self):
        """Test symbol mapping for unknown symbol."""
        from services.onchain_ingestor import OnChainIngestor

        ingestor = OnChainIngestor()

        assert ingestor._map_symbol("UNKNOWNUSD") is None
        assert ingestor._map_symbol("RANDOM") is None

    @pytest.mark.asyncio
    async def test_ingestor_not_initialized_returns_zero(self):
        """Test ingestor returns 0 when not initialized."""
        from services.onchain_ingestor import OnChainIngestor

        ingestor = OnChainIngestor()
        # Don't initialize - client will be None

        count = await ingestor.ingest_exchange_flows(["BTCUSD"])
        assert count == 0

        count = await ingestor.ingest_whale_activity(["BTCUSD"])
        assert count == 0

        count = await ingestor.ingest_funding_rates(["BTCUSD"])
        assert count == 0

        count = await ingestor.ingest_stablecoin_reserves()
        assert count == 0


# =============================================================================
# Test Factor Checkers
# =============================================================================

class TestFactorCheckers:
    """Tests for factor_checkers.py module."""

    @pytest.mark.asyncio
    async def test_check_onchain_accumulation_returns_factor_result(self):
        """Test check_onchain_accumulation returns FactorResult."""
        from services.factor_checkers import check_onchain_accumulation
        from services.signal_factors import FactorResult, BuyFactor

        # Mock the get_onchain_analysis function
        with patch('services.factor_checkers.get_onchain_analysis') as mock_analysis:
            from services.onchain_analyzer import OnChainSignal, OnChainAnalysis

            mock_analysis.return_value = OnChainAnalysis(
                signal=OnChainSignal.ACCUMULATION,
                confidence=75.0,
                net_flow_signal="accumulation",
                net_flow_value_usd=Decimal("-500000"),
                net_flow_vs_avg=1.5,
                whale_signal="buying",
                whale_buy_sell_ratio=1.5,
                whale_activity_level="high",
                funding_signal="neutral",
                avg_funding_rate=Decimal("0.0001"),
                funding_extreme=False,
                stablecoin_signal="neutral",
                reserves_change_7d_pct=3.5,
                reasoning="Test reasoning",
                factors=[]
            )

            result = await check_onchain_accumulation("BTCUSD")

            assert isinstance(result, FactorResult)
            assert result.factor == BuyFactor.ONCHAIN_ACCUMULATION.value
            assert result.triggered is True

    @pytest.mark.asyncio
    async def test_check_onchain_distribution_returns_factor_result(self):
        """Test check_onchain_distribution returns FactorResult."""
        from services.factor_checkers import check_onchain_distribution
        from services.signal_factors import FactorResult, SellFactor

        with patch('services.factor_checkers.get_onchain_analysis') as mock_analysis:
            from services.onchain_analyzer import OnChainSignal, OnChainAnalysis

            mock_analysis.return_value = OnChainAnalysis(
                signal=OnChainSignal.DISTRIBUTION,
                confidence=70.0,
                net_flow_signal="distribution",
                net_flow_value_usd=Decimal("500000"),
                net_flow_vs_avg=-1.5,
                whale_signal="selling",
                whale_buy_sell_ratio=0.5,
                whale_activity_level="high",
                funding_signal="neutral",
                avg_funding_rate=Decimal("0.0001"),
                funding_extreme=False,
                stablecoin_signal="neutral",
                reserves_change_7d_pct=-3.5,
                reasoning="Test reasoning",
                factors=[]
            )

            result = await check_onchain_distribution("BTCUSD")

            assert isinstance(result, FactorResult)
            assert result.factor == SellFactor.ONCHAIN_DISTRIBUTION.value
            assert result.triggered is True

    @pytest.mark.asyncio
    async def test_check_funding_short_squeeze(self):
        """Test check_funding_short_squeeze detects squeeze risk."""
        from services.factor_checkers import check_funding_short_squeeze
        from services.signal_factors import FactorResult, BuyFactor

        with patch('services.factor_checkers.get_onchain_analysis') as mock_analysis:
            from services.onchain_analyzer import OnChainSignal, OnChainAnalysis

            mock_analysis.return_value = OnChainAnalysis(
                signal=OnChainSignal.NEUTRAL,
                confidence=60.0,
                net_flow_signal="neutral",
                net_flow_value_usd=Decimal("0"),
                net_flow_vs_avg=0,
                whale_signal="neutral",
                whale_buy_sell_ratio=1.0,
                whale_activity_level="normal",
                funding_signal="short_squeeze_risk",
                avg_funding_rate=Decimal("-0.15"),
                funding_extreme=True,
                stablecoin_signal="neutral",
                reserves_change_7d_pct=0,
                reasoning="Test reasoning",
                factors=[]
            )

            result = await check_funding_short_squeeze("BTCUSD")

            assert isinstance(result, FactorResult)
            assert result.factor == BuyFactor.FUNDING_SHORT_SQUEEZE.value
            assert result.triggered is True

    @pytest.mark.asyncio
    async def test_check_funding_long_squeeze(self):
        """Test check_funding_long_squeeze detects squeeze risk."""
        from services.factor_checkers import check_funding_long_squeeze
        from services.signal_factors import FactorResult, SellFactor

        with patch('services.factor_checkers.get_onchain_analysis') as mock_analysis:
            from services.onchain_analyzer import OnChainSignal, OnChainAnalysis

            mock_analysis.return_value = OnChainAnalysis(
                signal=OnChainSignal.NEUTRAL,
                confidence=60.0,
                net_flow_signal="neutral",
                net_flow_value_usd=Decimal("0"),
                net_flow_vs_avg=0,
                whale_signal="neutral",
                whale_buy_sell_ratio=1.0,
                whale_activity_level="normal",
                funding_signal="long_squeeze_risk",
                avg_funding_rate=Decimal("0.15"),
                funding_extreme=True,
                stablecoin_signal="neutral",
                reserves_change_7d_pct=0,
                reasoning="Test reasoning",
                factors=[]
            )

            result = await check_funding_long_squeeze("BTCUSD")

            assert isinstance(result, FactorResult)
            assert result.factor == SellFactor.FUNDING_LONG_SQUEEZE.value
            assert result.triggered is True

    @pytest.mark.asyncio
    async def test_get_all_onchain_factors(self):
        """Test get_all_onchain_factors returns buy and sell factors."""
        from services.factor_checkers import get_all_onchain_factors

        with patch('services.factor_checkers.get_onchain_analysis') as mock_analysis:
            from services.onchain_analyzer import OnChainSignal, OnChainAnalysis

            mock_analysis.return_value = OnChainAnalysis(
                signal=OnChainSignal.NEUTRAL,
                confidence=50.0,
                net_flow_signal="neutral",
                net_flow_value_usd=Decimal("0"),
                net_flow_vs_avg=0,
                whale_signal="neutral",
                whale_buy_sell_ratio=1.0,
                whale_activity_level="normal",
                funding_signal="neutral",
                avg_funding_rate=Decimal("0.0001"),
                funding_extreme=False,
                stablecoin_signal="neutral",
                reserves_change_7d_pct=0,
                reasoning="Test reasoning",
                factors=[]
            )

            buy_factors, sell_factors = await get_all_onchain_factors("BTCUSD")

            assert len(buy_factors) == 3  # accumulation, short squeeze, stablecoin
            assert len(sell_factors) == 2  # distribution, long squeeze


# =============================================================================
# Integration Tests
# =============================================================================

class TestOnChainIntegration:
    """Integration tests for on-chain module."""

    def test_config_integration_with_main_config(self):
        """Test OnChainConfig integrates with main Config."""
        with patch.dict(os.environ, {"CRYPTOQUANT_API_KEY": "test_key"}, clear=True):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            main_config = config_module.Config()

            assert hasattr(main_config, 'onchain')
            assert main_config.onchain.cryptoquant_api_key == "test_key"
            assert main_config.onchain.is_configured() is True

    def test_all_onchain_factors_in_factor_weights(self):
        """Test all on-chain factors are in FACTOR_WEIGHTS."""
        from services.signal_factors import (
            FACTOR_WEIGHTS,
            BuyFactor,
            SellFactor
        )

        # Buy factors
        assert BuyFactor.ONCHAIN_ACCUMULATION.value in FACTOR_WEIGHTS
        assert BuyFactor.FUNDING_SHORT_SQUEEZE.value in FACTOR_WEIGHTS
        assert BuyFactor.STABLECOIN_DRY_POWDER.value in FACTOR_WEIGHTS

        # Sell factors
        assert SellFactor.ONCHAIN_DISTRIBUTION.value in FACTOR_WEIGHTS
        assert SellFactor.FUNDING_LONG_SQUEEZE.value in FACTOR_WEIGHTS


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_factor_checker_handles_exception(self):
        """Test factor checker handles exceptions gracefully."""
        from services.factor_checkers import check_onchain_accumulation
        from services.signal_factors import FactorResult

        with patch('services.factor_checkers.get_onchain_analysis') as mock_analysis:
            mock_analysis.side_effect = Exception("Test error")

            result = await check_onchain_accumulation("BTCUSD")

            assert isinstance(result, FactorResult)
            assert result.triggered is False
            assert "Error" in result.reasoning

    def test_model_with_none_optional_fields(self):
        """Test models work with None optional fields."""
        from models.onchain import ExchangeFlow, WhaleActivity, FundingRate, StablecoinReserves

        # ExchangeFlow with None avg
        flow = ExchangeFlow(
            asset_symbol="BTCUSD",
            timestamp=datetime.now(timezone.utc),
            inflow_usd=Decimal("1000.00"),
            outflow_usd=Decimal("2000.00"),
            net_flow_usd=Decimal("-1000.00"),
            avg_net_flow_7d=None,
            source="test"
        )
        assert flow.avg_net_flow_7d is None

        # WhaleActivity with None volumes
        activity = WhaleActivity(
            asset_symbol="BTCUSD",
            timestamp=datetime.now(timezone.utc),
            large_tx_count=10,
            total_whale_volume_usd=Decimal("1000000.00"),
            whale_buy_volume=None,
            whale_sell_volume=None,
            source="test"
        )
        assert activity.whale_buy_volume is None

    def test_multi_factor_score_empty_lists(self):
        """Test multi-factor scoring with empty lists."""
        from services.signal_factors import calculate_multi_factor_score

        result = calculate_multi_factor_score([], [])

        assert result.signal == "HOLD"
        assert result.buy_score == 0.0
        assert result.sell_score == 0.0
        assert result.confidence == 0.0


# =============================================================================
# Scheduler Integration
# =============================================================================

class TestSchedulerIntegration:
    """Tests for scheduler integration."""

    def test_run_onchain_ingestion_function_exists(self):
        """Test run_onchain_ingestion function exists in scheduler."""
        from services.scheduler import run_onchain_ingestion

        assert callable(run_onchain_ingestion)

    @pytest.mark.asyncio
    async def test_run_onchain_ingestion_skips_when_not_configured(self):
        """Test on-chain ingestion skips when not configured."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            from services.scheduler import run_onchain_ingestion

            result = await run_onchain_ingestion()

            assert result.get("skipped") is True
            assert "Not configured" in result.get("reason", "")

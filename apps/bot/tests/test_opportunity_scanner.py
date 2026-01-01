"""
Tests for services/opportunity_scanner.py - Dynamic Opportunity Scanner.

Story 5.8: Dynamic Opportunity Scanner - Integration tests for the scanner
orchestrator, volume filtering, symbol conversion, and dynamic universe.
"""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch


class TestOpportunityScanner:
    """Tests for OpportunityScanner class."""

    @pytest.fixture
    def mock_tickers(self):
        """Mock ticker data."""
        return {
            "BTC/USD": {"symbol": "BTC/USD", "last": 42000, "quoteVolume": 500000000},
            "ETH/USD": {"symbol": "ETH/USD", "last": 2200, "quoteVolume": 200000000},
            "SOL/USD": {"symbol": "SOL/USD", "last": 100, "quoteVolume": 50000000},
            "SMALL/USD": {"symbol": "SMALL/USD", "last": 0.01, "quoteVolume": 100000},
        }

    @pytest.fixture
    def mock_candles(self):
        """Mock OHLCV candles."""
        return [
            {
                "timestamp": datetime.utcnow() - timedelta(hours=i * 4),
                "open": Decimal("100") - Decimal(str(i)),
                "high": Decimal("102") - Decimal(str(i)),
                "low": Decimal("98") - Decimal(str(i)),
                "close": Decimal("99") - Decimal(str(i)),
                "volume": Decimal("1000000")
            }
            for i in range(50)
        ]

    def test_scanner_filters_by_volume(self, mock_tickers):
        """Scanner should filter out low volume pairs."""
        from services.opportunity_scanner import OpportunityScanner

        scanner = OpportunityScanner()

        filtered = scanner._filter_by_volume(mock_tickers)

        # SMALL/USD should be filtered out (< $1M volume)
        assert "SMALL/USD" not in filtered
        assert "BTC/USD" in filtered
        assert "ETH/USD" in filtered
        assert "SOL/USD" in filtered

    def test_scanner_filters_all_low_volume(self):
        """Scanner should filter all pairs when none meet volume threshold."""
        from services.opportunity_scanner import OpportunityScanner

        tickers = {
            "TINY1/USD": {"symbol": "TINY1/USD", "last": 0.001, "quoteVolume": 50000},
            "TINY2/USD": {"symbol": "TINY2/USD", "last": 0.002, "quoteVolume": 75000},
        }

        scanner = OpportunityScanner()
        filtered = scanner._filter_by_volume(tickers)

        assert len(filtered) == 0

    def test_scanner_converts_symbols_standard(self):
        """Scanner should convert ccxt symbols to database format."""
        from services.opportunity_scanner import OpportunityScanner

        scanner = OpportunityScanner()

        assert scanner._convert_to_db_symbol("BTC/USD") == "BTCUSD"
        assert scanner._convert_to_db_symbol("ETH/USD") == "ETHUSD"
        assert scanner._convert_to_db_symbol("SOL/USD") == "SOLUSD"

    def test_scanner_converts_xbt_to_btc(self):
        """Scanner should convert XBT to BTC for Kraken compatibility."""
        from services.opportunity_scanner import OpportunityScanner

        scanner = OpportunityScanner()

        assert scanner._convert_to_db_symbol("XBT/USD") == "BTCUSD"

    def test_scanner_converts_candles_for_scoring(self, mock_candles):
        """Scanner should convert candle Decimals to floats for scoring."""
        from services.opportunity_scanner import OpportunityScanner

        scanner = OpportunityScanner()
        converted = scanner._convert_candles_for_scoring(mock_candles)

        assert len(converted) == 50
        assert isinstance(converted[0]["close"], float)
        assert isinstance(converted[0]["volume"], float)

    def test_scanner_create_error_result(self):
        """Scanner should create proper error result structure."""
        from services.opportunity_scanner import OpportunityScanner

        scanner = OpportunityScanner()
        start_time = datetime.now(timezone.utc)
        errors = ["Test error 1", "Test error 2"]

        result = scanner._create_error_result(start_time, errors)

        assert result.timestamp == start_time
        assert result.total_pairs_scanned == 0
        assert result.opportunities_found == 0
        assert result.errors == errors

    def test_get_dynamic_universe_returns_copy(self):
        """get_dynamic_universe should return a copy of the universe list."""
        from services.opportunity_scanner import OpportunityScanner

        scanner = OpportunityScanner()
        scanner._dynamic_universe = ["BTCUSD", "ETHUSD"]

        universe = scanner.get_dynamic_universe()

        # Should be a copy, not the original
        assert universe == ["BTCUSD", "ETHUSD"]
        universe.append("SOLUSD")
        assert scanner._dynamic_universe == ["BTCUSD", "ETHUSD"]

    def test_get_last_scan_result_initially_none(self):
        """get_last_scan_result should return None before any scan."""
        from services.opportunity_scanner import OpportunityScanner

        scanner = OpportunityScanner()

        assert scanner.get_last_scan_result() is None


class TestDynamicTradingUniverse:
    """Tests for get_dynamic_trading_universe function."""

    def test_dynamic_universe_fallback(self):
        """Should fall back to static config when scanner has no results."""
        import services.opportunity_scanner as scanner_module

        # Reset global scanner
        scanner_module._scanner = None

        from services.opportunity_scanner import (
            get_dynamic_trading_universe,
            get_opportunity_scanner,
        )

        # Get scanner and ensure empty universe
        scanner = get_opportunity_scanner()
        scanner._dynamic_universe = []

        with patch('services.asset_universe.get_full_asset_universe') as mock_static:
            mock_static.return_value = ["BTCUSD", "ETHUSD"]

            universe = get_dynamic_trading_universe()

            assert universe == ["BTCUSD", "ETHUSD"]
            mock_static.assert_called_once()

    def test_dynamic_universe_returns_scanner_results(self):
        """Should return scanner results when available."""
        import services.opportunity_scanner as scanner_module

        # Reset global scanner
        scanner_module._scanner = None

        from services.opportunity_scanner import (
            get_dynamic_trading_universe,
            get_opportunity_scanner,
        )

        # Set up scanner with results
        scanner = get_opportunity_scanner()
        scanner._dynamic_universe = ["SOLUSD", "AVAXUSD", "LINKUSD"]

        with patch('services.asset_universe.get_full_asset_universe') as mock_static:
            universe = get_dynamic_trading_universe()

            assert universe == ["SOLUSD", "AVAXUSD", "LINKUSD"]
            mock_static.assert_not_called()


class TestScanResult:
    """Tests for ScanResult dataclass."""

    def test_scan_result_creation(self):
        """Test ScanResult can be created with all fields."""
        from services.opportunity_scanner import ScanResult

        result = ScanResult(
            timestamp=datetime.now(timezone.utc),
            total_pairs_scanned=613,
            pairs_after_volume_filter=60,
            pairs_scored=50,
            opportunities_found=8,
            top_opportunities=[],
            scan_duration_seconds=25.5,
            errors=[]
        )

        assert result.total_pairs_scanned == 613
        assert result.pairs_after_volume_filter == 60
        assert result.opportunities_found == 8
        assert result.scan_duration_seconds == 25.5


class TestScannerDisabled:
    """Tests for scanner disabled state."""

    @pytest.mark.asyncio
    async def test_run_scan_when_disabled(self):
        """Scanner should return early when disabled."""
        from services.opportunity_scanner import OpportunityScanner

        with patch('services.opportunity_scanner.get_config') as mock_config:
            # Set up mock config with scanner disabled
            mock_scanner_config = MagicMock()
            mock_scanner_config.enabled = False
            mock_config.return_value.scanner = mock_scanner_config

            scanner = OpportunityScanner()
            result = await scanner.run_scan()

            assert result.total_pairs_scanned == 0
            assert "Scanner disabled" in result.errors


class TestVolumeFilter:
    """Tests for volume filtering logic."""

    def test_volume_filter_with_none_values(self):
        """Volume filter should handle None quoteVolume values."""
        from services.opportunity_scanner import OpportunityScanner

        tickers = {
            "GOOD/USD": {"symbol": "GOOD/USD", "last": 100, "quoteVolume": 5000000},
            "NONE/USD": {"symbol": "NONE/USD", "last": 100, "quoteVolume": None},
            "ZERO/USD": {"symbol": "ZERO/USD", "last": 100, "quoteVolume": 0},
        }

        scanner = OpportunityScanner()
        filtered = scanner._filter_by_volume(tickers)

        assert "GOOD/USD" in filtered
        assert "NONE/USD" not in filtered
        assert "ZERO/USD" not in filtered

    def test_volume_filter_edge_case_at_threshold(self):
        """Volume filter should include pairs at exactly the threshold."""
        from services.opportunity_scanner import OpportunityScanner

        tickers = {
            "EXACT/USD": {"symbol": "EXACT/USD", "last": 100, "quoteVolume": 1000000},
            "BELOW/USD": {"symbol": "BELOW/USD", "last": 100, "quoteVolume": 999999},
        }

        scanner = OpportunityScanner()
        filtered = scanner._filter_by_volume(tickers)

        assert "EXACT/USD" in filtered
        assert "BELOW/USD" not in filtered


class TestGlobalScanner:
    """Tests for global scanner instance functions."""

    def test_get_opportunity_scanner_singleton(self):
        """get_opportunity_scanner should return the same instance."""
        # Clear the global scanner first
        import services.opportunity_scanner as scanner_module
        scanner_module._scanner = None

        from services.opportunity_scanner import get_opportunity_scanner

        scanner1 = get_opportunity_scanner()
        scanner2 = get_opportunity_scanner()

        assert scanner1 is scanner2

    @pytest.mark.asyncio
    async def test_run_opportunity_scan_uses_global_scanner(self):
        """run_opportunity_scan should use the global scanner instance."""
        import services.opportunity_scanner as scanner_module

        # Reset global scanner
        scanner_module._scanner = None

        # Create a mock scanner with disabled config
        mock_scanner = MagicMock()
        mock_scanner.run_scan = AsyncMock()

        # Create expected result
        from services.opportunity_scanner import ScanResult
        expected_result = ScanResult(
            timestamp=datetime.now(timezone.utc),
            total_pairs_scanned=0,
            pairs_after_volume_filter=0,
            pairs_scored=0,
            opportunities_found=0,
            top_opportunities=[],
            scan_duration_seconds=0,
            errors=["Scanner disabled"]
        )
        mock_scanner.run_scan.return_value = expected_result

        # Patch at module level
        with patch.object(scanner_module, 'get_opportunity_scanner', return_value=mock_scanner):
            from services.opportunity_scanner import run_opportunity_scan
            result = await run_opportunity_scan()

            assert result is not None
            assert "Scanner disabled" in result.errors


class TestCandleConversion:
    """Tests for candle data conversion."""

    def test_convert_candles_handles_empty_list(self):
        """Candle conversion should handle empty list."""
        from services.opportunity_scanner import OpportunityScanner

        scanner = OpportunityScanner()
        converted = scanner._convert_candles_for_scoring([])

        assert converted == []

    def test_convert_candles_handles_missing_fields(self):
        """Candle conversion should handle missing fields gracefully."""
        from services.opportunity_scanner import OpportunityScanner

        candles = [{"timestamp": datetime.utcnow()}]  # Missing price/volume

        scanner = OpportunityScanner()
        converted = scanner._convert_candles_for_scoring(candles)

        assert len(converted) == 1
        assert converted[0]["close"] == 0.0
        assert converted[0]["volume"] == 0.0

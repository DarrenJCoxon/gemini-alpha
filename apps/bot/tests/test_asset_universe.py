"""
Tests for asset_universe.py - Asset Universe Configuration.

Story 5.2: Asset Universe Reduction

Tests cover:
- Tier assignment for known assets
- Excluded asset detection
- Unknown asset handling
- Asset universe size validation
- Tier configuration retrieval
- Allocation percentage calculations
"""

import os
import pytest
from decimal import Decimal
from unittest.mock import patch

from services.asset_universe import (
    AssetTier,
    TierConfig,
    DEFAULT_TIER_CONFIG,
    EXCLUDED_ASSETS,
    EXCLUSION_REASONS,
    get_tier_3_assets,
    get_full_asset_universe,
    get_asset_tier,
    get_max_allocation,
    get_tier_config,
    get_exclusion_reason,
    is_tradeable,
)


class TestAssetTier:
    """Tests for AssetTier enum."""

    def test_tier_enum_values(self):
        """Test AssetTier enum has correct values."""
        assert AssetTier.TIER_1.value == "TIER_1"
        assert AssetTier.TIER_2.value == "TIER_2"
        assert AssetTier.TIER_3.value == "TIER_3"
        assert AssetTier.EXCLUDED.value == "EXCLUDED"

    def test_tier_is_string_enum(self):
        """Test AssetTier is a string enum."""
        assert isinstance(AssetTier.TIER_1, str)
        assert AssetTier.TIER_1 == "TIER_1"


class TestTierConfig:
    """Tests for TierConfig dataclass."""

    def test_tier_config_creation(self):
        """Test TierConfig can be created with values."""
        config = TierConfig(
            max_allocation_percent=Decimal("50.0"),
            min_volume_24h=Decimal("1000000"),
            min_market_cap=Decimal("10000000"),
            assets=["TESTASSET"],
        )
        assert config.max_allocation_percent == Decimal("50.0")
        assert config.min_volume_24h == Decimal("1000000")
        assert config.min_market_cap == Decimal("10000000")
        assert config.assets == ["TESTASSET"]


class TestDefaultTierConfig:
    """Tests for DEFAULT_TIER_CONFIG."""

    def test_tier_1_config(self):
        """Test Tier 1 configuration."""
        config = DEFAULT_TIER_CONFIG[AssetTier.TIER_1]
        assert config.max_allocation_percent == Decimal("60.0")
        assert config.min_volume_24h == Decimal("1000000000")  # $1B
        assert config.min_market_cap == Decimal("50000000000")  # $50B
        assert "BTCUSD" in config.assets
        assert "ETHUSD" in config.assets

    def test_tier_2_config(self):
        """Test Tier 2 configuration."""
        config = DEFAULT_TIER_CONFIG[AssetTier.TIER_2]
        assert config.max_allocation_percent == Decimal("30.0")
        assert config.min_volume_24h == Decimal("100000000")  # $100M
        assert config.min_market_cap == Decimal("5000000000")  # $5B
        assert "SOLUSD" in config.assets
        assert "AVAXUSD" in config.assets
        assert "LINKUSD" in config.assets

    def test_tier_3_config(self):
        """Test Tier 3 configuration."""
        config = DEFAULT_TIER_CONFIG[AssetTier.TIER_3]
        assert config.max_allocation_percent == Decimal("10.0")
        assert config.min_volume_24h == Decimal("50000000")  # $50M
        assert config.min_market_cap == Decimal("1000000000")  # $1B
        # Tier 3 assets come from environment, default is empty
        assert config.assets == []


class TestTier1Assets:
    """Tests for Tier 1 asset classification."""

    def test_btc_is_tier_1(self):
        """Test BTC is correctly identified as Tier 1."""
        assert get_asset_tier("BTCUSD") == AssetTier.TIER_1

    def test_eth_is_tier_1(self):
        """Test ETH is correctly identified as Tier 1."""
        assert get_asset_tier("ETHUSD") == AssetTier.TIER_1

    def test_tier_1_case_insensitive(self):
        """Test tier lookup is case insensitive."""
        assert get_asset_tier("btcusd") == AssetTier.TIER_1
        assert get_asset_tier("BtCuSd") == AssetTier.TIER_1


class TestTier2Assets:
    """Tests for Tier 2 asset classification."""

    def test_sol_is_tier_2(self):
        """Test SOL is correctly identified as Tier 2."""
        assert get_asset_tier("SOLUSD") == AssetTier.TIER_2

    def test_avax_is_tier_2(self):
        """Test AVAX is correctly identified as Tier 2."""
        assert get_asset_tier("AVAXUSD") == AssetTier.TIER_2

    def test_link_is_tier_2(self):
        """Test LINK is correctly identified as Tier 2."""
        assert get_asset_tier("LINKUSD") == AssetTier.TIER_2


class TestTier3Assets:
    """Tests for Tier 3 asset configuration."""

    def test_tier_3_from_env_empty(self):
        """Test Tier 3 returns empty list when not configured."""
        with patch.dict(os.environ, {"TIER_3_ASSETS": ""}, clear=False):
            assets = get_tier_3_assets()
            assert assets == []

    def test_tier_3_from_env_single(self):
        """Test Tier 3 with single asset."""
        with patch.dict(os.environ, {"TIER_3_ASSETS": "AAVEUSD"}, clear=False):
            assets = get_tier_3_assets()
            assert assets == ["AAVEUSD"]

    def test_tier_3_from_env_multiple(self):
        """Test Tier 3 with multiple assets."""
        with patch.dict(os.environ, {"TIER_3_ASSETS": "AAVEUSD,UNIUSD,ARBUSD"}, clear=False):
            assets = get_tier_3_assets()
            assert assets == ["AAVEUSD", "UNIUSD", "ARBUSD"]

    def test_tier_3_with_whitespace(self):
        """Test Tier 3 handles whitespace in config."""
        with patch.dict(os.environ, {"TIER_3_ASSETS": " AAVEUSD , UNIUSD "}, clear=False):
            assets = get_tier_3_assets()
            assert assets == ["AAVEUSD", "UNIUSD"]

    def test_tier_3_uppercases_assets(self):
        """Test Tier 3 assets are uppercased."""
        with patch.dict(os.environ, {"TIER_3_ASSETS": "aaveusd,uniusd"}, clear=False):
            assets = get_tier_3_assets()
            assert assets == ["AAVEUSD", "UNIUSD"]

    def test_tier_3_asset_is_tier_3(self):
        """Test configured Tier 3 asset is identified correctly."""
        with patch.dict(os.environ, {"TIER_3_ASSETS": "AAVEUSD"}, clear=False):
            assert get_asset_tier("AAVEUSD") == AssetTier.TIER_3


class TestExcludedAssets:
    """Tests for excluded asset detection."""

    def test_doge_is_excluded(self):
        """Test DOGE is correctly excluded."""
        assert get_asset_tier("DOGEUSD") == AssetTier.EXCLUDED

    def test_shib_is_excluded(self):
        """Test SHIB is correctly excluded."""
        assert get_asset_tier("SHIBUSD") == AssetTier.EXCLUDED

    def test_pepe_is_excluded(self):
        """Test PEPE is correctly excluded."""
        assert get_asset_tier("PEPEUSD") == AssetTier.EXCLUDED

    def test_all_meme_coins_in_excluded_list(self):
        """Test all meme coins are in EXCLUDED_ASSETS."""
        assert "DOGEUSD" in EXCLUDED_ASSETS
        assert "SHIBUSD" in EXCLUDED_ASSETS
        assert "PEPEUSD" in EXCLUDED_ASSETS
        assert "FLOKIUSD" in EXCLUDED_ASSETS
        assert "BONKUSD" in EXCLUDED_ASSETS

    def test_exclusion_reasons_exist(self):
        """Test exclusion reasons are defined for excluded assets."""
        for asset in ["DOGEUSD", "SHIBUSD", "PEPEUSD"]:
            assert asset in EXCLUSION_REASONS
            assert len(EXCLUSION_REASONS[asset]) > 0


class TestUnknownAssets:
    """Tests for unknown asset handling."""

    def test_unknown_asset_is_excluded(self):
        """Test unknown assets default to EXCLUDED."""
        assert get_asset_tier("UNKNOWNUSD") == AssetTier.EXCLUDED
        assert get_asset_tier("FAKEUSD") == AssetTier.EXCLUDED
        assert get_asset_tier("RANDOMUSD") == AssetTier.EXCLUDED


class TestAssetUniverseSize:
    """Tests for asset universe size."""

    def test_universe_contains_tier_1_and_2(self):
        """Test universe includes Tier 1 and Tier 2 assets."""
        universe = get_full_asset_universe()

        # Tier 1
        assert "BTCUSD" in universe
        assert "ETHUSD" in universe

        # Tier 2
        assert "SOLUSD" in universe
        assert "AVAXUSD" in universe
        assert "LINKUSD" in universe

    def test_universe_minimum_size(self):
        """Test universe has at least Tier 1 + Tier 2 assets."""
        universe = get_full_asset_universe()
        assert len(universe) >= 5  # 2 Tier 1 + 3 Tier 2

    def test_universe_maximum_size(self):
        """Test universe doesn't exceed 10 assets."""
        with patch.dict(os.environ, {"TIER_3_ASSETS": "AAVEUSD,UNIUSD,ARBUSD,OPUSD,MATICUSD"}, clear=False):
            universe = get_full_asset_universe()
            assert len(universe) <= 10

    def test_universe_with_tier_3(self):
        """Test universe includes Tier 3 when configured."""
        with patch.dict(os.environ, {"TIER_3_ASSETS": "AAVEUSD,UNIUSD"}, clear=False):
            universe = get_full_asset_universe()
            assert "AAVEUSD" in universe
            assert "UNIUSD" in universe


class TestTierAllocationLimits:
    """Tests for tier allocation limits."""

    def test_tier_1_allocation(self):
        """Test Tier 1 max allocation is 60%."""
        assert get_max_allocation(AssetTier.TIER_1) == Decimal("60.0")

    def test_tier_2_allocation(self):
        """Test Tier 2 max allocation is 30%."""
        assert get_max_allocation(AssetTier.TIER_2) == Decimal("30.0")

    def test_tier_3_allocation(self):
        """Test Tier 3 max allocation is 10%."""
        assert get_max_allocation(AssetTier.TIER_3) == Decimal("10.0")

    def test_excluded_allocation_is_zero(self):
        """Test excluded tier returns 0% allocation."""
        assert get_max_allocation(AssetTier.EXCLUDED) == Decimal("0")

    def test_total_allocation_is_100(self):
        """Test total allocation across all tiers equals 100%."""
        total = (
            get_max_allocation(AssetTier.TIER_1)
            + get_max_allocation(AssetTier.TIER_2)
            + get_max_allocation(AssetTier.TIER_3)
        )
        assert total == Decimal("100.0")


class TestTierConfigRetrieval:
    """Tests for get_tier_config function."""

    def test_get_tier_1_config(self):
        """Test getting Tier 1 config."""
        config = get_tier_config(AssetTier.TIER_1)
        assert config is not None
        assert config.max_allocation_percent == Decimal("60.0")

    def test_get_excluded_config(self):
        """Test getting excluded tier config returns None."""
        config = get_tier_config(AssetTier.EXCLUDED)
        assert config is None


class TestExclusionReasons:
    """Tests for get_exclusion_reason function."""

    def test_excluded_asset_has_reason(self):
        """Test excluded assets have reasons."""
        reason = get_exclusion_reason("DOGEUSD")
        assert reason is not None
        assert "Meme coin" in reason

    def test_unknown_excluded_has_reason(self):
        """Test unknown excluded assets get generic reason."""
        reason = get_exclusion_reason("UNKNOWNUSD")
        assert reason is not None
        assert "not in approved universe" in reason.lower()

    def test_tradeable_asset_no_reason(self):
        """Test tradeable assets have no exclusion reason."""
        reason = get_exclusion_reason("BTCUSD")
        assert reason is None


class TestIsTradeable:
    """Tests for is_tradeable function."""

    def test_tier_1_is_tradeable(self):
        """Test Tier 1 assets are tradeable."""
        assert is_tradeable("BTCUSD") is True
        assert is_tradeable("ETHUSD") is True

    def test_tier_2_is_tradeable(self):
        """Test Tier 2 assets are tradeable."""
        assert is_tradeable("SOLUSD") is True
        assert is_tradeable("AVAXUSD") is True

    def test_tier_3_is_tradeable(self):
        """Test Tier 3 assets are tradeable when configured."""
        with patch.dict(os.environ, {"TIER_3_ASSETS": "AAVEUSD"}, clear=False):
            assert is_tradeable("AAVEUSD") is True

    def test_excluded_not_tradeable(self):
        """Test excluded assets are not tradeable."""
        assert is_tradeable("DOGEUSD") is False
        assert is_tradeable("SHIBUSD") is False

    def test_unknown_not_tradeable(self):
        """Test unknown assets are not tradeable."""
        assert is_tradeable("UNKNOWNUSD") is False

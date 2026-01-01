"""
Tests for allocation_manager.py - Tier Allocation Enforcement.

Story 5.2: Asset Universe Reduction

Tests cover:
- Tier allocation limit calculations
- Allocation capacity checking
- Over-limit handling and position reduction
- Current tier allocation calculation
- Position size adjustment
- Allocation summary generation
"""

import pytest
from decimal import Decimal
from unittest.mock import patch

from services.allocation_manager import (
    AllocationResult,
    get_tier_allocation_limit,
    check_allocation_capacity,
    get_current_tier_allocations,
    calculate_position_size_for_tier,
    get_allocation_summary,
)
from services.asset_universe import AssetTier


class TestGetTierAllocationLimit:
    """Tests for get_tier_allocation_limit function."""

    def test_tier_1_limit_with_100k_portfolio(self):
        """Test Tier 1 limit is 60% of portfolio."""
        portfolio = Decimal("100000")
        limit = get_tier_allocation_limit(AssetTier.TIER_1, portfolio)
        assert limit == Decimal("60000")

    def test_tier_2_limit_with_100k_portfolio(self):
        """Test Tier 2 limit is 30% of portfolio."""
        portfolio = Decimal("100000")
        limit = get_tier_allocation_limit(AssetTier.TIER_2, portfolio)
        assert limit == Decimal("30000")

    def test_tier_3_limit_with_100k_portfolio(self):
        """Test Tier 3 limit is 10% of portfolio."""
        portfolio = Decimal("100000")
        limit = get_tier_allocation_limit(AssetTier.TIER_3, portfolio)
        assert limit == Decimal("10000")

    def test_excluded_limit_is_zero(self):
        """Test excluded tier has zero limit."""
        portfolio = Decimal("100000")
        limit = get_tier_allocation_limit(AssetTier.EXCLUDED, portfolio)
        assert limit == Decimal("0")

    def test_limit_scales_with_portfolio(self):
        """Test limit scales linearly with portfolio size."""
        portfolio_50k = Decimal("50000")
        portfolio_200k = Decimal("200000")

        limit_50k = get_tier_allocation_limit(AssetTier.TIER_1, portfolio_50k)
        limit_200k = get_tier_allocation_limit(AssetTier.TIER_1, portfolio_200k)

        assert limit_50k == Decimal("30000")  # 60% of 50k
        assert limit_200k == Decimal("120000")  # 60% of 200k


class TestCheckAllocationCapacity:
    """Tests for check_allocation_capacity function."""

    @pytest.mark.asyncio
    async def test_allocation_within_limits(self):
        """Test allocation succeeds when within limits."""
        result = await check_allocation_capacity(
            symbol="BTCUSD",
            tier=AssetTier.TIER_1,
            portfolio_value=Decimal("100000"),
            current_tier_allocation=Decimal("30000"),
            requested_amount=Decimal("10000"),
        )

        assert result.can_allocate is True
        assert result.max_amount == Decimal("10000")
        assert result.remaining_capacity == Decimal("20000")

    @pytest.mark.asyncio
    async def test_allocation_exceeds_limit_gets_reduced(self):
        """Test allocation is reduced when exceeding remaining capacity."""
        result = await check_allocation_capacity(
            symbol="BTCUSD",
            tier=AssetTier.TIER_1,
            portfolio_value=Decimal("100000"),
            current_tier_allocation=Decimal("55000"),  # $5k remaining
            requested_amount=Decimal("10000"),
        )

        assert result.can_allocate is True
        assert result.max_amount == Decimal("5000")  # Reduced to remaining
        assert result.remaining_capacity == Decimal("0")

    @pytest.mark.asyncio
    async def test_allocation_at_limit_blocked(self):
        """Test allocation is blocked when tier is at limit."""
        result = await check_allocation_capacity(
            symbol="BTCUSD",
            tier=AssetTier.TIER_1,
            portfolio_value=Decimal("100000"),
            current_tier_allocation=Decimal("60000"),  # At limit
            requested_amount=Decimal("10000"),
        )

        assert result.can_allocate is False
        assert result.max_amount == Decimal("0")
        assert result.remaining_capacity == Decimal("0")
        assert "limit reached" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_allocation_over_limit_blocked(self):
        """Test allocation is blocked when tier is over limit."""
        result = await check_allocation_capacity(
            symbol="BTCUSD",
            tier=AssetTier.TIER_1,
            portfolio_value=Decimal("100000"),
            current_tier_allocation=Decimal("65000"),  # Over limit
            requested_amount=Decimal("10000"),
        )

        assert result.can_allocate is False
        assert result.max_amount == Decimal("0")

    @pytest.mark.asyncio
    async def test_allocation_result_contains_tier_info(self):
        """Test allocation result contains tier limit info."""
        result = await check_allocation_capacity(
            symbol="SOLUSD",
            tier=AssetTier.TIER_2,
            portfolio_value=Decimal("100000"),
            current_tier_allocation=Decimal("15000"),
            requested_amount=Decimal("5000"),
        )

        assert result.tier_limit == Decimal("30000")  # Tier 2 = 30%
        assert result.current_allocation == Decimal("15000")

    @pytest.mark.asyncio
    async def test_tier_3_allocation(self):
        """Test Tier 3 allocation (10% limit)."""
        result = await check_allocation_capacity(
            symbol="AAVEUSD",
            tier=AssetTier.TIER_3,
            portfolio_value=Decimal("100000"),
            current_tier_allocation=Decimal("5000"),
            requested_amount=Decimal("3000"),
        )

        assert result.can_allocate is True
        assert result.max_amount == Decimal("3000")
        assert result.tier_limit == Decimal("10000")
        assert result.remaining_capacity == Decimal("2000")


class TestGetCurrentTierAllocations:
    """Tests for get_current_tier_allocations function."""

    @pytest.mark.asyncio
    async def test_empty_trades_returns_zero_allocations(self):
        """Test empty trade list returns zero for all tiers."""
        allocations = await get_current_tier_allocations([])

        assert allocations[AssetTier.TIER_1] == Decimal("0")
        assert allocations[AssetTier.TIER_2] == Decimal("0")
        assert allocations[AssetTier.TIER_3] == Decimal("0")
        assert allocations[AssetTier.EXCLUDED] == Decimal("0")

    @pytest.mark.asyncio
    async def test_single_tier_1_trade(self):
        """Test single Tier 1 trade allocation."""
        trades = [
            {"symbol": "BTCUSD", "entry_value": 30000},
        ]
        allocations = await get_current_tier_allocations(trades)

        assert allocations[AssetTier.TIER_1] == Decimal("30000")
        assert allocations[AssetTier.TIER_2] == Decimal("0")

    @pytest.mark.asyncio
    async def test_multiple_tier_1_trades_summed(self):
        """Test multiple Tier 1 trades are summed."""
        trades = [
            {"symbol": "BTCUSD", "entry_value": 30000},
            {"symbol": "ETHUSD", "entry_value": 20000},
        ]
        allocations = await get_current_tier_allocations(trades)

        assert allocations[AssetTier.TIER_1] == Decimal("50000")

    @pytest.mark.asyncio
    async def test_multiple_tiers_separated(self):
        """Test trades are correctly separated by tier."""
        trades = [
            {"symbol": "BTCUSD", "entry_value": 30000},  # Tier 1
            {"symbol": "ETHUSD", "entry_value": 20000},  # Tier 1
            {"symbol": "SOLUSD", "entry_value": 15000},  # Tier 2
            {"symbol": "LINKUSD", "entry_value": 10000},  # Tier 2
        ]
        allocations = await get_current_tier_allocations(trades)

        assert allocations[AssetTier.TIER_1] == Decimal("50000")
        assert allocations[AssetTier.TIER_2] == Decimal("25000")

    @pytest.mark.asyncio
    async def test_entry_price_and_size_calculation(self):
        """Test allocation calculated from entry_price * size."""
        trades = [
            {"symbol": "BTCUSD", "entry_price": 50000, "size": 0.5},  # = 25000
        ]
        allocations = await get_current_tier_allocations(trades)

        assert allocations[AssetTier.TIER_1] == Decimal("25000")


class TestCalculatePositionSizeForTier:
    """Tests for calculate_position_size_for_tier function."""

    def test_position_within_limit(self):
        """Test position size unchanged when within limit."""
        size = calculate_position_size_for_tier(
            tier=AssetTier.TIER_1,
            portfolio_value=Decimal("100000"),
            current_tier_allocation=Decimal("30000"),
            base_position_size=Decimal("10000"),
        )
        assert size == Decimal("10000")

    def test_position_reduced_to_remaining(self):
        """Test position size reduced to remaining capacity."""
        size = calculate_position_size_for_tier(
            tier=AssetTier.TIER_1,
            portfolio_value=Decimal("100000"),
            current_tier_allocation=Decimal("55000"),  # 5k remaining
            base_position_size=Decimal("10000"),
        )
        assert size == Decimal("5000")

    def test_position_zero_at_limit(self):
        """Test position size is zero when at limit."""
        size = calculate_position_size_for_tier(
            tier=AssetTier.TIER_1,
            portfolio_value=Decimal("100000"),
            current_tier_allocation=Decimal("60000"),
            base_position_size=Decimal("10000"),
        )
        assert size == Decimal("0")


class TestGetAllocationSummary:
    """Tests for get_allocation_summary function."""

    def test_summary_contains_all_tiers(self):
        """Test summary includes Tier 1, 2, and 3."""
        tier_allocations = {
            AssetTier.TIER_1: Decimal("30000"),
            AssetTier.TIER_2: Decimal("15000"),
            AssetTier.TIER_3: Decimal("5000"),
        }
        summary = get_allocation_summary(Decimal("100000"), tier_allocations)

        assert "TIER_1" in summary
        assert "TIER_2" in summary
        assert "TIER_3" in summary

    def test_summary_calculates_percentages(self):
        """Test summary calculates used percentage."""
        tier_allocations = {
            AssetTier.TIER_1: Decimal("30000"),  # 50% of 60k limit
        }
        summary = get_allocation_summary(Decimal("100000"), tier_allocations)

        assert summary["TIER_1"]["current"] == 30000.0
        assert summary["TIER_1"]["limit"] == 60000.0
        assert summary["TIER_1"]["used_percent"] == 50.0

    def test_summary_shows_at_limit(self):
        """Test summary correctly identifies tiers at limit."""
        tier_allocations = {
            AssetTier.TIER_1: Decimal("60000"),  # At limit
            AssetTier.TIER_2: Decimal("15000"),  # Not at limit
        }
        summary = get_allocation_summary(Decimal("100000"), tier_allocations)

        assert summary["TIER_1"]["at_limit"] is True
        assert summary["TIER_2"]["at_limit"] is False

    def test_summary_calculates_remaining(self):
        """Test summary calculates remaining capacity."""
        tier_allocations = {
            AssetTier.TIER_1: Decimal("40000"),
        }
        summary = get_allocation_summary(Decimal("100000"), tier_allocations)

        assert summary["TIER_1"]["remaining"] == 20000.0


class TestAllocationResult:
    """Tests for AllocationResult dataclass."""

    def test_allocation_result_creation(self):
        """Test AllocationResult can be created."""
        result = AllocationResult(
            can_allocate=True,
            max_amount=Decimal("10000"),
            current_allocation=Decimal("30000"),
            tier_limit=Decimal("60000"),
            remaining_capacity=Decimal("20000"),
            reason="Within limits",
        )

        assert result.can_allocate is True
        assert result.max_amount == Decimal("10000")
        assert result.current_allocation == Decimal("30000")
        assert result.tier_limit == Decimal("60000")
        assert result.remaining_capacity == Decimal("20000")
        assert result.reason == "Within limits"

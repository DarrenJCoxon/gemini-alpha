"""
On-chain data models for Story 5.6: On-Chain Data Integration.

This module provides SQLModel models for on-chain metrics:
- ExchangeFlow: Exchange inflow/outflow for accumulation/distribution analysis
- WhaleActivity: Large wallet transaction tracking
- FundingRate: Perpetual futures funding rates for squeeze detection
- StablecoinReserves: Stablecoin reserves on exchanges (buying power indicator)
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Column, String, DateTime, Numeric, Integer
from sqlmodel import Field, SQLModel

from .base import generate_cuid


class ExchangeFlow(SQLModel, table=True):
    """
    Exchange inflow/outflow data for accumulation/distribution analysis.

    Negative net flow = Accumulation (outflow > inflow) - Bullish
    Positive net flow = Distribution (inflow > outflow) - Bearish
    """
    __tablename__ = "ExchangeFlow"

    id: str = Field(
        default_factory=generate_cuid,
        sa_column=Column(String, primary_key=True),
    )
    asset_symbol: str = Field(
        sa_column=Column("assetSymbol", String(20), nullable=False, index=True),
    )
    timestamp: datetime = Field(
        sa_column=Column(DateTime, nullable=False, index=True),
    )

    # Flow data in USD
    inflow_usd: Decimal = Field(
        sa_column=Column("inflowUsd", Numeric(18, 2), nullable=False),
    )
    outflow_usd: Decimal = Field(
        sa_column=Column("outflowUsd", Numeric(18, 2), nullable=False),
    )
    net_flow_usd: Decimal = Field(
        sa_column=Column("netFlowUsd", Numeric(18, 2), nullable=False),
    )  # Negative = accumulation (outflow > inflow)

    # 7-day average for comparison
    avg_net_flow_7d: Optional[Decimal] = Field(
        default=None,
        sa_column=Column("avgNetFlow7d", Numeric(18, 2), nullable=True),
    )

    # Source metadata
    source: str = Field(
        default="cryptoquant",
        sa_column=Column(String(50), nullable=False),
    )


class WhaleActivity(SQLModel, table=True):
    """
    Large wallet transaction tracking.

    Tracks transactions > $1M to identify smart money movements.
    """
    __tablename__ = "WhaleActivity"

    id: str = Field(
        default_factory=generate_cuid,
        sa_column=Column(String, primary_key=True),
    )
    asset_symbol: str = Field(
        sa_column=Column("assetSymbol", String(20), nullable=False, index=True),
    )
    timestamp: datetime = Field(
        sa_column=Column(DateTime, nullable=False, index=True),
    )

    # Activity metrics
    large_tx_count: int = Field(
        sa_column=Column("largeTxCount", Integer, nullable=False),
    )  # Transactions > $1M
    total_whale_volume_usd: Decimal = Field(
        sa_column=Column("totalWhaleVolumeUsd", Numeric(18, 2), nullable=False),
    )

    # Direction analysis
    whale_buy_volume: Optional[Decimal] = Field(
        default=None,
        sa_column=Column("whaleBuyVolume", Numeric(18, 2), nullable=True),
    )
    whale_sell_volume: Optional[Decimal] = Field(
        default=None,
        sa_column=Column("whaleSellVolume", Numeric(18, 2), nullable=True),
    )

    # 7-day average for comparison
    avg_large_tx_count_7d: Optional[int] = Field(
        default=None,
        sa_column=Column("avgLargeTxCount7d", Integer, nullable=True),
    )

    source: str = Field(
        default="cryptoquant",
        sa_column=Column(String(50), nullable=False),
    )


class FundingRate(SQLModel, table=True):
    """
    Perpetual futures funding rates for squeeze detection.

    Extreme positive = Market heavily long, long squeeze risk
    Extreme negative = Market heavily short, short squeeze risk
    """
    __tablename__ = "FundingRate"

    id: str = Field(
        default_factory=generate_cuid,
        sa_column=Column(String, primary_key=True),
    )
    asset_symbol: str = Field(
        sa_column=Column("assetSymbol", String(20), nullable=False, index=True),
    )
    timestamp: datetime = Field(
        sa_column=Column(DateTime, nullable=False, index=True),
    )
    exchange: str = Field(
        sa_column=Column(String(50), nullable=False),
    )  # binance, bybit, aggregate, etc.

    # Funding rate (typically per 8 hours)
    funding_rate: Decimal = Field(
        sa_column=Column("fundingRate", Numeric(10, 6), nullable=False),
    )  # e.g., 0.0001 = 0.01%

    # Aggregated rates
    avg_funding_rate_24h: Optional[Decimal] = Field(
        default=None,
        sa_column=Column("avgFundingRate24h", Numeric(10, 6), nullable=True),
    )

    # Open interest for context
    open_interest_usd: Optional[Decimal] = Field(
        default=None,
        sa_column=Column("openInterestUsd", Numeric(18, 2), nullable=True),
    )

    source: str = Field(
        default="cryptoquant",
        sa_column=Column(String(50), nullable=False),
    )


class StablecoinReserves(SQLModel, table=True):
    """
    Stablecoin reserves on exchanges (buying power indicator).

    Rising reserves = More dry powder ready to buy = Bullish
    Falling reserves = Less buying power available = Bearish
    """
    __tablename__ = "StablecoinReserves"

    id: str = Field(
        default_factory=generate_cuid,
        sa_column=Column(String, primary_key=True),
    )
    timestamp: datetime = Field(
        sa_column=Column(DateTime, nullable=False, index=True),
    )

    # Reserve amounts in USD
    total_reserves_usd: Decimal = Field(
        sa_column=Column("totalReservesUsd", Numeric(18, 2), nullable=False),
    )
    usdt_reserves: Decimal = Field(
        sa_column=Column("usdtReserves", Numeric(18, 2), nullable=False),
    )
    usdc_reserves: Decimal = Field(
        sa_column=Column("usdcReserves", Numeric(18, 2), nullable=False),
    )

    # Change metrics
    change_24h_pct: Optional[Decimal] = Field(
        default=None,
        sa_column=Column("change24hPct", Numeric(8, 4), nullable=True),
    )
    change_7d_pct: Optional[Decimal] = Field(
        default=None,
        sa_column=Column("change7dPct", Numeric(8, 4), nullable=True),
    )

    source: str = Field(
        default="cryptoquant",
        sa_column=Column(String(50), nullable=False),
    )


# Export all models
__all__ = [
    "ExchangeFlow",
    "WhaleActivity",
    "FundingRate",
    "StablecoinReserves",
]

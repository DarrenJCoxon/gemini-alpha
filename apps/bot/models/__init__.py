"""
Models module - SQLModel definitions.

This module contains SQLModel classes that mirror the Prisma schema
for type-safe database operations in Python.
"""

from .base import Decision, TradeStatus, generate_cuid
from .asset import Asset, AssetTier
from .candle import Candle
from .sentiment import SentimentLog
from .council import CouncilSession
from .trade import Trade
from .system_config import SystemConfig, SystemStatus
from .portfolio import PortfolioSnapshot
from .scaled_position import (
    ScaledPosition,
    ScaleOrder,
    ScaleDirection,
    ScaleStatus,
    ScaleTriggerType,
)
from .onchain import (
    ExchangeFlow,
    WhaleActivity,
    FundingRate,
    StablecoinReserves,
)

__all__ = [
    # Enums
    "Decision",
    "TradeStatus",
    "SystemStatus",
    "ScaleDirection",
    "ScaleStatus",
    "ScaleTriggerType",
    # Utility functions
    "generate_cuid",
    # Models
    "Asset",
    "AssetTier",
    "Candle",
    "SentimentLog",
    "CouncilSession",
    "Trade",
    "SystemConfig",
    "PortfolioSnapshot",
    "ScaledPosition",
    "ScaleOrder",
    # On-chain models
    "ExchangeFlow",
    "WhaleActivity",
    "FundingRate",
    "StablecoinReserves",
]

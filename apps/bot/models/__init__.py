"""
Models module - SQLModel definitions.

This module contains SQLModel classes that mirror the Prisma schema
for type-safe database operations in Python.
"""

from .base import Decision, TradeStatus, generate_cuid
from .asset import Asset
from .candle import Candle
from .sentiment import SentimentLog
from .council import CouncilSession
from .trade import Trade
from .system_config import SystemConfig, SystemStatus
from .scaled_position import (
    ScaledPosition,
    ScaleOrder,
    ScaleDirection,
    ScaleStatus,
    ScaleTriggerType,
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
    "Candle",
    "SentimentLog",
    "CouncilSession",
    "Trade",
    "SystemConfig",
    "ScaledPosition",
    "ScaleOrder",
]

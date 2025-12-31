"""
Base SQLModel configuration for the trading bot.

This module provides the base classes and common configurations
for all SQLModel models in the application.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional

from sqlmodel import Field, SQLModel


class Decision(str, Enum):
    """Trading decision enum matching Prisma schema."""
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"


class TradeStatus(str, Enum):
    """Trade status enum matching Prisma schema."""
    PENDING = "PENDING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


def generate_cuid() -> str:
    """Generate a CUID-like identifier.

    Note: For production, consider using the cuid2 package.
    This is a simplified version for development.
    """
    import time
    import random
    import string

    timestamp = hex(int(time.time() * 1000))[2:]
    random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
    return f"c{timestamp}{random_part}"


# Re-export commonly used types
__all__ = [
    "SQLModel",
    "Field",
    "Decision",
    "TradeStatus",
    "Decimal",
    "datetime",
    "Optional",
    "Dict",
    "Any",
    "generate_cuid",
]

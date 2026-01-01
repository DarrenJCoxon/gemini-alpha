"""
Average price calculation utilities for scaled positions.

Story 5.4: Scale In/Out Position Management

This module provides functions for calculating:
- Weighted average entry prices from multiple entries
- Realized P&L from partial exits
- Position cost basis for tax/reporting

The weighted average formula is:
    Average Price = Sum(size_i * price_i) / Sum(size_i)
"""

from decimal import Decimal
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class AveragePosition:
    """
    Calculated position metrics from multiple entries.

    Attributes:
        total_size: Total position size across all entries
        total_cost: Total cost (size * price) of all entries
        average_price: Weighted average entry price
        num_entries: Number of entries in the position
        entries: List of individual entry records
    """
    total_size: Decimal
    total_cost: Decimal
    average_price: Decimal
    num_entries: int
    entries: List[Dict[str, Any]]


@dataclass
class RealizedPnL:
    """
    Realized profit/loss calculation from partial exits.

    Attributes:
        realized_pnl: Dollar amount of realized P&L
        realized_pnl_pct: Percentage P&L based on cost basis
        average_entry: Average entry price used for calculation
        average_exit: Average exit price across all exits
        exited_size: Total size that has been exited
        remaining_size: Remaining position size
        cost_basis: Cost basis of exited portion
        exit_value: Total value received from exits
    """
    realized_pnl: Decimal
    realized_pnl_pct: Decimal
    average_entry: Decimal
    average_exit: Decimal
    exited_size: Decimal
    remaining_size: Decimal
    cost_basis: Decimal
    exit_value: Decimal


def calculate_average_entry(
    entries: List[Dict[str, Any]]
) -> AveragePosition:
    """
    Calculate weighted average entry price from multiple entries.

    The weighted average gives more weight to larger positions,
    providing the true average cost per unit.

    Args:
        entries: List of entry dicts with "size" and "price" keys
                 Values can be Decimal, float, int, or str

    Returns:
        AveragePosition with calculated metrics

    Example:
        >>> entries = [
        ...     {"size": "1.0", "price": "100.0"},
        ...     {"size": "1.0", "price": "90.0"},
        ...     {"size": "1.0", "price": "80.0"},
        ... ]
        >>> result = calculate_average_entry(entries)
        >>> result.average_price
        Decimal('90.0')  # (100+90+80)/3
    """
    if not entries:
        return AveragePosition(
            total_size=Decimal("0"),
            total_cost=Decimal("0"),
            average_price=Decimal("0"),
            num_entries=0,
            entries=entries,
        )

    total_size = Decimal("0")
    total_cost = Decimal("0")

    for entry in entries:
        size = Decimal(str(entry["size"]))
        price = Decimal(str(entry["price"]))
        total_size += size
        total_cost += size * price

    average_price = total_cost / total_size if total_size > 0 else Decimal("0")

    return AveragePosition(
        total_size=total_size,
        total_cost=total_cost,
        average_price=average_price,
        num_entries=len(entries),
        entries=entries,
    )


def calculate_realized_pnl(
    entries: List[Dict[str, Any]],
    exits: List[Dict[str, Any]]
) -> RealizedPnL:
    """
    Calculate realized P&L from scaled entries and exits.

    Uses the average cost method (not FIFO/LIFO) to calculate
    the cost basis for exited portions.

    Args:
        entries: List of entry dicts with "size" and "price" keys
        exits: List of exit dicts with "size" and "price" keys

    Returns:
        RealizedPnL with calculated metrics

    Example:
        >>> entries = [
        ...     {"size": "1.0", "price": "100.0"},
        ...     {"size": "1.0", "price": "90.0"},
        ... ]
        >>> exits = [
        ...     {"size": "1.0", "price": "110.0"},
        ... ]
        >>> result = calculate_realized_pnl(entries, exits)
        >>> result.realized_pnl
        Decimal('15.0')  # Sold 1 @ 110, avg cost 95 = +15 profit
    """
    # Calculate average entry
    avg_entry = calculate_average_entry(entries)

    if not exits:
        return RealizedPnL(
            realized_pnl=Decimal("0"),
            realized_pnl_pct=Decimal("0"),
            average_entry=avg_entry.average_price,
            average_exit=Decimal("0"),
            exited_size=Decimal("0"),
            remaining_size=avg_entry.total_size,
            cost_basis=Decimal("0"),
            exit_value=Decimal("0"),
        )

    # Calculate total exit value
    total_exit_value = Decimal("0")
    total_exit_size = Decimal("0")

    for exit_order in exits:
        size = Decimal(str(exit_order["size"]))
        price = Decimal(str(exit_order["price"]))
        total_exit_size += size
        total_exit_value += size * price

    # Calculate average exit price
    average_exit = total_exit_value / total_exit_size if total_exit_size > 0 else Decimal("0")

    # Calculate cost basis for exited portion (using average entry)
    cost_basis = avg_entry.average_price * total_exit_size

    # Calculate realized P&L
    realized_pnl = total_exit_value - cost_basis
    realized_pnl_pct = (realized_pnl / cost_basis * 100) if cost_basis > 0 else Decimal("0")

    # Calculate remaining position
    remaining_size = avg_entry.total_size - total_exit_size

    return RealizedPnL(
        realized_pnl=realized_pnl,
        realized_pnl_pct=realized_pnl_pct,
        average_entry=avg_entry.average_price,
        average_exit=average_exit,
        exited_size=total_exit_size,
        remaining_size=remaining_size,
        cost_basis=cost_basis,
        exit_value=total_exit_value,
    )


def calculate_unrealized_pnl(
    entries: List[Dict[str, Any]],
    current_price: float,
    exits: List[Dict[str, Any]] = None
) -> Dict[str, Decimal]:
    """
    Calculate unrealized P&L for remaining position.

    Args:
        entries: List of entry dicts with "size" and "price" keys
        current_price: Current market price
        exits: Optional list of exits to account for

    Returns:
        Dict with unrealized_pnl, unrealized_pnl_pct, remaining_size, current_value

    Example:
        >>> entries = [{"size": "2.0", "price": "100.0"}]
        >>> result = calculate_unrealized_pnl(entries, current_price=110.0)
        >>> result["unrealized_pnl"]
        Decimal('20.0')  # 2 units * (110 - 100) = 20
    """
    avg_entry = calculate_average_entry(entries)

    # Account for any exits
    exited_size = Decimal("0")
    if exits:
        for exit_order in exits:
            exited_size += Decimal(str(exit_order["size"]))

    remaining_size = avg_entry.total_size - exited_size

    if remaining_size <= 0:
        return {
            "unrealized_pnl": Decimal("0"),
            "unrealized_pnl_pct": Decimal("0"),
            "remaining_size": Decimal("0"),
            "current_value": Decimal("0"),
            "cost_basis": Decimal("0"),
        }

    current_price_dec = Decimal(str(current_price))
    current_value = remaining_size * current_price_dec
    cost_basis = remaining_size * avg_entry.average_price

    unrealized_pnl = current_value - cost_basis
    unrealized_pnl_pct = (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else Decimal("0")

    return {
        "unrealized_pnl": unrealized_pnl,
        "unrealized_pnl_pct": unrealized_pnl_pct,
        "remaining_size": remaining_size,
        "current_value": current_value,
        "cost_basis": cost_basis,
    }


def calculate_total_pnl(
    entries: List[Dict[str, Any]],
    exits: List[Dict[str, Any]],
    current_price: float
) -> Dict[str, Decimal]:
    """
    Calculate total P&L (realized + unrealized).

    Args:
        entries: List of entry dicts with "size" and "price" keys
        exits: List of exit dicts with "size" and "price" keys
        current_price: Current market price for unrealized calculation

    Returns:
        Dict with total_pnl, realized_pnl, unrealized_pnl, and percentages
    """
    realized = calculate_realized_pnl(entries, exits)
    unrealized = calculate_unrealized_pnl(entries, current_price, exits)

    total_pnl = realized.realized_pnl + unrealized["unrealized_pnl"]

    # Calculate total cost basis (for percentage)
    avg_entry = calculate_average_entry(entries)
    total_cost_basis = avg_entry.total_cost

    total_pnl_pct = (total_pnl / total_cost_basis * 100) if total_cost_basis > 0 else Decimal("0")

    return {
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "realized_pnl": realized.realized_pnl,
        "realized_pnl_pct": realized.realized_pnl_pct,
        "unrealized_pnl": unrealized["unrealized_pnl"],
        "unrealized_pnl_pct": unrealized["unrealized_pnl_pct"],
        "average_entry": avg_entry.average_price,
        "average_exit": realized.average_exit,
        "total_size": avg_entry.total_size,
        "exited_size": realized.exited_size,
        "remaining_size": realized.remaining_size,
    }

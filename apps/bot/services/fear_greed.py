"""
Fear & Greed Index API Client.

Fetches the Crypto Fear & Greed Index from Alternative.me API.
This is a FREE API that provides market sentiment data.

API Docs: https://alternative.me/crypto/fear-and-greed-index/

The index ranges from 0-100:
- 0-24: Extreme Fear (BUY signal for contrarian)
- 25-44: Fear
- 45-55: Neutral
- 56-75: Greed
- 76-100: Extreme Greed (SELL signal for contrarian)
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger("fear_greed")

# API endpoint (free, no auth required)
FEAR_GREED_API_URL = "https://api.alternative.me/fng/"


@dataclass
class FearGreedData:
    """Fear & Greed Index data point."""

    value: int  # 0-100 scale
    classification: str  # "Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"
    timestamp: datetime

    def to_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        return {
            "value": self.value,
            "classification": self.classification,
            "timestamp": self.timestamp.isoformat(),
        }

    @property
    def is_extreme_fear(self) -> bool:
        """Check if market is in extreme fear (contrarian BUY zone)."""
        return self.value <= 24

    @property
    def is_extreme_greed(self) -> bool:
        """Check if market is in extreme greed (contrarian SELL zone)."""
        return self.value >= 76


async def fetch_fear_greed_index(limit: int = 1) -> Optional[FearGreedData]:
    """
    Fetch the current Fear & Greed Index from Alternative.me.

    Args:
        limit: Number of historical data points (1 = current only)

    Returns:
        FearGreedData object or None if fetch failed
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                FEAR_GREED_API_URL,
                params={"limit": limit, "format": "json"}
            )
            response.raise_for_status()

            data = response.json()

            if "data" not in data or not data["data"]:
                logger.warning("Fear & Greed API returned no data")
                return None

            # Get the most recent entry
            latest = data["data"][0]

            # Parse timestamp (Unix timestamp)
            timestamp = datetime.fromtimestamp(
                int(latest["timestamp"]),
                tz=timezone.utc
            ).replace(tzinfo=None)  # Naive for Prisma compatibility

            result = FearGreedData(
                value=int(latest["value"]),
                classification=latest["value_classification"],
                timestamp=timestamp,
            )

            logger.info(
                f"[FearGreed] Current index: {result.value} ({result.classification})"
            )

            return result

    except httpx.HTTPStatusError as e:
        logger.error(f"Fear & Greed API HTTP error: {e.response.status_code}")
        return None
    except httpx.RequestError as e:
        logger.error(f"Fear & Greed API request failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Fear & Greed API error: {e}")
        return None


async def fetch_fear_greed_history(days: int = 7) -> list[FearGreedData]:
    """
    Fetch historical Fear & Greed data.

    Args:
        days: Number of days of history to fetch

    Returns:
        List of FearGreedData objects (newest first)
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                FEAR_GREED_API_URL,
                params={"limit": days, "format": "json"}
            )
            response.raise_for_status()

            data = response.json()

            if "data" not in data:
                return []

            results = []
            for entry in data["data"]:
                timestamp = datetime.fromtimestamp(
                    int(entry["timestamp"]),
                    tz=timezone.utc
                ).replace(tzinfo=None)

                results.append(FearGreedData(
                    value=int(entry["value"]),
                    classification=entry["value_classification"],
                    timestamp=timestamp,
                ))

            logger.info(f"[FearGreed] Fetched {len(results)} days of history")
            return results

    except Exception as e:
        logger.error(f"Fear & Greed history fetch failed: {e}")
        return []


def fear_greed_to_contrarian_score(fg_value: int) -> int:
    """
    Convert Fear & Greed Index to ContrarianAI fear score.

    The F&G index is:
    - 0 = Extreme Fear (market scared)
    - 100 = Extreme Greed (market euphoric)

    Our fear_score is the same scale, so we use it directly.
    This gives us:
    - Low fear_score (0-25) = Extreme Fear = BUY opportunity
    - High fear_score (75-100) = Extreme Greed = SELL opportunity

    Args:
        fg_value: Fear & Greed index value (0-100)

    Returns:
        fear_score for sentiment analysis (0-100)
    """
    # Direct mapping - F&G 0 = fear_score 0 (extreme fear = buy)
    return fg_value

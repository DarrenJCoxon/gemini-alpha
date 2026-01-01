"""
CryptoPanic API client for crypto news sentiment.

CryptoPanic is a news aggregator that tracks crypto news and provides
sentiment indicators (bullish/bearish votes) from the community.

API Documentation: https://cryptopanic.com/developers/api/
Get free API key: https://cryptopanic.com/developers/api/keys

Story 1.4: Sentiment Ingestor - Real news aggregation.
"""

import logging
import os
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional, List

import httpx

# Configure logging
logger = logging.getLogger("sentiment_ingestor")

# API Configuration
CRYPTOPANIC_API_URL = "https://cryptopanic.com/api/v1/posts/"


@dataclass
class CryptoPanicNews:
    """Data class for a CryptoPanic news item."""

    title: str
    url: str
    source: str
    published_at: datetime
    currencies: List[str]  # Affected currencies
    kind: str  # "news" or "media"
    votes: dict  # {"positive": int, "negative": int, "important": int, ...}
    sentiment: Optional[str] = None  # "bullish", "bearish", or None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "published_at": self.published_at.isoformat(),
            "currencies": self.currencies,
            "kind": self.kind,
            "votes": self.votes,
            "sentiment": self.sentiment,
        }


class BaseCryptoPanicClient(ABC):
    """Abstract base class for CryptoPanic clients."""

    # Symbol mapping from our format to CryptoPanic format
    SYMBOL_MAP = {
        "BTCUSD": "BTC",
        "ETHUSD": "ETH",
        "SOLUSD": "SOL",
        "ADAUSD": "ADA",
        "DOTUSD": "DOT",
        "AVAXUSD": "AVAX",
        "LINKUSD": "LINK",
        "MATICUSD": "MATIC",
        "ATOMUSD": "ATOM",
        "XRPUSD": "XRP",
        "DOGEUSD": "DOGE",
        "SHIBUSD": "SHIB",
        "UNIUSD": "UNI",
        "AABORUSD": "AAVE",
        "LTCUSD": "LTC",
    }

    @abstractmethod
    async def fetch_news(
        self,
        symbol: str,
        filter_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[CryptoPanicNews]:
        """
        Fetch news for a cryptocurrency.

        Args:
            symbol: Our symbol format (e.g., "SOLUSD")
            filter_type: Optional filter - "rising", "hot", "bullish", "bearish", "important"
            limit: Maximum number of news items

        Returns:
            List of CryptoPanicNews objects
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the client."""
        pass

    def normalize_symbol(self, symbol: str) -> str:
        """Convert our symbol format to CryptoPanic format."""
        # Check direct mapping first
        if symbol in self.SYMBOL_MAP:
            return self.SYMBOL_MAP[symbol]

        # Try stripping USD suffix
        if symbol.endswith("USD"):
            return symbol[:-3]

        return symbol


class CryptoPanicClient(BaseCryptoPanicClient):
    """
    Real CryptoPanic API client.

    Requires CRYPTOPANIC_API_KEY environment variable.
    Get free key at: https://cryptopanic.com/developers/api/keys
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = 10.0,
    ) -> None:
        """
        Initialize CryptoPanic client.

        Args:
            api_key: CryptoPanic API auth token
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv("CRYPTOPANIC_API_KEY", "")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def fetch_news(
        self,
        symbol: str,
        filter_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[CryptoPanicNews]:
        """
        Fetch news for a cryptocurrency.

        Args:
            symbol: Our symbol format (e.g., "SOLUSD")
            filter_type: Optional filter - "rising", "hot", "bullish", "bearish", "important"
            limit: Maximum number of news items

        Returns:
            List of CryptoPanicNews objects
        """
        if not self.api_key:
            logger.warning("CryptoPanic API key not set, skipping")
            return []

        news_items = []
        crypto_symbol = self.normalize_symbol(symbol)

        try:
            client = await self._get_client()

            # Build request parameters
            params = {
                "auth_token": self.api_key,
                "currencies": crypto_symbol,
                "public": "true",
                "kind": "news",
            }

            if filter_type and filter_type in ["rising", "hot", "bullish", "bearish", "important"]:
                params["filter"] = filter_type

            response = await client.get(CRYPTOPANIC_API_URL, params=params)

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])

                for item in results[:limit]:
                    # Parse publication date
                    pub_date_str = item.get("published_at", "")
                    try:
                        pub_date = datetime.fromisoformat(
                            pub_date_str.replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError):
                        pub_date = datetime.now(timezone.utc)

                    # Extract currencies mentioned
                    currencies = []
                    for currency in item.get("currencies", []):
                        if isinstance(currency, dict):
                            currencies.append(currency.get("code", ""))
                        else:
                            currencies.append(str(currency))

                    # Get votes
                    votes = item.get("votes", {})

                    # Determine sentiment from votes
                    positive = votes.get("positive", 0)
                    negative = votes.get("negative", 0)
                    sentiment = None
                    if positive > negative + 2:
                        sentiment = "bullish"
                    elif negative > positive + 2:
                        sentiment = "bearish"

                    news_items.append(
                        CryptoPanicNews(
                            title=item.get("title", ""),
                            url=item.get("url", ""),
                            source=item.get("source", {}).get("title", "Unknown"),
                            published_at=pub_date,
                            currencies=currencies,
                            kind=item.get("kind", "news"),
                            votes=votes,
                            sentiment=sentiment,
                        )
                    )

                logger.debug(
                    f"CryptoPanic: Fetched {len(news_items)} news items for {symbol}"
                )

            elif response.status_code == 401:
                logger.error("CryptoPanic: Invalid API key")
            elif response.status_code == 429:
                logger.warning("CryptoPanic: Rate limit exceeded")
            else:
                logger.warning(
                    f"CryptoPanic: API returned status {response.status_code}"
                )

        except httpx.TimeoutException:
            logger.warning(f"CryptoPanic: Request timeout for {symbol}")
        except Exception as e:
            logger.error(f"CryptoPanic: Error fetching news for {symbol}: {e}")

        return news_items

    async def fetch_market_news(
        self,
        filter_type: str = "hot",
        limit: int = 20,
    ) -> List[CryptoPanicNews]:
        """
        Fetch general market news (not filtered by currency).

        Args:
            filter_type: Filter - "rising", "hot", "bullish", "bearish", "important"
            limit: Maximum number of news items

        Returns:
            List of CryptoPanicNews objects
        """
        if not self.api_key:
            logger.warning("CryptoPanic API key not set, skipping")
            return []

        news_items = []

        try:
            client = await self._get_client()

            params = {
                "auth_token": self.api_key,
                "public": "true",
                "filter": filter_type,
                "kind": "news",
            }

            response = await client.get(CRYPTOPANIC_API_URL, params=params)

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])

                for item in results[:limit]:
                    pub_date_str = item.get("published_at", "")
                    try:
                        pub_date = datetime.fromisoformat(
                            pub_date_str.replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError):
                        pub_date = datetime.now(timezone.utc)

                    currencies = []
                    for currency in item.get("currencies", []):
                        if isinstance(currency, dict):
                            currencies.append(currency.get("code", ""))
                        else:
                            currencies.append(str(currency))

                    votes = item.get("votes", {})
                    positive = votes.get("positive", 0)
                    negative = votes.get("negative", 0)
                    sentiment = None
                    if positive > negative + 2:
                        sentiment = "bullish"
                    elif negative > positive + 2:
                        sentiment = "bearish"

                    news_items.append(
                        CryptoPanicNews(
                            title=item.get("title", ""),
                            url=item.get("url", ""),
                            source=item.get("source", {}).get("title", "Unknown"),
                            published_at=pub_date,
                            currencies=currencies,
                            kind=item.get("kind", "news"),
                            votes=votes,
                            sentiment=sentiment,
                        )
                    )

                logger.info(
                    f"CryptoPanic: Fetched {len(news_items)} {filter_type} market news"
                )

        except Exception as e:
            logger.error(f"CryptoPanic: Error fetching market news: {e}")

        return news_items

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.debug("CryptoPanic client closed")


class MockCryptoPanicClient(BaseCryptoPanicClient):
    """
    Mock CryptoPanic client for development and testing.

    Generates realistic sample news for sentiment pipeline testing.
    """

    # Sample news templates
    BULLISH_TEMPLATES = [
        "{symbol} hits new weekly high as institutional buying accelerates",
        "Major fund announces ${amount}M {symbol} position",
        "{symbol} network upgrade drives optimism among developers",
        "Breaking: {symbol} partnership with Fortune 500 company announced",
        "Whale accumulation of {symbol} reaches yearly high",
        "{symbol} trading volume surges 50% amid bullish sentiment",
    ]

    BEARISH_TEMPLATES = [
        "{symbol} faces selling pressure as market corrects",
        "Regulatory concerns weigh on {symbol} price action",
        "{symbol} whale moves large amount to exchange",
        "Technical breakdown: {symbol} loses key support level",
        "Profit-taking intensifies as {symbol} stalls at resistance",
    ]

    NEUTRAL_TEMPLATES = [
        "{symbol} consolidates ahead of major event",
        "Analysts divided on {symbol} short-term direction",
        "{symbol} trading in tight range as market awaits catalyst",
        "Weekly {symbol} market update: What to watch",
        "{symbol} development update: New features in progress",
    ]

    SOURCES = [
        "CoinDesk",
        "Cointelegraph",
        "The Block",
        "Decrypt",
        "CryptoSlate",
        "NewsBTC",
        "Bitcoin Magazine",
    ]

    def __init__(self, seed: Optional[int] = None) -> None:
        """Initialize mock client."""
        if seed is not None:
            random.seed(seed)

    async def fetch_news(
        self,
        symbol: str,
        filter_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[CryptoPanicNews]:
        """Generate mock news for a symbol."""
        crypto_symbol = self.normalize_symbol(symbol)
        news_items = []
        now = datetime.now(timezone.utc)

        for i in range(min(limit, 5)):
            # Choose sentiment type (bias towards bullish/neutral)
            sentiment_type = random.choice(
                ["bullish", "bullish", "neutral", "neutral", "bearish"]
            )

            if sentiment_type == "bullish":
                template = random.choice(self.BULLISH_TEMPLATES)
                sentiment = "bullish"
                votes = {"positive": random.randint(10, 50), "negative": random.randint(0, 5)}
            elif sentiment_type == "bearish":
                template = random.choice(self.BEARISH_TEMPLATES)
                sentiment = "bearish"
                votes = {"positive": random.randint(0, 5), "negative": random.randint(10, 50)}
            else:
                template = random.choice(self.NEUTRAL_TEMPLATES)
                sentiment = None
                votes = {"positive": random.randint(5, 15), "negative": random.randint(5, 15)}

            title = template.format(
                symbol=crypto_symbol,
                amount=random.randint(10, 500),
            )

            # Random time in last 24 hours
            hours_ago = random.randint(1, 24)
            pub_date = now - timedelta(hours=hours_ago)

            news_items.append(
                CryptoPanicNews(
                    title=title,
                    url=f"https://example.com/news/{random.randint(10000, 99999)}",
                    source=random.choice(self.SOURCES),
                    published_at=pub_date,
                    currencies=[crypto_symbol],
                    kind="news",
                    votes=votes,
                    sentiment=sentiment,
                )
            )

        logger.debug(f"[MOCK] Generated {len(news_items)} CryptoPanic news for {symbol}")
        return news_items

    async def fetch_market_news(
        self,
        filter_type: str = "hot",
        limit: int = 20,
    ) -> List[CryptoPanicNews]:
        """Generate mock market news."""
        news_items = []
        now = datetime.now(timezone.utc)
        symbols = ["BTC", "ETH", "SOL", "ADA", "XRP"]

        for i in range(min(limit, 10)):
            symbol = random.choice(symbols)
            sentiment_type = random.choice(["bullish", "neutral", "bearish"])

            if sentiment_type == "bullish":
                template = random.choice(self.BULLISH_TEMPLATES)
                sentiment = "bullish"
                votes = {"positive": random.randint(20, 100), "negative": random.randint(0, 10)}
            elif sentiment_type == "bearish":
                template = random.choice(self.BEARISH_TEMPLATES)
                sentiment = "bearish"
                votes = {"positive": random.randint(0, 10), "negative": random.randint(20, 100)}
            else:
                template = random.choice(self.NEUTRAL_TEMPLATES)
                sentiment = None
                votes = {"positive": random.randint(10, 30), "negative": random.randint(10, 30)}

            title = template.format(symbol=symbol, amount=random.randint(10, 500))
            hours_ago = random.randint(1, 12)

            news_items.append(
                CryptoPanicNews(
                    title=title,
                    url=f"https://example.com/news/{random.randint(10000, 99999)}",
                    source=random.choice(self.SOURCES),
                    published_at=now - timedelta(hours=hours_ago),
                    currencies=[symbol],
                    kind="news",
                    votes=votes,
                    sentiment=sentiment,
                )
            )

        logger.debug(f"[MOCK] Generated {len(news_items)} CryptoPanic market news")
        return news_items

    async def close(self) -> None:
        """Close mock client."""
        pass


def get_cryptopanic_client(use_mock: bool = False) -> BaseCryptoPanicClient:
    """
    Factory function to get appropriate CryptoPanic client.

    Args:
        use_mock: Force use of mock client (for testing)

    Returns:
        BaseCryptoPanicClient instance
    """
    if use_mock:
        logger.info("Using mock CryptoPanic client (forced)")
        return MockCryptoPanicClient()

    api_key = os.getenv("CRYPTOPANIC_API_KEY", "")

    if api_key:
        logger.info("CryptoPanic API key found, using real client")
        return CryptoPanicClient()
    else:
        logger.info("No CryptoPanic API key - using mock client")
        return MockCryptoPanicClient()


# Global client instance
_cryptopanic_client: Optional[BaseCryptoPanicClient] = None


def get_or_create_cryptopanic_client() -> BaseCryptoPanicClient:
    """Get or create the global CryptoPanic client instance."""
    global _cryptopanic_client
    if _cryptopanic_client is None:
        _cryptopanic_client = get_cryptopanic_client()
    return _cryptopanic_client


async def close_cryptopanic_client() -> None:
    """Close the global CryptoPanic client."""
    global _cryptopanic_client
    if _cryptopanic_client is not None:
        await _cryptopanic_client.close()
        _cryptopanic_client = None

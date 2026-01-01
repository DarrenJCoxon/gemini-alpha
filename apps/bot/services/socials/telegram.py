"""
Telegram fetcher for social sentiment data.

This module provides functionality to:
- Fetch recent messages from Telegram channels
- Monitor specific crypto-focused channels
- Extract message content for sentiment analysis

Story 1.4: Sentiment Ingestor - Real Telethon implementation.

Security Note:
- API credentials stored in environment variables
- Session files should be protected (contain auth tokens)
- Never commit session files to version control
"""

import asyncio
import logging
import os
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List

# Configure logging
logger = logging.getLogger("sentiment_ingestor")


@dataclass
class TelegramMessage:
    """Data class for a Telegram message."""

    text: str
    channel: str
    timestamp: datetime
    views: int
    forwards: int
    message_id: int

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "channel": self.channel,
            "timestamp": self.timestamp.isoformat(),
            "views": self.views,
            "forwards": self.forwards,
            "message_id": self.message_id,
        }


class BaseTelegramFetcher(ABC):
    """Abstract base class for Telegram fetchers."""

    # Default target channels for crypto sentiment
    # Verified reputable public channels - curated for reliability
    TARGET_CHANNELS = [
        # === Tier 1: Major News Outlets ===
        "cryptonews",            # Crypto news aggregator
        "crypto",                # General crypto community
        "BitcoinMagazine",       # Bitcoin Magazine official

        # === Tier 2: Market Data & Analysis ===
        "CoinGecko",             # CoinGecko market updates
        "lookonchain",           # On-chain analytics, whale tracking
        "WhaleAlert",            # Large transaction alerts

        # === Tier 3: Official Channels ===
        "binance_announcements", # Binance official
        "ethereum",              # Ethereum community
    ]

    @abstractmethod
    async def fetch_channel_messages(
        self,
        channel: str,
        symbol: str,
        limit: int = 10,
    ) -> list[TelegramMessage]:
        """
        Fetch recent messages from a Telegram channel mentioning a symbol.

        Args:
            channel: Channel name (without @)
            symbol: Crypto symbol to filter for
            limit: Maximum number of messages

        Returns:
            List of TelegramMessage objects
        """
        pass

    @abstractmethod
    async def fetch_all_channels(
        self,
        symbol: str,
        limit_per_channel: int = 5,
    ) -> list[TelegramMessage]:
        """
        Fetch messages from all target channels.

        Args:
            symbol: Crypto symbol to filter for
            limit_per_channel: Max messages per channel

        Returns:
            Combined list of TelegramMessage objects
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the fetcher connection."""
        pass

    @abstractmethod
    async def is_authenticated(self) -> bool:
        """Check if the fetcher is authenticated."""
        pass


class TelegramFetcher(BaseTelegramFetcher):
    """
    Real Telegram fetcher using Telethon.

    Requires:
    - TELEGRAM_API_ID: Your Telegram API ID
    - TELEGRAM_API_HASH: Your Telegram API hash
    - TELEGRAM_PHONE: Phone number for first-time auth (optional after session created)

    Get credentials at: https://my.telegram.org/apps

    Session files are stored in the bot directory and persist authentication.
    """

    def __init__(
        self,
        api_id: Optional[str] = None,
        api_hash: Optional[str] = None,
        phone: Optional[str] = None,
        session_name: str = "contrarian_bot",
        channels: Optional[List[str]] = None,
    ) -> None:
        """
        Initialize Telegram fetcher.

        Args:
            api_id: Telegram API ID
            api_hash: Telegram API hash
            phone: Phone number for authentication
            session_name: Name for the session file
            channels: Optional list of channels to monitor (overrides defaults)
        """
        self.api_id = int(api_id or os.getenv("TELEGRAM_API_ID", "0"))
        self.api_hash = api_hash or os.getenv("TELEGRAM_API_HASH", "")
        self.phone = phone or os.getenv("TELEGRAM_PHONE", "")
        self.session_name = session_name
        self._client = None
        self._authenticated = False

        # Allow custom channel list
        if channels:
            self.TARGET_CHANNELS = channels

        # Session file path
        bot_dir = Path(__file__).parent.parent.parent
        self._session_path = bot_dir / f"{session_name}.session"

    async def _get_client(self):
        """Get or create the Telethon client."""
        if self._client is None:
            try:
                from telethon import TelegramClient
                from telethon.sessions import StringSession

                # Create client with session file
                self._client = TelegramClient(
                    str(self._session_path.with_suffix("")),  # Without .session extension
                    self.api_id,
                    self.api_hash,
                )

                await self._client.connect()

                # Check if already authorized
                if await self._client.is_user_authorized():
                    self._authenticated = True
                    logger.info("Telegram: Using existing session")
                elif self.phone:
                    # First-time auth - requires phone code
                    logger.warning(
                        "Telegram: Not authenticated. First-time setup requires interactive auth. "
                        "Run 'python -m services.socials.telegram_auth' to authenticate."
                    )
                else:
                    logger.warning(
                        "Telegram: No phone number provided for authentication. "
                        "Set TELEGRAM_PHONE environment variable."
                    )

            except ImportError:
                logger.error("Telethon not installed. Run: pip install Telethon")
                raise
            except Exception as e:
                logger.error(f"Failed to create Telegram client: {e}")
                raise

        return self._client

    async def is_authenticated(self) -> bool:
        """Check if authenticated with Telegram."""
        try:
            client = await self._get_client()
            return await client.is_user_authorized()
        except Exception:
            return False

    async def fetch_channel_messages(
        self,
        channel: str,
        symbol: str,
        limit: int = 10,
    ) -> list[TelegramMessage]:
        """
        Fetch recent messages from a Telegram channel.

        Args:
            channel: Channel username (without @)
            symbol: Crypto symbol to filter for
            limit: Maximum number of messages to fetch

        Returns:
            List of TelegramMessage objects mentioning the symbol
        """
        messages = []

        try:
            client = await self._get_client()

            if not await client.is_user_authorized():
                logger.warning(f"Telegram not authenticated, skipping {channel}")
                return []

            # Normalize symbol for searching
            clean_symbol = symbol.upper().replace("USD", "").replace("USDT", "")
            search_terms = [clean_symbol, f"${clean_symbol}"]

            # Add full name mappings for common coins
            symbol_names = {
                "BTC": ["bitcoin", "btc"],
                "ETH": ["ethereum", "eth"],
                "SOL": ["solana", "sol"],
                "ADA": ["cardano", "ada"],
                "DOT": ["polkadot", "dot"],
                "AVAX": ["avalanche", "avax"],
                "LINK": ["chainlink", "link"],
                "MATIC": ["polygon", "matic"],
                "ATOM": ["cosmos", "atom"],
                "XRP": ["ripple", "xrp"],
            }
            if clean_symbol in symbol_names:
                search_terms.extend(symbol_names[clean_symbol])

            try:
                # Get the channel entity
                entity = await client.get_entity(channel)

                # Fetch recent messages
                async for message in client.iter_messages(
                    entity,
                    limit=limit * 3,  # Fetch more, then filter
                ):
                    if not message.text:
                        continue

                    # Check if message contains the symbol
                    text_lower = message.text.lower()
                    if not any(term.lower() in text_lower for term in search_terms):
                        continue

                    # Get message stats
                    views = message.views or 0
                    forwards = message.forwards or 0

                    messages.append(
                        TelegramMessage(
                            text=message.text[:1000],  # Limit text length
                            channel=channel,
                            timestamp=message.date.replace(tzinfo=timezone.utc),
                            views=views,
                            forwards=forwards,
                            message_id=message.id,
                        )
                    )

                    if len(messages) >= limit:
                        break

                logger.debug(
                    f"Telegram: Fetched {len(messages)} messages from {channel} for {symbol}"
                )

            except Exception as e:
                # Channel might not exist or be private
                logger.warning(f"Telegram: Could not fetch from {channel}: {e}")

        except Exception as e:
            logger.error(f"Telegram fetch error: {e}")

        return messages

    async def fetch_all_channels(
        self,
        symbol: str,
        limit_per_channel: int = 5,
    ) -> list[TelegramMessage]:
        """
        Fetch messages from all target channels.

        Args:
            symbol: Crypto symbol to filter for
            limit_per_channel: Max messages per channel

        Returns:
            Combined list of TelegramMessage objects from all channels
        """
        all_messages = []

        for channel in self.TARGET_CHANNELS:
            try:
                messages = await self.fetch_channel_messages(
                    channel, symbol, limit_per_channel
                )
                all_messages.extend(messages)

                # Small delay between channels to avoid rate limiting
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.warning(f"Telegram: Error fetching from {channel}: {e}")
                continue

        # Sort by timestamp, most recent first
        all_messages.sort(key=lambda m: m.timestamp, reverse=True)

        logger.info(
            f"Telegram: Fetched {len(all_messages)} total messages for {symbol}"
        )
        return all_messages

    async def close(self) -> None:
        """Disconnect from Telegram."""
        if self._client:
            await self._client.disconnect()
            self._client = None
        self._authenticated = False
        logger.debug("Telegram fetcher closed")


class MockTelegramFetcher(BaseTelegramFetcher):
    """
    Mock Telegram fetcher for development and testing.

    Generates realistic sample messages for sentiment pipeline testing.
    """

    # Sample message templates
    SIGNAL_TEMPLATES = [
        "[SIGNAL] {symbol} Buy Entry: ${price:.2f} | Target: +15% | Stop: -5%",
        "[ALERT] {symbol} breaking out! Volume surge detected.",
        "[ANALYSIS] {symbol} technical setup looks bullish. RSI oversold.",
        "[UPDATE] {symbol} approaching key resistance at ${price:.2f}",
        "[WHALE] Large {symbol} accumulation detected on exchanges",
    ]

    NEWS_TEMPLATES = [
        "{symbol} announces major partnership. Price surging!",
        "Breaking: {symbol} integration with major protocol confirmed",
        "{symbol} network upgrade scheduled for next week",
        "Institutional interest in {symbol} continues to grow",
        "Developer activity on {symbol} reaches all-time high",
    ]

    BEARISH_TEMPLATES = [
        "Warning: {symbol} showing weakness on daily chart",
        "{symbol} facing selling pressure at ${price:.2f}",
        "Caution advised for {symbol} - support levels at risk",
        "{symbol} whale wallets moving to exchanges - potential dump",
        "Take profits on {symbol} - overbought conditions",
    ]

    def __init__(self, seed: Optional[int] = None) -> None:
        """
        Initialize mock fetcher.

        Args:
            seed: Random seed for reproducible results
        """
        if seed is not None:
            random.seed(seed)
        self._closed = False

    async def is_authenticated(self) -> bool:
        """Mock is always authenticated."""
        return True

    def _generate_price(self, symbol: str) -> float:
        """Generate a realistic price for a symbol."""
        # Rough price ranges for common coins
        price_ranges = {
            "BTC": (40000, 70000),
            "ETH": (2000, 4000),
            "SOL": (50, 200),
            "ADA": (0.3, 1.0),
            "DOT": (5, 20),
            "AVAX": (20, 60),
            "LINK": (10, 30),
        }
        min_p, max_p = price_ranges.get(symbol, (10, 100))
        return random.uniform(min_p, max_p)

    async def fetch_channel_messages(
        self,
        channel: str,
        symbol: str,
        limit: int = 10,
    ) -> list[TelegramMessage]:
        """
        Generate mock messages for a channel and symbol.

        Args:
            channel: Channel name
            symbol: Crypto symbol
            limit: Max messages to return

        Returns:
            List of mock TelegramMessage objects
        """
        # Normalize symbol
        clean_symbol = symbol.upper()
        if clean_symbol.endswith("USD"):
            clean_symbol = clean_symbol[:-3]

        messages = []
        now = datetime.now(timezone.utc)

        for i in range(min(limit, 5)):
            # Choose template type randomly
            template_type = random.choice(["signal", "signal", "news", "bearish"])

            if template_type == "signal":
                template = random.choice(self.SIGNAL_TEMPLATES)
            elif template_type == "news":
                template = random.choice(self.NEWS_TEMPLATES)
            else:
                template = random.choice(self.BEARISH_TEMPLATES)

            price = self._generate_price(clean_symbol)
            text = template.format(symbol=clean_symbol, price=price)

            # Random engagement
            views = random.randint(100, 10000)
            forwards = random.randint(0, views // 10)

            # Random timestamp within last 2 hours
            minutes_ago = random.randint(1, 120)
            timestamp = now - timedelta(minutes=minutes_ago)

            messages.append(
                TelegramMessage(
                    text=text,
                    channel=channel,
                    timestamp=timestamp,
                    views=views,
                    forwards=forwards,
                    message_id=random.randint(10000, 99999),
                )
            )

        logger.debug(f"[MOCK] Generated {len(messages)} Telegram messages from {channel}")
        return messages

    async def fetch_all_channels(
        self,
        symbol: str,
        limit_per_channel: int = 5,
    ) -> list[TelegramMessage]:
        """
        Fetch from all target channels.

        Args:
            symbol: Crypto symbol
            limit_per_channel: Max messages per channel

        Returns:
            Combined list from all channels
        """
        all_messages = []

        for channel in self.TARGET_CHANNELS:
            messages = await self.fetch_channel_messages(
                channel, symbol, limit_per_channel
            )
            all_messages.extend(messages)

        # Sort by timestamp, most recent first
        all_messages.sort(key=lambda m: m.timestamp, reverse=True)

        logger.debug(f"[MOCK] Generated {len(all_messages)} total Telegram messages")
        return all_messages

    async def close(self) -> None:
        """Close mock fetcher."""
        self._closed = True


def get_telegram_fetcher(use_mock: bool = False) -> BaseTelegramFetcher:
    """
    Factory function to get appropriate Telegram fetcher.

    Args:
        use_mock: Force use of mock fetcher (for testing)

    Returns:
        BaseTelegramFetcher instance (real or mock based on config)
    """
    if use_mock:
        logger.info("Using mock Telegram fetcher (forced)")
        return MockTelegramFetcher()

    api_id = os.getenv("TELEGRAM_API_ID", "")
    api_hash = os.getenv("TELEGRAM_API_HASH", "")

    if api_id and api_hash:
        logger.info("Telegram credentials found, using real fetcher")
        return TelegramFetcher()
    else:
        logger.info("No Telegram credentials - using mock fetcher")
        return MockTelegramFetcher()


# Global fetcher instance
_telegram_fetcher: Optional[BaseTelegramFetcher] = None


def get_or_create_telegram_fetcher() -> BaseTelegramFetcher:
    """Get or create the global Telegram fetcher instance."""
    global _telegram_fetcher
    if _telegram_fetcher is None:
        _telegram_fetcher = get_telegram_fetcher()
    return _telegram_fetcher


async def close_telegram_fetcher() -> None:
    """Close the global Telegram fetcher."""
    global _telegram_fetcher
    if _telegram_fetcher is not None:
        await _telegram_fetcher.close()
        _telegram_fetcher = None

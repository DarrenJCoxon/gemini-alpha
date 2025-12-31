"""
Test fixtures for sentiment data.

This module provides sample data for testing the sentiment ingestor,
including LunarCrush API responses, Bluesky posts, and Telegram messages.

Based on Story 1.4: Sentiment Ingestor requirements.
"""

from datetime import datetime, timezone, timedelta
from typing import Any


# Sample LunarCrush API v4 response
SAMPLE_LUNARCRUSH_RESPONSE: dict[str, Any] = {
    "data": {
        "symbol": "SOL",
        "name": "Solana",
        "galaxy_score": 67,
        "alt_rank": 12,
        "social_volume": 15234,
        "social_score": 72,
        "market_dominance": 2.1,
        "sentiment": {
            "bullish": 0.65,
            "bearish": 0.35,
        },
        "price": 98.50,
        "price_change_24h": 3.5,
        "volume_24h": 1500000000,
    }
}


# Sample Bluesky posts
SAMPLE_BLUESKY_POSTS: list[dict[str, Any]] = [
    {
        "text": "SOL is looking extremely bullish right now! Breaking out of resistance.",
        "author": "cryptotrader.bsky.social",
        "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
        "likes": 245,
        "reposts": 42,
        "uri": "at://cryptotrader.bsky.social/app.bsky.feed.post/1234",
    },
    {
        "text": "Just added more SOL to my portfolio. This one is going to moon!",
        "author": "hodler4life.bsky.social",
        "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat(),
        "likes": 128,
        "reposts": 18,
        "uri": "at://hodler4life.bsky.social/app.bsky.feed.post/5678",
    },
    {
        "text": "Technical analysis shows SOL ready for a major move up.",
        "author": "trading_guru.bsky.social",
        "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(),
        "likes": 312,
        "reposts": 67,
        "uri": "at://trading_guru.bsky.social/app.bsky.feed.post/9012",
    },
    {
        "text": "Warning: SOL showing some weakness on the 4H chart. Be careful.",
        "author": "market_watch.bsky.social",
        "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat(),
        "likes": 89,
        "reposts": 12,
        "uri": "at://market_watch.bsky.social/app.bsky.feed.post/3456",
    },
]


# Sample Telegram messages
SAMPLE_TELEGRAM_MESSAGES: list[dict[str, Any]] = [
    {
        "text": "[SIGNAL] SOL Buy Entry: $98.50 | Target: +15% | Stop: -5%",
        "channel": "@CryptoSignals",
        "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
        "views": 5420,
        "forwards": 128,
        "message_id": 45678,
    },
    {
        "text": "[ALERT] SOL breaking out! Volume surge detected.",
        "channel": "@WhaleTrades",
        "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat(),
        "views": 8912,
        "forwards": 256,
        "message_id": 45679,
    },
    {
        "text": "[ANALYSIS] SOL technical setup looks bullish. RSI oversold.",
        "channel": "@CryptoNews",
        "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=35)).isoformat(),
        "views": 3245,
        "forwards": 45,
        "message_id": 45680,
    },
    {
        "text": "Institutional interest in SOL continues to grow.",
        "channel": "@AltcoinDaily",
        "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=50)).isoformat(),
        "views": 6789,
        "forwards": 178,
        "message_id": 45681,
    },
    {
        "text": "Caution advised for SOL - overbought conditions on daily.",
        "channel": "@TradingAlerts",
        "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat(),
        "views": 2134,
        "forwards": 34,
        "message_id": 45682,
    },
]


# Sample aggregated sentiment data
SAMPLE_AGGREGATED_SENTIMENT: dict[str, Any] = {
    "symbol": "SOLUSD",
    "lunarcrush": {
        "galaxy_score": 67,
        "alt_rank": 12,
        "social_volume": 15234,
        "social_score": 72,
        "bullish_sentiment": 0.65,
        "bearish_sentiment": 0.35,
        "symbol": "sol",
    },
    "bluesky_posts": SAMPLE_BLUESKY_POSTS,
    "telegram_messages": SAMPLE_TELEGRAM_MESSAGES,
    "aggregated_score": 68,
    "galaxy_score": 67,
    "alt_rank": 12,
    "social_volume": 15234,
}


def generate_mock_lunarcrush_metrics(
    galaxy_score: int = 67,
    alt_rank: int = 12,
    social_volume: int = 15000,
    symbol: str = "sol",
) -> dict[str, Any]:
    """
    Generate mock LunarCrush metrics.

    Args:
        galaxy_score: Galaxy Score (0-100)
        alt_rank: AltRank position
        social_volume: Social media volume
        symbol: Symbol name

    Returns:
        Dict matching LunarCrushMetrics.to_dict() format
    """
    bullish = 0.5 + (galaxy_score - 50) / 100
    bullish = max(0.1, min(0.9, bullish))

    return {
        "galaxy_score": galaxy_score,
        "alt_rank": alt_rank,
        "social_volume": social_volume,
        "social_score": int(galaxy_score * 1.1),
        "bullish_sentiment": round(bullish, 2),
        "bearish_sentiment": round(1.0 - bullish, 2),
        "symbol": symbol,
    }


def generate_mock_bluesky_posts(
    symbol: str = "SOL",
    count: int = 5,
    sentiment: str = "mixed",
) -> list[dict[str, Any]]:
    """
    Generate mock Bluesky posts for testing.

    Args:
        symbol: Crypto symbol
        count: Number of posts
        sentiment: "bullish", "bearish", or "mixed"

    Returns:
        List of post dicts
    """
    bullish_templates = [
        f"{symbol} is looking extremely bullish right now!",
        f"Just added more {symbol} to my portfolio.",
        f"Technical analysis shows {symbol} ready for a major move up.",
    ]

    bearish_templates = [
        f"Warning: {symbol} showing weakness.",
        f"Taking profits on {symbol}. Looks overbought.",
        f"Not sure about {symbol} at these prices.",
    ]

    neutral_templates = [
        f"{symbol} consolidating at current levels.",
        f"Interesting development for {symbol} today.",
        f"What do you think about {symbol}?",
    ]

    posts = []
    now = datetime.now(timezone.utc)

    for i in range(count):
        if sentiment == "bullish":
            text = bullish_templates[i % len(bullish_templates)]
        elif sentiment == "bearish":
            text = bearish_templates[i % len(bearish_templates)]
        else:
            # Mixed - alternate
            if i % 3 == 0:
                text = bullish_templates[i % len(bullish_templates)]
            elif i % 3 == 1:
                text = bearish_templates[i % len(bearish_templates)]
            else:
                text = neutral_templates[i % len(neutral_templates)]

        posts.append({
            "text": text,
            "author": f"user{i}.bsky.social",
            "timestamp": (now - timedelta(minutes=i * 10)).isoformat(),
            "likes": 50 + i * 20,
            "reposts": 5 + i * 3,
            "uri": f"at://user{i}.bsky.social/app.bsky.feed.post/{i}",
        })

    return posts


def generate_mock_telegram_messages(
    symbol: str = "SOL",
    count: int = 5,
    include_signals: bool = True,
) -> list[dict[str, Any]]:
    """
    Generate mock Telegram messages for testing.

    Args:
        symbol: Crypto symbol
        count: Number of messages
        include_signals: Whether to include trading signals

    Returns:
        List of message dicts
    """
    channels = ["@CryptoNews", "@WhaleTrades", "@AltcoinDaily", "@TradingAlerts"]

    signal_templates = [
        f"[SIGNAL] {symbol} Buy Entry: $100 | Target: +15% | Stop: -5%",
        f"[ALERT] {symbol} breaking out! Volume surge detected.",
    ]

    news_templates = [
        f"{symbol} announces major partnership. Price surging!",
        f"Developer activity on {symbol} reaches all-time high.",
        f"Institutional interest in {symbol} continues to grow.",
    ]

    messages = []
    now = datetime.now(timezone.utc)

    for i in range(count):
        if include_signals and i < 2:
            text = signal_templates[i % len(signal_templates)]
        else:
            text = news_templates[i % len(news_templates)]

        messages.append({
            "text": text,
            "channel": channels[i % len(channels)],
            "timestamp": (now - timedelta(minutes=i * 15)).isoformat(),
            "views": 1000 + i * 500,
            "forwards": 50 + i * 20,
            "message_id": 10000 + i,
        })

    return messages


# Galaxy Score interpretation (from PRD)
GALAXY_SCORE_INTERPRETATION = {
    (0, 20): {"label": "Extreme Fear", "action": "BUY signal potential"},
    (21, 40): {"label": "Fear", "action": "Monitor closely"},
    (41, 60): {"label": "Neutral", "action": "No action"},
    (61, 80): {"label": "Greed", "action": "Caution"},
    (81, 100): {"label": "Extreme Greed", "action": "SELL signal potential"},
}


def interpret_galaxy_score(score: int) -> dict[str, str]:
    """
    Interpret a Galaxy Score according to PRD guidelines.

    Args:
        score: Galaxy Score (0-100)

    Returns:
        Dict with 'label' and 'action'
    """
    for (low, high), interpretation in GALAXY_SCORE_INTERPRETATION.items():
        if low <= score <= high:
            return interpretation

    return {"label": "Unknown", "action": "Error in score"}

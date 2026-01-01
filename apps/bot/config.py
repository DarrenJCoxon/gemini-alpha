"""
Configuration management for the Contrarian AI Trading Bot.

This module provides centralized configuration loading from environment
variables with validation and sensible defaults.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class DatabaseConfig:
    """Database connection configuration."""

    url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    pool_size: int = field(
        default_factory=lambda: int(os.getenv("DATABASE_POOL_SIZE", "10"))
    )
    debug: bool = field(
        default_factory=lambda: os.getenv("DEBUG", "").lower() == "true"
    )

    def get_async_url(self) -> str:
        """Convert URL to async-compatible format."""
        url = self.url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


@dataclass
class KrakenConfig:
    """Kraken API configuration."""

    api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("KRAKEN_API_KEY")
    )
    api_secret: Optional[str] = field(
        default_factory=lambda: os.getenv("KRAKEN_API_SECRET")
    )
    # Private key for trading operations (Story 3.1)
    private_key: Optional[str] = field(
        default_factory=lambda: os.getenv("KRAKEN_PRIVATE_KEY")
    )
    # Sandbox mode for testing without real orders (Story 3.1)
    sandbox_mode: bool = field(
        default_factory=lambda: os.getenv("KRAKEN_SANDBOX_MODE", "true").lower() == "true"
    )
    rate_limit_ms: int = field(
        default_factory=lambda: int(os.getenv("KRAKEN_RATE_LIMIT_MS", "500"))
    )
    enable_rate_limit: bool = True
    retry_count: int = 3
    retry_min_wait: int = 2
    retry_max_wait: int = 10

    def validate_trading_credentials(self) -> None:
        """
        Validate that trading credentials are configured when not in sandbox mode.

        Raises:
            ValueError: If credentials are missing and sandbox_mode is False
        """
        if not self.sandbox_mode:
            if not self.api_key or not self.api_secret:
                raise ValueError(
                    "KRAKEN_API_KEY and KRAKEN_API_SECRET are required when "
                    "KRAKEN_SANDBOX_MODE is set to 'false'. Cannot execute real "
                    "trades without valid API credentials."
                )
            if not self.private_key:
                raise ValueError(
                    "KRAKEN_PRIVATE_KEY is required when KRAKEN_SANDBOX_MODE is "
                    "set to 'false'. Cannot sign trading orders without private key."
                )


@dataclass
class LunarCrushConfig:
    """LunarCrush API configuration."""

    api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("LUNARCRUSH_API_KEY")
    )
    # Free tier: 300 calls/day, Pro: 10000 calls/day
    daily_limit: int = field(
        default_factory=lambda: int(os.getenv("LUNARCRUSH_DAILY_LIMIT", "300"))
    )
    # Number of groups for rotation strategy (to stay within API limits)
    rotation_groups: int = field(
        default_factory=lambda: int(os.getenv("LUNARCRUSH_ROTATION_GROUPS", "3"))
    )


@dataclass
class SocialConfig:
    """Social media API configuration."""

    # Bluesky
    bluesky_handle: Optional[str] = field(
        default_factory=lambda: os.getenv("BLUESKY_HANDLE")
    )
    bluesky_password: Optional[str] = field(
        default_factory=lambda: os.getenv("BLUESKY_PASSWORD")
    )

    # Telegram
    telegram_api_id: Optional[str] = field(
        default_factory=lambda: os.getenv("TELEGRAM_API_ID")
    )
    telegram_api_hash: Optional[str] = field(
        default_factory=lambda: os.getenv("TELEGRAM_API_HASH")
    )
    telegram_phone: Optional[str] = field(
        default_factory=lambda: os.getenv("TELEGRAM_PHONE")
    )


@dataclass
class SchedulerConfig:
    """APScheduler configuration."""

    timezone: str = "UTC"
    # Cron expression for 15-minute intervals: 0, 15, 30, 45 minutes
    ingest_cron_minutes: str = "0,15,30,45"
    # Run immediate ingestion on startup
    run_on_startup: bool = field(
        default_factory=lambda: os.getenv("RUN_INGESTION_ON_STARTUP", "false").lower() == "true"
    )
    # Run sentiment ingestion on startup
    run_sentiment_on_startup: bool = field(
        default_factory=lambda: os.getenv("RUN_SENTIMENT_ON_STARTUP", "false").lower() == "true"
    )


@dataclass
class VertexAIConfig:
    """Google Vertex AI configuration for LangGraph agents (Story 2.1)."""

    project_id: Optional[str] = field(
        default_factory=lambda: os.getenv("GOOGLE_CLOUD_PROJECT")
    )
    location: str = field(
        default_factory=lambda: os.getenv("VERTEX_AI_LOCATION", "us-central1")
    )
    credentials_path: Optional[str] = field(
        default_factory=lambda: os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    )
    # Model selection for agents (fallback to GEMINI_MODEL)
    model_name: str = field(
        default_factory=lambda: os.getenv("VERTEX_AI_MODEL", os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite"))
    )
    # Temperature for agent responses (lower = more deterministic)
    temperature: float = field(
        default_factory=lambda: float(os.getenv("VERTEX_AI_TEMPERATURE", "0.1"))
    )
    # Maximum tokens for responses
    max_output_tokens: int = field(
        default_factory=lambda: int(os.getenv("VERTEX_AI_MAX_TOKENS", "2048"))
    )

    def is_configured(self) -> bool:
        """Check if Vertex AI is properly configured."""
        return self.project_id is not None and len(self.project_id) > 0


@dataclass
class GeminiConfig:
    """
    Google Gemini AI configuration for Sentiment Analysis (Story 2.2).

    Uses the google-generativeai library (not Vertex AI) for faster,
    cost-effective text analysis with Gemini Flash models.
    """

    api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("GOOGLE_AI_API_KEY")
    )
    # Gemini Flash model for sentiment analysis (fast and cost-effective)
    model_name: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    )
    # Low temperature for consistent sentiment analysis
    temperature: float = field(
        default_factory=lambda: float(os.getenv("GEMINI_TEMPERATURE", "0.3"))
    )
    # Maximum tokens for sentiment responses
    max_output_tokens: int = field(
        default_factory=lambda: int(os.getenv("GEMINI_MAX_TOKENS", "1024"))
    )

    def is_configured(self) -> bool:
        """Check if Gemini API is properly configured."""
        return self.api_key is not None and len(self.api_key) > 0


def get_gemini_flash_model():
    """
    Get configured Gemini Flash model for text/sentiment analysis.

    Uses google-generativeai library with Gemini Flash for fast,
    cost-effective sentiment analysis in the Council of Agents.

    Returns:
        Configured GenerativeModel instance

    Raises:
        ValueError: If GOOGLE_AI_API_KEY is not set
    """
    import google.generativeai as genai

    gemini_config = GeminiConfig()

    if not gemini_config.is_configured():
        raise ValueError("GOOGLE_AI_API_KEY not set")

    genai.configure(api_key=gemini_config.api_key)

    # Gemini Flash - optimized for fast text analysis
    model = genai.GenerativeModel(
        model_name=gemini_config.model_name,
        generation_config={
            "temperature": gemini_config.temperature,
            "max_output_tokens": gemini_config.max_output_tokens,
        }
    )
    return model


@dataclass
class RiskConfig:
    """
    Risk management configuration for ATR-based stop loss (Story 3.2).

    Controls dynamic stop loss calculation parameters:
    - ATR period and multiplier for volatility-adjusted stops
    - Min/max stop loss bounds for safety
    - Default risk percentage for position sizing
    """

    # ATR calculation period (default: 14 - industry standard)
    atr_period: int = field(
        default_factory=lambda: int(os.getenv("RISK_ATR_PERIOD", "14"))
    )
    # ATR multiplier for stop loss distance (default: 2.0)
    atr_multiplier: float = field(
        default_factory=lambda: float(os.getenv("RISK_ATR_MULTIPLIER", "2.0"))
    )
    # Maximum stop loss as percentage of entry (default: 20%)
    max_stop_loss_percentage: float = field(
        default_factory=lambda: float(os.getenv("RISK_MAX_STOP_LOSS_PERCENTAGE", "0.20"))
    )
    # Minimum stop loss as percentage of entry (default: 2%)
    min_stop_loss_percentage: float = field(
        default_factory=lambda: float(os.getenv("RISK_MIN_STOP_LOSS_PERCENTAGE", "0.02"))
    )
    # Default risk percentage per trade for position sizing (default: 2%)
    default_risk_per_trade: float = field(
        default_factory=lambda: float(os.getenv("RISK_DEFAULT_PER_TRADE", "0.02"))
    )

    def validate(self) -> None:
        """
        Validate risk configuration values.

        Raises:
            ValueError: If configuration values are invalid
        """
        if self.atr_period < 1:
            raise ValueError(f"ATR period must be >= 1, got {self.atr_period}")

        if self.atr_multiplier <= 0:
            raise ValueError(f"ATR multiplier must be > 0, got {self.atr_multiplier}")

        if not (0 < self.min_stop_loss_percentage <= self.max_stop_loss_percentage <= 1.0):
            raise ValueError(
                f"Invalid stop loss bounds: min={self.min_stop_loss_percentage}, "
                f"max={self.max_stop_loss_percentage}. Must be 0 < min <= max <= 1.0"
            )

        if not (0 < self.default_risk_per_trade <= 0.10):
            raise ValueError(
                f"Default risk per trade must be between 0% and 10%, "
                f"got {self.default_risk_per_trade * 100}%"
            )


@dataclass
class RegimeConfig:
    """
    Market regime detection configuration (Story 5.1).

    Controls how market regime is detected and how thresholds
    are adjusted for each regime.
    """

    # DMA periods
    fast_ma_period: int = field(
        default_factory=lambda: int(os.getenv("REGIME_FAST_MA_PERIOD", "50"))
    )
    slow_ma_period: int = field(
        default_factory=lambda: int(os.getenv("REGIME_SLOW_MA_PERIOD", "200"))
    )

    # Position size multipliers per regime
    bull_position_multiplier: float = field(
        default_factory=lambda: float(os.getenv("REGIME_BULL_POSITION_MULT", "1.0"))
    )
    bear_position_multiplier: float = field(
        default_factory=lambda: float(os.getenv("REGIME_BEAR_POSITION_MULT", "0.5"))
    )
    chop_position_multiplier: float = field(
        default_factory=lambda: float(os.getenv("REGIME_CHOP_POSITION_MULT", "0.25"))
    )

    # Fear thresholds per regime (fear must be BELOW this to buy)
    bull_fear_threshold: int = field(
        default_factory=lambda: int(os.getenv("REGIME_BULL_FEAR_THRESHOLD", "30"))
    )
    bear_fear_threshold: int = field(
        default_factory=lambda: int(os.getenv("REGIME_BEAR_FEAR_THRESHOLD", "20"))
    )
    chop_fear_threshold: int = field(
        default_factory=lambda: int(os.getenv("REGIME_CHOP_FEAR_THRESHOLD", "15"))
    )

    def validate(self) -> None:
        """
        Validate regime configuration values.

        Raises:
            ValueError: If configuration values are invalid
        """
        if self.fast_ma_period <= 0:
            raise ValueError(f"Fast MA period must be > 0, got {self.fast_ma_period}")

        if self.slow_ma_period <= self.fast_ma_period:
            raise ValueError(
                f"Slow MA period ({self.slow_ma_period}) must be > "
                f"fast MA period ({self.fast_ma_period})"
            )

        for multiplier_name, value in [
            ("bull", self.bull_position_multiplier),
            ("bear", self.bear_position_multiplier),
            ("chop", self.chop_position_multiplier),
        ]:
            if not (0.0 < value <= 1.0):
                raise ValueError(
                    f"{multiplier_name} position multiplier must be between 0 and 1, "
                    f"got {value}"
                )

        for threshold_name, value in [
            ("bull", self.bull_fear_threshold),
            ("bear", self.bear_fear_threshold),
            ("chop", self.chop_fear_threshold),
        ]:
            if not (0 <= value <= 100):
                raise ValueError(
                    f"{threshold_name} fear threshold must be between 0 and 100, "
                    f"got {value}"
                )


@dataclass
class GeminiVisionConfig:
    """
    Google Gemini Pro Vision configuration for Chart Analysis (Story 2.3).

    Uses the google-generativeai library with Gemini Pro for
    visual chart pattern recognition and scam wick detection.
    """

    api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("GOOGLE_AI_API_KEY")
    )
    # Gemini model for vision analysis (uses GEMINI_MODEL by default)
    model_name: str = field(
        default_factory=lambda: os.getenv("GEMINI_VISION_MODEL", os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite"))
    )
    # Very low temperature for consistent chart analysis
    temperature: float = field(
        default_factory=lambda: float(os.getenv("GEMINI_VISION_TEMPERATURE", "0.2"))
    )
    # Maximum tokens for vision responses
    max_output_tokens: int = field(
        default_factory=lambda: int(os.getenv("GEMINI_VISION_MAX_TOKENS", "2048"))
    )

    def is_configured(self) -> bool:
        """Check if Gemini Vision API is properly configured."""
        return self.api_key is not None and len(self.api_key) > 0


def get_gemini_pro_vision_model():
    """
    Get configured Gemini Pro model for vision/chart analysis.

    Uses google-generativeai library with Gemini Pro for
    complex visual chart pattern recognition in the Vision Agent.

    Story 2.3: Vision Agent & Chart Generation

    Returns:
        Configured GenerativeModel instance

    Raises:
        ValueError: If GOOGLE_AI_API_KEY is not set
    """
    import google.generativeai as genai

    vision_config = GeminiVisionConfig()

    if not vision_config.is_configured():
        raise ValueError("GOOGLE_AI_API_KEY not set")

    genai.configure(api_key=vision_config.api_key)

    # Gemini Pro - optimized for complex visual analysis
    model = genai.GenerativeModel(
        model_name=vision_config.model_name,
        generation_config={
            "temperature": vision_config.temperature,
            "max_output_tokens": vision_config.max_output_tokens,
        }
    )
    return model


@dataclass
class Config:
    """Main application configuration."""

    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    kraken: KrakenConfig = field(default_factory=KrakenConfig)
    lunarcrush: LunarCrushConfig = field(default_factory=LunarCrushConfig)
    social: SocialConfig = field(default_factory=SocialConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    vertex_ai: VertexAIConfig = field(default_factory=VertexAIConfig)
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    gemini_vision: GeminiVisionConfig = field(default_factory=GeminiVisionConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    regime: RegimeConfig = field(default_factory=RegimeConfig)  # Story 5.1
    web_url: str = field(default_factory=lambda: os.getenv("WEB_URL", ""))
    debug: bool = field(
        default_factory=lambda: os.getenv("DEBUG", "").lower() == "true"
    )


# Global configuration instance
config = Config()


def get_config() -> Config:
    """Get the global configuration instance."""
    return config

"""
Configuration management for the Contrarian AI Trading Bot.

This module provides centralized configuration loading from environment
variables with validation and sensible defaults.
"""

import os
from dataclasses import dataclass, field
from typing import Optional, List

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
class OnChainConfig:
    """
    On-chain data provider configuration (Story 5.6).

    Integrates on-chain metrics like exchange flows, whale activity,
    stablecoin reserves, and funding rates for deeper market insight.
    """

    # CryptoQuant API (primary provider - best free tier)
    cryptoquant_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("CRYPTOQUANT_API_KEY")
    )

    # Santiment API (backup provider)
    santiment_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("SANTIMENT_API_KEY")
    )

    # Glassnode API (premium provider)
    glassnode_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("GLASSNODE_API_KEY")
    )

    # Cache settings
    cache_ttl_minutes: int = field(
        default_factory=lambda: int(os.getenv("ONCHAIN_CACHE_TTL_MINUTES", "15"))
    )

    # Data fetch settings
    lookback_days: int = field(
        default_factory=lambda: int(os.getenv("ONCHAIN_LOOKBACK_DAYS", "7"))
    )

    # Thresholds for signals
    exchange_flow_spike_mult: float = field(
        default_factory=lambda: float(os.getenv("EXCHANGE_FLOW_SPIKE_MULT", "2.0"))
    )
    whale_activity_threshold: int = field(
        default_factory=lambda: int(os.getenv("WHALE_ACTIVITY_THRESHOLD", "100"))
    )  # Number of large transactions
    funding_rate_extreme_threshold: float = field(
        default_factory=lambda: float(os.getenv("FUNDING_RATE_EXTREME_THRESHOLD", "0.1"))
    )  # 0.1% per 8 hours is extreme

    def is_configured(self) -> bool:
        """Check if any on-chain provider is configured."""
        return any([
            self.cryptoquant_api_key,
            self.santiment_api_key,
            self.glassnode_api_key
        ])


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
class EnhancedRiskConfig:
    """
    Enhanced risk management configuration (Story 5.5).

    Tighter parameters for capital preservation:
    - Maximum portfolio drawdown (reduced from 20% to 15%)
    - Per-trade risk (reduced from 2% to 1.5%)
    - Maximum single position size (10%)
    - Maximum correlated exposure (30%)
    - Daily loss limit (5%)
    """

    # Maximum Portfolio Drawdown (reduced from 20% to 15%)
    max_drawdown_pct: float = field(
        default_factory=lambda: float(os.getenv("MAX_DRAWDOWN_PCT", "15.0"))
    )

    # Per-Trade Risk (reduced from 2% to 1.5%)
    per_trade_risk_pct: float = field(
        default_factory=lambda: float(os.getenv("PER_TRADE_RISK_PCT", "1.5"))
    )

    # Maximum Single Position Size (new)
    max_single_position_pct: float = field(
        default_factory=lambda: float(os.getenv("MAX_SINGLE_POSITION_PCT", "10.0"))
    )

    # Maximum Correlated Exposure (new)
    max_correlated_exposure_pct: float = field(
        default_factory=lambda: float(os.getenv("MAX_CORRELATED_EXPOSURE_PCT", "30.0"))
    )

    # Correlation threshold to consider assets "correlated"
    correlation_threshold: float = field(
        default_factory=lambda: float(os.getenv("CORRELATION_THRESHOLD", "0.7"))
    )

    # Alert threshold (percentage of limit)
    alert_threshold_pct: float = field(
        default_factory=lambda: float(os.getenv("RISK_ALERT_THRESHOLD_PCT", "80.0"))
    )

    # Daily loss limit (stop trading for day if reached)
    daily_loss_limit_pct: float = field(
        default_factory=lambda: float(os.getenv("DAILY_LOSS_LIMIT_PCT", "5.0"))
    )

    # Existing ATR-based stop loss settings
    atr_period: int = field(
        default_factory=lambda: int(os.getenv("RISK_ATR_PERIOD", "14"))
    )
    atr_multiplier: float = field(
        default_factory=lambda: float(os.getenv("RISK_ATR_MULTIPLIER", "2.0"))
    )
    max_stop_loss_pct: float = field(
        default_factory=lambda: float(os.getenv("RISK_MAX_STOP_LOSS_PCT", "15.0"))
    )
    min_stop_loss_pct: float = field(
        default_factory=lambda: float(os.getenv("RISK_MIN_STOP_LOSS_PCT", "2.0"))
    )

    def validate(self) -> None:
        """Validate risk configuration values."""
        if not (1.0 <= self.max_drawdown_pct <= 50.0):
            raise ValueError(f"Max drawdown must be 1-50%, got {self.max_drawdown_pct}")

        if not (0.1 <= self.per_trade_risk_pct <= 5.0):
            raise ValueError(f"Per-trade risk must be 0.1-5%, got {self.per_trade_risk_pct}")

        if not (1.0 <= self.max_single_position_pct <= 25.0):
            raise ValueError(f"Max position must be 1-25%, got {self.max_single_position_pct}")

        if not (10.0 <= self.max_correlated_exposure_pct <= 100.0):
            raise ValueError(f"Correlated exposure must be 10-100%, got {self.max_correlated_exposure_pct}")

        if not (1.0 <= self.daily_loss_limit_pct <= 20.0):
            raise ValueError(f"Daily loss limit must be 1-20%, got {self.daily_loss_limit_pct}")

        if not (0.5 <= self.correlation_threshold <= 1.0):
            raise ValueError(f"Correlation threshold must be 0.5-1.0, got {self.correlation_threshold}")

        if not (50.0 <= self.alert_threshold_pct <= 99.0):
            raise ValueError(f"Alert threshold must be 50-99%, got {self.alert_threshold_pct}")


@dataclass
class ScannerConfig:
    """
    Dynamic Opportunity Scanner configuration (Story 5.8).

    Scans all Kraken USD pairs hourly to discover contrarian opportunities.
    """

    # Enable/disable scanner
    enabled: bool = field(
        default_factory=lambda: os.getenv("SCANNER_ENABLED", "true").lower() == "true"
    )

    # Minimum 24h volume in USD to consider a pair
    min_volume_usd: float = field(
        default_factory=lambda: float(os.getenv("SCANNER_MIN_VOLUME", "1000000"))
    )

    # Maximum assets to include in active universe
    universe_size: int = field(
        default_factory=lambda: int(os.getenv("SCANNER_UNIVERSE_SIZE", "10"))
    )

    # Minimum score threshold to include in universe
    min_score: float = field(
        default_factory=lambda: float(os.getenv("SCANNER_MIN_SCORE", "40"))
    )

    # Score weights (must sum to ~82 for full score before liquidity bonus)
    weight_rsi_oversold: float = field(
        default_factory=lambda: float(os.getenv("SCANNER_WEIGHT_RSI", "15"))
    )
    weight_price_capitulation: float = field(
        default_factory=lambda: float(os.getenv("SCANNER_WEIGHT_CAPITULATION", "15"))
    )
    weight_volume_spike: float = field(
        default_factory=lambda: float(os.getenv("SCANNER_WEIGHT_VOLUME_SPIKE", "12"))
    )
    weight_adx_weak: float = field(
        default_factory=lambda: float(os.getenv("SCANNER_WEIGHT_ADX", "12"))
    )
    weight_bollinger_lower: float = field(
        default_factory=lambda: float(os.getenv("SCANNER_WEIGHT_BOLLINGER", "12"))
    )
    weight_vwap_discount: float = field(
        default_factory=lambda: float(os.getenv("SCANNER_WEIGHT_VWAP", "6"))
    )
    weight_liquidity_bonus: float = field(
        default_factory=lambda: float(os.getenv("SCANNER_WEIGHT_LIQUIDITY", "10"))
    )

    # Technical thresholds
    rsi_oversold_threshold: float = field(
        default_factory=lambda: float(os.getenv("SCANNER_RSI_THRESHOLD", "30"))
    )
    capitulation_threshold_pct: float = field(
        default_factory=lambda: float(os.getenv("SCANNER_CAPITULATION_PCT", "10"))
    )
    volume_spike_mult: float = field(
        default_factory=lambda: float(os.getenv("SCANNER_VOLUME_SPIKE_MULT", "2.0"))
    )
    adx_weak_threshold: float = field(
        default_factory=lambda: float(os.getenv("SCANNER_ADX_THRESHOLD", "25"))
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
class MultiFactorConfig:
    """
    Multi-Factor Confirmation System configuration (Story 5.3).

    Controls the minimum number of factors required for BUY/SELL signals:
    - BUY: Requires 3+ of 6 factors (conservative)
    - SELL: Requires 2+ of 5 factors (protective)
    """

    # Minimum factors required for BUY signal (default: 3 of 6)
    min_factors_buy: int = field(
        default_factory=lambda: int(os.getenv("MULTI_FACTOR_MIN_BUY", "3"))
    )

    # Minimum factors required for SELL signal (default: 2 of 5)
    min_factors_sell: int = field(
        default_factory=lambda: int(os.getenv("MULTI_FACTOR_MIN_SELL", "2"))
    )

    def validate(self) -> None:
        """Validate multi-factor configuration values."""
        if not (1 <= self.min_factors_buy <= 6):
            raise ValueError(f"min_factors_buy must be 1-6, got {self.min_factors_buy}")
        if not (1 <= self.min_factors_sell <= 5):
            raise ValueError(f"min_factors_sell must be 1-5, got {self.min_factors_sell}")


@dataclass
class BasketConfig:
    """
    Basket Trading System configuration (Story 5.9).

    Controls portfolio-level position management:
    - Maximum concurrent positions (10)
    - Correlation limits between basket members
    - Position rotation rules
    - Balanced thresholds (not too contrarian)

    Philosophy: Catch reversals that HOLD, not falling knives.
    """

    # Maximum number of concurrent positions
    max_positions: int = field(
        default_factory=lambda: int(os.getenv("BASKET_MAX_POSITIONS", "10"))
    )

    # Minimum positions to maintain (avoid concentration)
    min_positions: int = field(
        default_factory=lambda: int(os.getenv("BASKET_MIN_POSITIONS", "3"))
    )

    # Maximum allocation to single position (% of portfolio)
    max_single_position_pct: float = field(
        default_factory=lambda: float(os.getenv("BASKET_MAX_SINGLE_PCT", "15.0"))
    )

    # Maximum correlation between basket members (0-1)
    max_correlation: float = field(
        default_factory=lambda: float(os.getenv("BASKET_MAX_CORRELATION", "0.7"))
    )

    # Correlation lookback period (days)
    correlation_lookback_days: int = field(
        default_factory=lambda: int(os.getenv("BASKET_CORRELATION_DAYS", "30"))
    )

    # Position rotation: minimum holding period (hours) before considering exit
    min_hold_hours: int = field(
        default_factory=lambda: int(os.getenv("BASKET_MIN_HOLD_HOURS", "4"))
    )

    # Position rotation: max age before forced review (hours)
    max_position_age_hours: int = field(
        default_factory=lambda: int(os.getenv("BASKET_MAX_AGE_HOURS", "168"))
    )  # 7 days

    # Enable hourly council (aligned with scanner) vs 15-min
    hourly_council_enabled: bool = field(
        default_factory=lambda: os.getenv("BASKET_HOURLY_COUNCIL", "true").lower() == "true"
    )

    # =============================================================================
    # BALANCED THRESHOLDS (Not Too Contrarian)
    # =============================================================================

    # Fear & Greed thresholds (relaxed from 25/75 to 40/60)
    fear_threshold_buy: int = field(
        default_factory=lambda: int(os.getenv("BASKET_FEAR_BUY", "40"))
    )  # Was 25 - too extreme
    greed_threshold_sell: int = field(
        default_factory=lambda: int(os.getenv("BASKET_GREED_SELL", "60"))
    )  # Was 75 - too extreme

    # RSI thresholds (relaxed from 30/70 to 35/65)
    rsi_oversold: int = field(
        default_factory=lambda: int(os.getenv("BASKET_RSI_OVERSOLD", "35"))
    )  # Was 30
    rsi_overbought: int = field(
        default_factory=lambda: int(os.getenv("BASKET_RSI_OVERBOUGHT", "65"))
    )  # Was 70

    # ADX threshold (increased to allow trending markets)
    adx_max_for_entry: int = field(
        default_factory=lambda: int(os.getenv("BASKET_ADX_MAX", "40"))
    )  # Was 25 - rejected trending markets

    # =============================================================================
    # REVERSAL CONFIRMATION REQUIREMENTS
    # =============================================================================

    # Require MACD bullish crossover for BUY
    require_macd_confirmation: bool = field(
        default_factory=lambda: os.getenv("BASKET_REQUIRE_MACD", "true").lower() == "true"
    )

    # Require higher-low pattern (price above prior swing low)
    require_higher_low: bool = field(
        default_factory=lambda: os.getenv("BASKET_REQUIRE_HIGHER_LOW", "true").lower() == "true"
    )

    # Minimum candles since reversal to confirm it's holding
    reversal_confirmation_candles: int = field(
        default_factory=lambda: int(os.getenv("BASKET_REVERSAL_CANDLES", "3"))
    )

    # =============================================================================
    # VOLUME EXHAUSTION DETECTION
    # =============================================================================

    # Detect volume climax followed by declining volume
    volume_climax_mult: float = field(
        default_factory=lambda: float(os.getenv("BASKET_VOLUME_CLIMAX_MULT", "2.0"))
    )

    # Consecutive declining volume periods to confirm exhaustion
    exhaustion_decline_periods: int = field(
        default_factory=lambda: int(os.getenv("BASKET_EXHAUSTION_PERIODS", "3"))
    )

    def validate(self) -> None:
        """Validate basket configuration values."""
        if not (1 <= self.max_positions <= 20):
            raise ValueError(f"max_positions must be 1-20, got {self.max_positions}")
        if not (0 <= self.min_positions <= self.max_positions):
            raise ValueError(f"min_positions must be 0-{self.max_positions}")
        if not (5.0 <= self.max_single_position_pct <= 50.0):
            raise ValueError(f"max_single_position_pct must be 5-50%")
        if not (0.3 <= self.max_correlation <= 1.0):
            raise ValueError(f"max_correlation must be 0.3-1.0")
        if not (10 <= self.fear_threshold_buy <= 50):
            raise ValueError(f"fear_threshold_buy must be 10-50")
        if not (50 <= self.greed_threshold_sell <= 90):
            raise ValueError(f"greed_threshold_sell must be 50-90")


@dataclass
class ScaleConfig:
    """
    Position scaling configuration (Story 5.4).

    Controls gradual entry/exit to achieve better average prices
    and reduce timing risk.

    Scale-in: 33% immediate, 33% at -5% drop, 33% at -10% capitulation
    Scale-out: 33% at +10% profit, 33% at +20% profit, 33% trailing stop
    """

    # Number of scale levels
    num_scale_in_levels: int = field(
        default_factory=lambda: int(os.getenv("NUM_SCALE_IN_LEVELS", "3"))
    )
    num_scale_out_levels: int = field(
        default_factory=lambda: int(os.getenv("NUM_SCALE_OUT_LEVELS", "3"))
    )

    # Scale-in allocation percentages (must sum to 100)
    scale_in_pct_1: float = field(
        default_factory=lambda: float(os.getenv("SCALE_IN_PCT_1", "33.33"))
    )
    scale_in_pct_2: float = field(
        default_factory=lambda: float(os.getenv("SCALE_IN_PCT_2", "33.33"))
    )
    scale_in_pct_3: float = field(
        default_factory=lambda: float(os.getenv("SCALE_IN_PCT_3", "33.34"))
    )

    # Scale-in trigger levels (% below first entry)
    scale_in_drop_2: float = field(
        default_factory=lambda: float(os.getenv("SCALE_IN_DROP_2", "5.0"))
    )  # 5% drop triggers scale 2
    scale_in_drop_3: float = field(
        default_factory=lambda: float(os.getenv("SCALE_IN_DROP_3", "10.0"))
    )  # 10% drop triggers scale 3 (capitulation)

    # Scale-out allocation percentages
    scale_out_pct_1: float = field(
        default_factory=lambda: float(os.getenv("SCALE_OUT_PCT_1", "33.33"))
    )
    scale_out_pct_2: float = field(
        default_factory=lambda: float(os.getenv("SCALE_OUT_PCT_2", "33.33"))
    )
    scale_out_pct_3: float = field(
        default_factory=lambda: float(os.getenv("SCALE_OUT_PCT_3", "33.34"))
    )

    # Scale-out profit targets (% above average entry)
    scale_out_profit_1: float = field(
        default_factory=lambda: float(os.getenv("SCALE_OUT_PROFIT_1", "10.0"))
    )  # 10% profit = first exit
    scale_out_profit_2: float = field(
        default_factory=lambda: float(os.getenv("SCALE_OUT_PROFIT_2", "20.0"))
    )  # 20% profit = second exit
    # scale_out_3 is trailing stop or extended target

    # Timeout for pending scales (hours)
    scale_timeout_hours: int = field(
        default_factory=lambda: int(os.getenv("SCALE_TIMEOUT_HOURS", "168"))
    )  # 7 days default

    def get_scale_in_percentages(self) -> List[float]:
        """Get list of scale-in percentages."""
        return [self.scale_in_pct_1, self.scale_in_pct_2, self.scale_in_pct_3]

    def get_scale_out_percentages(self) -> List[float]:
        """Get list of scale-out percentages."""
        return [self.scale_out_pct_1, self.scale_out_pct_2, self.scale_out_pct_3]

    def get_scale_in_drop_triggers(self) -> List[float]:
        """Get list of scale-in drop trigger percentages (0 for first scale)."""
        return [0.0, self.scale_in_drop_2, self.scale_in_drop_3]

    def get_scale_out_profit_triggers(self) -> List[float]:
        """Get list of scale-out profit trigger percentages (0 for trailing)."""
        return [self.scale_out_profit_1, self.scale_out_profit_2, 0.0]

    def validate(self) -> None:
        """
        Validate scale configuration values.

        Raises:
            ValueError: If configuration values are invalid
        """
        # Validate scale-in percentages sum to 100
        scale_in_sum = sum(self.get_scale_in_percentages())
        if abs(scale_in_sum - 100.0) > 0.1:
            raise ValueError(
                f"Scale-in percentages must sum to 100, got {scale_in_sum}"
            )

        # Validate scale-out percentages sum to 100
        scale_out_sum = sum(self.get_scale_out_percentages())
        if abs(scale_out_sum - 100.0) > 0.1:
            raise ValueError(
                f"Scale-out percentages must sum to 100, got {scale_out_sum}"
            )

        # Validate drop triggers are positive and ascending
        if self.scale_in_drop_2 <= 0 or self.scale_in_drop_3 <= 0:
            raise ValueError("Scale-in drop triggers must be positive")
        if self.scale_in_drop_3 <= self.scale_in_drop_2:
            raise ValueError("Scale-in drop 3 must be greater than drop 2")

        # Validate profit triggers are positive and ascending
        if self.scale_out_profit_1 <= 0 or self.scale_out_profit_2 <= 0:
            raise ValueError("Scale-out profit triggers must be positive")
        if self.scale_out_profit_2 <= self.scale_out_profit_1:
            raise ValueError("Scale-out profit 2 must be greater than profit 1")


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
    onchain: OnChainConfig = field(default_factory=OnChainConfig)
    scanner: ScannerConfig = field(default_factory=ScannerConfig)
    multi_factor: MultiFactorConfig = field(default_factory=MultiFactorConfig)
    basket: BasketConfig = field(default_factory=BasketConfig)
    web_url: str = field(default_factory=lambda: os.getenv("WEB_URL", ""))
    debug: bool = field(
        default_factory=lambda: os.getenv("DEBUG", "").lower() == "true"
    )


# Global configuration instance
config = Config()


def get_config() -> Config:
    """Get the global configuration instance."""
    return config

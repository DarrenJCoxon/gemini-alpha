"""
Regime-Based Threshold Adjustments.

Story 5.1: Market Regime Filter

This module provides functions to adjust trading thresholds based on
the current market regime. In BEAR and CHOP regimes, we apply stricter
criteria to prevent catching falling knives.

Regime-Based Threshold Adjustments:
    BULL: Normal operation - fear < 30, 100% position size
    BEAR: Stricter signals - fear < 20, 50% position size
    CHOP: Most conservative - fear < 15, 25% position size
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional
import logging
import os

from services.market_regime import MarketRegime, RegimeAnalysis

logger = logging.getLogger(__name__)


# Original thresholds from decision_logic.py
BASE_FEAR_THRESHOLD_BUY = 30    # fear_score must be below this to buy
BASE_POSITION_SIZE = 1.0        # Multiplier for position sizing
BASE_TECHNICAL_STRENGTH = 50    # Minimum technical strength


@dataclass
class RegimeThresholds:
    """
    Trading thresholds adjusted for market regime.

    Contains all parameters that may be adjusted based on market conditions.
    """
    fear_threshold_buy: int
    position_size_multiplier: float
    require_vision_valid: bool
    allow_trading: bool
    min_technical_strength: int
    reasoning: str


def get_regime_adjusted_thresholds(
    regime: MarketRegime,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Get adjusted trading thresholds based on market regime.

    Applies different criteria for BUY signals based on whether
    we're in a bull, bear, or choppy market.

    Args:
        regime: Current market regime
        config: Optional config overrides for thresholds

    Returns:
        Dict with adjusted thresholds:
        - fear_threshold_buy: Max fear score to allow BUY
        - position_size_multiplier: Position size multiplier (0.0-1.0)
        - require_vision_valid: Whether vision must validate
        - allow_trading: Whether trading is allowed
        - min_technical_strength: Minimum technical strength required
        - reasoning: Explanation of adjustments
    """
    # Load from config or use defaults
    if config is None:
        config = {}

    if regime == MarketRegime.BULL:
        return {
            "fear_threshold_buy": config.get(
                "bull_fear_threshold",
                int(os.getenv("REGIME_BULL_FEAR_THRESHOLD", "30"))
            ),
            "position_size_multiplier": config.get(
                "bull_position_multiplier",
                float(os.getenv("REGIME_BULL_POSITION_MULT", "1.0"))
            ),
            "require_vision_valid": True,
            "allow_trading": True,
            "min_technical_strength": 50,
            "reasoning": "BULL regime: Normal contrarian operation"
        }

    elif regime == MarketRegime.BEAR:
        return {
            "fear_threshold_buy": config.get(
                "bear_fear_threshold",
                int(os.getenv("REGIME_BEAR_FEAR_THRESHOLD", "20"))
            ),
            "position_size_multiplier": config.get(
                "bear_position_multiplier",
                float(os.getenv("REGIME_BEAR_POSITION_MULT", "0.5"))
            ),
            "require_vision_valid": True,
            "allow_trading": True,
            "min_technical_strength": 65,  # Require stronger technicals
            "reasoning": "BEAR regime: Reduced positions, stricter signals"
        }

    else:  # CHOP
        return {
            "fear_threshold_buy": config.get(
                "chop_fear_threshold",
                int(os.getenv("REGIME_CHOP_FEAR_THRESHOLD", "15"))
            ),
            "position_size_multiplier": config.get(
                "chop_position_multiplier",
                float(os.getenv("REGIME_CHOP_POSITION_MULT", "0.25"))
            ),
            "require_vision_valid": True,
            "allow_trading": True,  # Allow but with strict criteria
            "min_technical_strength": 75,  # Require very strong technicals
            "reasoning": "CHOP regime: Minimal trading, wait for clarity"
        }


def should_skip_trading(regime: MarketRegime) -> bool:
    """
    Determine if trading should be skipped entirely.

    In extreme conditions, we may want to halt trading completely.
    Currently allows trading in all regimes with adjustments.

    Args:
        regime: Current market regime

    Returns:
        True if trading should be skipped, False otherwise
    """
    # For now, allow trading in all regimes with adjustments
    # This can be made stricter if needed
    return False


def get_position_size_for_regime(
    regime: MarketRegime,
    base_size: float,
    config: Optional[Dict[str, Any]] = None
) -> float:
    """
    Calculate position size adjusted for market regime.

    In BEAR and CHOP markets, we reduce position size to limit
    exposure during uncertain conditions.

    Args:
        regime: Current market regime
        base_size: Base position size before adjustment
        config: Optional config overrides

    Returns:
        Adjusted position size
    """
    thresholds = get_regime_adjusted_thresholds(regime, config)
    multiplier = thresholds["position_size_multiplier"]

    adjusted_size = base_size * multiplier

    logger.info(
        f"[RegimeAdjustments] Position size: {base_size} * {multiplier} = {adjusted_size} "
        f"({regime.value} regime)"
    )

    return adjusted_size


def validate_buy_conditions_with_regime(
    fear_score: int,
    technical_signal: str,
    technical_strength: int,
    vision_valid: bool,
    regime_analysis: RegimeAnalysis,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Validate BUY conditions with regime-adjusted thresholds.

    Applies stricter criteria in BEAR and CHOP regimes to prevent
    catching falling knives during downtrends.

    Args:
        fear_score: Current fear/greed score (0-100)
        technical_signal: Technical signal (BULLISH/BEARISH/NEUTRAL)
        technical_strength: Technical signal strength (0-100)
        vision_valid: Whether vision analysis is valid
        regime_analysis: Current regime analysis
        config: Optional config overrides

    Returns:
        Dict with:
        - is_valid: Whether all conditions are met
        - reasons: List of PASS/FAIL reasons
        - adjustments: Applied threshold adjustments
    """
    adjustments = get_regime_adjusted_thresholds(regime_analysis.regime, config)
    reasons = []

    # Log regime impact
    reasons.append(f"REGIME: {regime_analysis.regime.value} - {adjustments['reasoning']}")

    # Condition 1: Fear threshold (regime-adjusted)
    fear_threshold = adjustments["fear_threshold_buy"]
    if fear_score < fear_threshold:
        reasons.append(f"PASS: Fear {fear_score} < {fear_threshold} (regime-adjusted)")
        condition_1 = True
    else:
        reasons.append(f"FAIL: Fear {fear_score} >= {fear_threshold} (regime requires lower)")
        condition_1 = False

    # Condition 2: Technical strength (regime-adjusted)
    min_strength = adjustments["min_technical_strength"]
    if technical_signal == "BULLISH" and technical_strength >= min_strength:
        reasons.append(f"PASS: Bullish signal with strength {technical_strength} >= {min_strength}")
        condition_2 = True
    else:
        reasons.append(f"FAIL: Technical {technical_signal} (strength {technical_strength}) below threshold {min_strength}")
        condition_2 = False

    # Condition 3: Vision validation
    if vision_valid:
        reasons.append("PASS: Vision validated")
        condition_3 = True
    else:
        reasons.append("FAIL: Vision not valid")
        condition_3 = False

    all_met = condition_1 and condition_2 and condition_3

    return {
        "is_valid": all_met,
        "reasons": reasons,
        "adjustments": adjustments,
    }


def get_regime_summary(regime_analysis: RegimeAnalysis) -> str:
    """
    Get a concise summary of the regime for logging.

    Args:
        regime_analysis: Current regime analysis

    Returns:
        Human-readable regime summary string
    """
    return (
        f"{regime_analysis.regime.value} "
        f"(DMA: {regime_analysis.price_vs_200dma:+.1f}%, "
        f"Confidence: {regime_analysis.confidence}%)"
    )

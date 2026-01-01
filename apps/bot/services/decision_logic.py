"""
Decision Logic Module for the Master Node.

Story 2.4: Master Node & Signal Logging

This module implements the strict decision validation rules for
the contrarian trading strategy. These rules are applied BEFORE
and AFTER the LLM synthesis to ensure safety.

Decision Logic:
    BUY = (fear_score < 20) AND (technical_signal == "BULLISH") AND (vision_is_valid == true)
    SELL = (fear_score > 80) OR (technical_signal == "BEARISH" AND strength > 70)
    HOLD = All other cases (default)
"""

from typing import Any, Dict, List, Tuple

# Contrarian thresholds
FEAR_THRESHOLD_BUY = 20      # fear_score must be BELOW this to buy
FEAR_THRESHOLD_SELL = 80     # fear_score must be ABOVE this to sell
TECHNICAL_STRENGTH_MIN = 50  # Minimum strength for signal validity
VISION_CONFIDENCE_MIN = 30   # Minimum vision confidence
BEARISH_STRENGTH_SELL = 70   # Minimum strength for bearish sell trigger


def validate_buy_conditions(
    sentiment_analysis: Dict[str, Any],
    technical_analysis: Dict[str, Any],
    vision_analysis: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    Validate if all BUY conditions are met.

    BUY requires ALL three conditions:
    1. Extreme fear (fear_score < 20)
    2. Bullish technicals with sufficient strength
    3. Valid vision analysis (no scam wicks)

    Args:
        sentiment_analysis: Output from Sentiment Agent
        technical_analysis: Output from Technical Agent
        vision_analysis: Output from Vision Agent

    Returns:
        Tuple of (is_valid: bool, reasons: List[str])
        reasons contains PASS/FAIL status for each condition
    """
    reasons = []

    # Extract values with safe defaults
    fear_score = sentiment_analysis.get("fear_score", 50)
    tech_signal = technical_analysis.get("signal", "NEUTRAL")
    tech_strength = technical_analysis.get("strength", 0)
    vision_valid = vision_analysis.get("is_valid", False)
    vision_confidence = vision_analysis.get("confidence_score", 0)

    # Condition 1: Extreme Fear
    if fear_score < FEAR_THRESHOLD_BUY:
        reasons.append(f"PASS: Extreme fear detected (score: {fear_score})")
        condition_1 = True
    else:
        reasons.append(f"FAIL: Fear score {fear_score} >= {FEAR_THRESHOLD_BUY}")
        condition_1 = False

    # Condition 2: Bullish Technicals with sufficient strength
    if tech_signal == "BULLISH" and tech_strength >= TECHNICAL_STRENGTH_MIN:
        reasons.append(f"PASS: Bullish signal (strength: {tech_strength})")
        condition_2 = True
    else:
        reasons.append(f"FAIL: Technical signal is {tech_signal} (strength: {tech_strength})")
        condition_2 = False

    # Condition 3: Vision Validation
    if vision_valid and vision_confidence >= VISION_CONFIDENCE_MIN:
        reasons.append(f"PASS: Vision validated (confidence: {vision_confidence})")
        condition_3 = True
    else:
        reasons.append(f"FAIL: Vision not valid or low confidence ({vision_confidence})")
        condition_3 = False

    all_conditions_met = condition_1 and condition_2 and condition_3

    return all_conditions_met, reasons


def validate_sell_conditions(
    sentiment_analysis: Dict[str, Any],
    technical_analysis: Dict[str, Any],
    vision_analysis: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    Validate if SELL conditions are met.

    SELL triggers on ANY of:
    1. Extreme greed (fear_score > 80)
    2. Strong bearish technicals (signal BEARISH with strength > 70)
    3. Vision detected bearish reversal pattern (not implemented yet)

    Args:
        sentiment_analysis: Output from Sentiment Agent
        technical_analysis: Output from Technical Agent
        vision_analysis: Output from Vision Agent

    Returns:
        Tuple of (is_valid: bool, reasons: List[str])
        reasons contains the triggering condition or default message
    """
    reasons = []

    # Extract values with safe defaults
    fear_score = sentiment_analysis.get("fear_score", 50)
    tech_signal = technical_analysis.get("signal", "NEUTRAL")
    tech_strength = technical_analysis.get("strength", 0)

    # Condition: Extreme Greed
    if fear_score > FEAR_THRESHOLD_SELL:
        reasons.append(f"TRIGGER: Extreme greed detected (score: {fear_score})")
        return True, reasons

    # Condition: Strong Bearish Technicals
    if tech_signal == "BEARISH" and tech_strength >= BEARISH_STRENGTH_SELL:
        reasons.append(f"TRIGGER: Strong bearish signal (strength: {tech_strength})")
        return True, reasons

    # Future: Check for bearish reversal patterns in vision_analysis
    # patterns = vision_analysis.get("patterns_detected", [])
    # bearish_patterns = ["head_and_shoulders", "double_top", "rising_wedge"]
    # if any(p in patterns for p in bearish_patterns):
    #     reasons.append(f"TRIGGER: Bearish pattern detected")
    #     return True, reasons

    reasons.append("No SELL conditions triggered")
    return False, reasons


def pre_validate_decision(
    sentiment_analysis: Dict[str, Any],
    technical_analysis: Dict[str, Any],
    vision_analysis: Dict[str, Any]
) -> Tuple[str, List[str]]:
    """
    Pre-validate decision before sending to LLM.

    This acts as a safety check - the LLM should agree with this.
    If the LLM disagrees (suggests BUY when pre-validation says HOLD),
    the Master Node will override to the safer decision.

    Decision priority:
    1. Check BUY conditions (all must be met)
    2. Check SELL conditions (any can trigger)
    3. Default to HOLD

    Args:
        sentiment_analysis: Output from Sentiment Agent
        technical_analysis: Output from Technical Agent
        vision_analysis: Output from Vision Agent

    Returns:
        Tuple of (suggested_action: str, validation_reasons: List[str])
        suggested_action is one of "BUY", "SELL", "HOLD"
    """
    # Check BUY conditions first
    buy_valid, buy_reasons = validate_buy_conditions(
        sentiment_analysis, technical_analysis, vision_analysis
    )

    if buy_valid:
        return "BUY", buy_reasons

    # Check SELL conditions
    sell_valid, sell_reasons = validate_sell_conditions(
        sentiment_analysis, technical_analysis, vision_analysis
    )

    if sell_valid:
        return "SELL", sell_reasons

    # Default to HOLD
    return "HOLD", ["Default to HOLD - not all BUY/SELL conditions met"]


def calculate_decision_confidence(
    action: str,
    sentiment_analysis: Dict[str, Any],
    technical_analysis: Dict[str, Any],
    vision_analysis: Dict[str, Any]
) -> int:
    """
    Calculate confidence score for a decision based on input strength.

    Higher confidence when:
    - Fear score is more extreme (very low for BUY, very high for SELL)
    - Technical strength is higher
    - Vision confidence is higher

    Args:
        action: The trading action ("BUY", "SELL", "HOLD")
        sentiment_analysis: Output from Sentiment Agent
        technical_analysis: Output from Technical Agent
        vision_analysis: Output from Vision Agent

    Returns:
        Confidence score 0-100
    """
    fear_score = sentiment_analysis.get("fear_score", 50)
    tech_strength = technical_analysis.get("strength", 0)
    vision_confidence = vision_analysis.get("confidence_score", 0)

    if action == "BUY":
        # Higher confidence when fear is more extreme (lower score)
        fear_factor = max(0, (FEAR_THRESHOLD_BUY - fear_score) * 2)  # 0-40
        tech_factor = min(tech_strength, 30)  # 0-30
        vision_factor = min(vision_confidence // 3, 30)  # 0-30
        return min(100, fear_factor + tech_factor + vision_factor)

    elif action == "SELL":
        # Higher confidence when greed is more extreme (higher score)
        greed_factor = max(0, (fear_score - FEAR_THRESHOLD_SELL) * 2)  # 0-40
        tech_factor = min(tech_strength, 30)  # 0-30
        # For SELL, vision is less important
        return min(100, greed_factor + tech_factor + 20)

    else:  # HOLD
        # Medium confidence for HOLD - we're uncertain
        return 50

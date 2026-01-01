"""
Master Synthesis Node.

Story 2.4: Master Node & Signal Logging
Story 5.1: Market Regime Filter

This node synthesizes all agent analyses into a final trading decision,
applying contrarian trading principles and strict risk management rules.

The Master Node:
1. Receives outputs from Sentiment, Technical, and Vision agents
2. Classifies market regime (BULL/BEAR/CHOP) from daily candles (Story 5.1)
3. Pre-validates decision using regime-adjusted logic rules
4. Calls Gemini Pro LLM for synthesis and reasoning
5. Applies safety override if LLM disagrees with pre-validation
6. Returns final decision with confidence and reasoning

Story 5.1 additions:
- Regime classification before decision making
- Regime-adjusted thresholds for BUY conditions
- Regime logged in state for audit trail
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from core.state import FinalDecision, GraphState
from services.master_prompts import (
    MASTER_SYSTEM_PROMPT,
    build_master_prompt,
)
from services.decision_logic import (
    pre_validate_decision,
    pre_validate_decision_with_regime,
    calculate_decision_confidence,
    validate_decision_with_multi_factor,
)
from services.market_regime import (
    classify_market_regime,
    get_default_regime,
    MarketRegime,
)

logger = logging.getLogger(__name__)


def parse_master_response(response_text: str) -> dict:
    """
    Parse Master Node JSON response from LLM.

    Handles various JSON formats including:
    - Raw JSON
    - JSON wrapped in markdown code blocks
    - Malformed JSON (returns safe defaults)

    Args:
        response_text: Raw response text from Gemini LLM

    Returns:
        Dict with keys: action, confidence, reasoning, risk_assessment, key_factors
    """
    try:
        text = response_text.strip()

        # Remove markdown code block wrappers if present
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        data = json.loads(text.strip())

        # Validate and normalize action
        action = data.get("action", "HOLD").upper()
        if action not in ["BUY", "SELL", "HOLD"]:
            action = "HOLD"

        return {
            "action": action,
            "confidence": int(data.get("confidence", 50)),
            "reasoning": data.get("reasoning", "Unable to parse reasoning"),
            "risk_assessment": data.get("risk_assessment", "MEDIUM"),
            "key_factors": data.get("key_factors", [])
        }

    except json.JSONDecodeError:
        logger.warning(f"Failed to parse LLM response as JSON: {response_text[:200]}")
        return {
            "action": "HOLD",
            "confidence": 0,
            "reasoning": f"Failed to parse LLM response: {response_text[:200]}",
            "risk_assessment": "HIGH",
            "key_factors": ["Parse error"]
        }
    except Exception as e:
        logger.error(f"Unexpected error parsing LLM response: {e}")
        return {
            "action": "HOLD",
            "confidence": 0,
            "reasoning": f"Error parsing response: {str(e)}",
            "risk_assessment": "HIGH",
            "key_factors": ["Error"]
        }


def master_node(state: GraphState) -> Dict[str, Any]:
    """
    Master Synthesis Node - Makes final trading decision.

    This node synthesizes all agent analyses and makes the final
    trading decision using a multi-layer safety system:

    1. Multi-factor validation: Check if 3+ factors align for BUY/SELL (Story 5.3)
    2. Pre-validation: Pure logic check as backup
    3. LLM synthesis: AI reasoning for the decision
    4. Post-validation: Override if LLM disagrees with pre-validation

    Args:
        state: Current GraphState with all agent analyses

    Returns:
        Dict with final_decision and multi_factor_analysis fields populated

    Note:
        Returns dict with only the fields to update (LangGraph pattern),
        not the full state. LangGraph merges this with existing state.

    Decision Logic (Story 5.3):
        BUY = 3+ of 6 factors triggered (configurable)
        SELL = 2+ of 5 factors triggered (configurable)
        HOLD = Neither threshold met

    Safety:
        If LLM suggests BUY but multi-factor validation disagrees, override to HOLD.
        This prevents the LLM from being "creative" with trading decisions.
    """
    asset = state.get("asset_symbol", "UNKNOWN")

    # Get agent analyses (may be None if agents haven't run yet)
    sentiment = state.get("sentiment_analysis") or {}
    technical = state.get("technical_analysis") or {}
    vision = state.get("vision_analysis") or {}
    regime = state.get("regime_analysis")

    # Get current price from candles data
    candles = state.get("candles_data", [])
    current_price = float(candles[-1].get("close", 0)) if candles else 0

    logger.info(f"[MasterNode] Synthesizing decision for {asset}")
    logger.debug(f"[MasterNode] Sentiment: {sentiment}")
    logger.debug(f"[MasterNode] Technical: {technical}")
    logger.debug(f"[MasterNode] Vision: {vision}")
    logger.debug(f"[MasterNode] Current Price: {current_price}")

    # Multi-factor validation (Story 5.3)
    mf_action, mf_details = validate_decision_with_multi_factor(
        sentiment_analysis=sentiment,
        technical_analysis=technical,
        vision_analysis=vision,
        current_price=current_price,
        regime_analysis=regime
    )
    logger.info(f"[MasterNode] Multi-factor validation suggests: {mf_action}")
    logger.info(f"[MasterNode] Factors met: {mf_details['factors_met']}")
    logger.debug(f"[MasterNode] Multi-factor reasoning: {mf_details['reasoning']}")

    # Pre-validation safety check (legacy, kept for backup)
    suggested_action, validation_reasons = pre_validate_decision(
        sentiment, technical, vision
    )
    logger.info(f"[MasterNode] Pre-validation suggests: {suggested_action}")
    for reason in validation_reasons:
        logger.debug(f"    - {reason}")

    # Try to call Gemini Pro for synthesis
    llm_response = None
    try:
        from config import get_gemini_pro_vision_model

        # Build prompt with all context
        timestamp = datetime.now(timezone.utc).isoformat()
        user_prompt = build_master_prompt(
            asset_symbol=asset,
            timestamp=timestamp,
            sentiment_analysis=sentiment,
            technical_analysis=technical,
            vision_analysis=vision
        )

        # Call Gemini Pro for synthesis
        model = get_gemini_pro_vision_model()
        response = model.generate_content([
            MASTER_SYSTEM_PROMPT,
            user_prompt
        ])

        # Parse response
        llm_response = parse_master_response(response.text)
        logger.info(f"[MasterNode] LLM suggested: {llm_response['action']}")

    except ValueError as e:
        # API key not configured - use pre-validation only
        logger.warning(f"[MasterNode] Gemini API not configured: {e}")
        logger.info("[MasterNode] Falling back to pre-validation decision")

    except Exception as e:
        logger.error(f"[MasterNode] Error calling Gemini API: {e}")
        logger.info("[MasterNode] Falling back to pre-validation decision")

    # Determine final action using multi-factor as primary
    if llm_response:
        final_action = llm_response["action"]
        reasoning = llm_response["reasoning"]

        # Safety check: Override if LLM disagrees with multi-factor validation for BUY
        if final_action == "BUY" and mf_action != "BUY":
            logger.warning(
                f"[MasterNode] SAFETY OVERRIDE: LLM suggested BUY but "
                f"multi-factor validation said {mf_action}"
            )
            final_action = "HOLD"
            reasoning = (
                f"Safety override: LLM suggested BUY but multi-factor conditions not met. "
                f"Multi-factor: {mf_action} ({mf_details['factors_met']} factors). "
                f"Original reasoning: {reasoning}"
            )
            logger.info("[MasterNode] Overriding to HOLD for safety")

        # Use multi-factor confidence as primary, blend with LLM
        confidence = int(mf_details["confidence"])
        if llm_response["confidence"] > 0:
            confidence = (confidence + llm_response["confidence"]) // 2

    else:
        # No LLM response - use multi-factor validation
        final_action = mf_action
        reasoning = mf_details["reasoning"]
        confidence = int(mf_details["confidence"])

    # Build final decision
    final_decision: FinalDecision = {
        "action": final_action,
        "confidence": confidence,
        "reasoning": reasoning,
        "timestamp": datetime.now(timezone.utc)
    }

    logger.info(
        f"[MasterNode] Final Decision: {final_decision['action']} "
        f"(Confidence: {final_decision['confidence']}%) "
        f"[Regime: {regime_analysis_dict['regime']}]"
    )

    # Build multi-factor analysis state (Story 5.3)
    buy_analysis = mf_details["buy_analysis"]
    sell_analysis = mf_details["sell_analysis"]
    multi_factor_analysis = {
        "action": mf_action,
        "buy_factors_met": buy_analysis.factors_met,
        "sell_factors_met": sell_analysis.factors_met,
        "buy_factors_triggered": [f.factor for f in buy_analysis.factors_triggered],
        "sell_factors_triggered": [f.factor for f in sell_analysis.factors_triggered],
        "confidence": mf_details["confidence"],
        "reasoning": mf_details["reasoning"]
    }

    # Return only the fields to update (LangGraph merge pattern)
    return {
        "final_decision": final_decision,
        "multi_factor_analysis": multi_factor_analysis
    }

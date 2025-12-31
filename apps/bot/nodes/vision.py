"""
Vision Analysis Agent Node.

Story 2.3: Vision Agent & Chart Generation

This node generates candlestick charts and uses Gemini Vision
to analyze chart patterns and detect potential manipulation.

Features:
    - Generate candlestick chart from candles_data
    - Send image to Gemini Vision for pattern analysis
    - Detect reversal patterns (Double Bottom, Wyckoff Spring)
    - Flag "scam wicks" and manipulation patterns
"""

import base64
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

from core.state import GraphState, VisionAnalysis
from services.chart_generator import generate_chart_image, save_chart_to_file
from services.vision_prompts import VISION_SYSTEM_PROMPT, build_vision_prompt
from services.vision_utils import parse_vision_response, validate_vision_result
from config import get_gemini_pro_vision_model

logger = logging.getLogger(__name__)

# Minimum candles required for meaningful chart analysis
MIN_CANDLES_FOR_CHART = 50


def vision_node(state: GraphState) -> Dict[str, Any]:
    """
    Vision Analysis Agent - Analyzes chart patterns visually.

    Generates a candlestick chart image and sends it to Gemini Vision
    for pattern recognition and scam wick detection.

    Analysis includes:
    - Reversal patterns (Double Bottom, Wyckoff Spring, Hammer)
    - Warning patterns (Double Top, Head and Shoulders)
    - Scam wick detection (manipulation signals)
    - Support level identification

    Args:
        state: Current GraphState containing candles_data

    Returns:
        Dict with vision_analysis field populated containing:
            - patterns_detected: List of detected patterns
            - confidence_score: Analysis confidence (0-100)
            - description: Natural language chart description
            - is_valid: False if scam wick or manipulation detected

    Note:
        Returns dict with only the fields to update (LangGraph pattern),
        not the full state. LangGraph merges this with existing state.
    """
    asset = state.get("asset_symbol", "UNKNOWN")
    candles = state.get("candles_data", [])

    logger.info(f"[VisionAgent] Processing {asset} chart with {len(candles)} candles")

    # Check for minimum candle requirement
    if len(candles) < MIN_CANDLES_FOR_CHART:
        logger.warning(
            f"[VisionAgent] Insufficient candles ({len(candles)} < {MIN_CANDLES_FOR_CHART})"
        )
        vision_analysis: VisionAnalysis = {
            "patterns_detected": [],
            "confidence_score": 0,
            "description": f"Insufficient candle data for chart analysis ({len(candles)} candles)",
            "is_valid": False
        }
        return {"vision_analysis": vision_analysis}

    try:
        # Generate chart image
        logger.info(f"[VisionAgent] Generating chart image...")
        image_bytes = generate_chart_image(
            candles=candles,
            asset_symbol=asset,
            num_candles=100,
            include_volume=True,
            include_sma=True
        )
        logger.info(f"[VisionAgent] Chart generated: {len(image_bytes)} bytes")

        # Optional: Save for debugging if CHART_DEBUG_DIR is set
        debug_dir = os.getenv("CHART_DEBUG_DIR")
        if debug_dir:
            try:
                filename = f"{asset}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
                filepath = os.path.join(debug_dir, filename)
                save_chart_to_file(image_bytes, filepath)
                logger.info(f"[VisionAgent] Debug chart saved to {filepath}")
            except Exception as save_err:
                logger.warning(f"[VisionAgent] Failed to save debug chart: {save_err}")

        # Convert to base64 for API
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')

        # Build prompts
        user_prompt = build_vision_prompt(
            asset_symbol=asset,
            num_candles=min(100, len(candles)),
            timeframe="15-minute",
            include_sma=True
        )

        # Call Gemini Vision
        logger.info(f"[VisionAgent] Calling Gemini Vision API...")
        model = get_gemini_pro_vision_model()

        response = model.generate_content([
            VISION_SYSTEM_PROMPT,
            {
                "mime_type": "image/png",
                "data": image_base64
            },
            user_prompt
        ])

        # Parse response
        logger.info(f"[VisionAgent] Parsing vision response...")
        parsed = parse_vision_response(response.text)

        # Determine validity based on parsed analysis
        is_valid = validate_vision_result(parsed)

        vision_analysis = {
            "patterns_detected": parsed["patterns_detected"],
            "confidence_score": parsed["confidence_score"],
            "description": parsed["description"],
            "is_valid": is_valid
        }

        logger.info(
            f"[VisionAgent] Patterns: {parsed['patterns_detected']}, "
            f"Valid: {is_valid}, Confidence: {parsed['confidence_score']}"
        )

        if parsed.get("scam_wick_detected"):
            logger.warning(
                f"[VisionAgent] SCAM WICK DETECTED: {parsed.get('scam_wick_explanation', 'No details')}"
            )

        return {"vision_analysis": vision_analysis}

    except Exception as e:
        logger.error(f"[VisionAgent] Error during vision analysis: {str(e)}", exc_info=True)

        vision_analysis = {
            "patterns_detected": [],
            "confidence_score": 0,
            "description": f"Error during vision analysis: {str(e)}",
            "is_valid": False
        }

        # Also set error in state for downstream handling
        return {
            "vision_analysis": vision_analysis,
            "error": f"Vision analysis error: {str(e)}"
        }

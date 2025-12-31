#!/usr/bin/env python3
"""
Vision Agent Verification Script.

Story 2.3: Vision Agent & Chart Generation

This script verifies the Vision Agent components:
1. Chart generation from sample candle data
2. PNG image validation
3. Optional: Send to Gemini Vision (requires API key)

Usage:
    cd apps/bot
    python scripts/test_vision.py [--api]

Options:
    --api    Also test the Gemini Vision API (requires GOOGLE_AI_API_KEY)
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from services.chart_generator import generate_chart_image, save_chart_to_file
from services.vision_prompts import VISION_SYSTEM_PROMPT, build_vision_prompt
from services.vision_utils import parse_vision_response, validate_vision_result


def generate_test_candles(num_candles: int = 100):
    """
    Generate realistic-looking test candles.

    Creates a price pattern with:
    - Initial downtrend (fear phase)
    - Reversal at support
    - Recovery uptrend

    Args:
        num_candles: Number of candles to generate

    Returns:
        List of candle dictionaries
    """
    candles = []
    base_price = 100.0
    base_time = datetime.utcnow() - timedelta(hours=num_candles)

    for i in range(num_candles):
        # Simulate market movement with phases
        if i < 40:
            # Downtrend phase
            trend = -0.3
            volatility = 2
        elif i < 60:
            # Consolidation/reversal phase
            trend = -0.05
            volatility = 3
        else:
            # Recovery phase
            trend = 0.25
            volatility = 1.5

        noise = ((-1) ** i * volatility) + ((i % 7) - 3) * 0.5
        price = base_price + (i * trend) + noise

        # Ensure price stays positive
        price = max(price, 50.0)

        candles.append({
            "timestamp": base_time + timedelta(hours=i),
            "open": price - 1,
            "high": price + volatility + 1,
            "low": price - volatility - 1,
            "close": price + (0.5 if i > 60 else -0.5),
            "volume": 10000 + (abs(noise) * 1000) + (i * 50)
        })
    return candles


def test_chart_generation():
    """Test chart image generation."""
    print("\n[1] Generating test candles...")
    candles = generate_test_candles(100)
    print(f"    Generated {len(candles)} candles")
    print(f"    Price range: ${min(c['low'] for c in candles):.2f} - ${max(c['high'] for c in candles):.2f}")

    print("\n[2] Generating chart image...")
    image_bytes = generate_chart_image(
        candles=candles,
        asset_symbol="TESTUSD",
        num_candles=100,
        include_volume=True,
        include_sma=True
    )
    print(f"    Image size: {len(image_bytes):,} bytes")

    # Verify PNG format
    if image_bytes[:8] != b'\x89PNG\r\n\x1a\n':
        print("    ERROR: Output is not valid PNG!")
        return False

    print("    PNG validation: PASSED")

    # Save chart for visual inspection
    output_path = "/tmp/vision_test_chart.png"
    print(f"\n[3] Saving chart to {output_path}...")
    save_chart_to_file(image_bytes, output_path)
    print(f"    Saved successfully!")

    return True


def test_prompt_generation():
    """Test vision prompt generation."""
    print("\n[4] Testing prompt generation...")

    prompt = build_vision_prompt(
        asset_symbol="SOLUSD",
        num_candles=100,
        timeframe="15-minute",
        include_sma=True
    )

    print(f"    User prompt length: {len(prompt)} chars")
    print(f"    System prompt length: {len(VISION_SYSTEM_PROMPT)} chars")

    if "SOLUSD" not in prompt:
        print("    ERROR: Asset symbol not in prompt!")
        return False

    if "SMA" not in prompt:
        print("    ERROR: SMA note not in prompt!")
        return False

    print("    Prompt validation: PASSED")
    return True


def test_response_parsing():
    """Test vision response parsing."""
    print("\n[5] Testing response parsing...")

    # Test valid response
    valid_response = '''{
        "patterns_detected": ["Double Bottom", "Hammer"],
        "pattern_quality": "STRONG",
        "support_level_nearby": true,
        "scam_wick_detected": false,
        "overall_bias": "BULLISH",
        "confidence_score": 75,
        "description": "Clear double bottom pattern",
        "recommendation": "VALID"
    }'''

    parsed = parse_vision_response(valid_response)
    is_valid = validate_vision_result(parsed)

    print(f"    Parsed patterns: {parsed['patterns_detected']}")
    print(f"    Confidence: {parsed['confidence_score']}")
    print(f"    Recommendation: {parsed['recommendation']}")
    print(f"    Is Valid: {is_valid}")

    if not is_valid:
        print("    ERROR: Valid response marked as invalid!")
        return False

    # Test scam wick response
    scam_response = '''{
        "patterns_detected": ["Long Wick"],
        "pattern_quality": "WEAK",
        "support_level_nearby": false,
        "scam_wick_detected": true,
        "overall_bias": "NEUTRAL",
        "confidence_score": 20,
        "description": "Manipulation detected",
        "recommendation": "INVALID"
    }'''

    parsed_scam = parse_vision_response(scam_response)
    is_valid_scam = validate_vision_result(parsed_scam)

    print(f"\n    Scam wick test:")
    print(f"    Scam detected: {parsed_scam['scam_wick_detected']}")
    print(f"    Is Valid: {is_valid_scam}")

    if is_valid_scam:
        print("    ERROR: Scam wick response marked as valid!")
        return False

    print("    Response parsing: PASSED")
    return True


def test_gemini_api():
    """Test actual Gemini Vision API call."""
    print("\n[6] Testing Gemini Vision API...")

    try:
        from config import get_gemini_pro_vision_model
        import base64

        # Check for API key
        api_key = os.getenv("GOOGLE_AI_API_KEY")
        if not api_key:
            print("    SKIPPED: GOOGLE_AI_API_KEY not set")
            return None

        # Generate chart
        candles = generate_test_candles(100)
        image_bytes = generate_chart_image(
            candles=candles,
            asset_symbol="TESTUSD",
            num_candles=100
        )
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')

        # Build prompt
        user_prompt = build_vision_prompt(
            asset_symbol="TESTUSD",
            num_candles=100,
            timeframe="15-minute",
            include_sma=True
        )

        # Call API
        print("    Calling Gemini Vision API...")
        model = get_gemini_pro_vision_model()
        response = model.generate_content([
            VISION_SYSTEM_PROMPT,
            {"mime_type": "image/png", "data": image_base64},
            user_prompt
        ])

        print(f"    Response received: {len(response.text)} chars")

        # Parse response
        parsed = parse_vision_response(response.text)
        is_valid = validate_vision_result(parsed)

        print(f"    Patterns: {parsed['patterns_detected']}")
        print(f"    Confidence: {parsed['confidence_score']}")
        print(f"    Bias: {parsed['overall_bias']}")
        print(f"    Description: {parsed['description'][:100]}...")
        print(f"    Is Valid: {is_valid}")

        print("    API test: PASSED")
        return True

    except Exception as e:
        print(f"    ERROR: {str(e)}")
        return False


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("Vision Agent Verification Script")
    print("Story 2.3: Vision Agent & Chart Generation")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Chart Generation", test_chart_generation()))
    results.append(("Prompt Generation", test_prompt_generation()))
    results.append(("Response Parsing", test_response_parsing()))

    # Run API test if requested
    if "--api" in sys.argv:
        api_result = test_gemini_api()
        if api_result is not None:
            results.append(("Gemini Vision API", api_result))
    else:
        print("\n[6] Gemini Vision API test: SKIPPED (use --api flag to test)")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_passed = True
    for name, result in results:
        if result is None:
            status = "SKIPPED"
        elif result:
            status = "PASSED"
        else:
            status = "FAILED"
            all_passed = False
        print(f"  {name}: {status}")

    print("\n" + "=" * 60)
    if all_passed:
        print("ALL TESTS PASSED!")
        print("Chart saved to: /tmp/vision_test_chart.png")
    else:
        print("SOME TESTS FAILED - See output above for details")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

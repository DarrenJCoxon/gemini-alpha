#!/usr/bin/env python3
"""
Verification script for LangGraph Council setup.

Story 2.1: LangGraph State Machine Setup

This script tests the complete graph flow by:
1. Building the Council graph
2. Creating a test state with dummy data
3. Invoking the graph and running all nodes
4. Verifying all output fields are populated

Usage:
    cd apps/bot/
    python scripts/test_graph.py

Expected Output:
    - All 4 nodes execute in order
    - Final state contains all analysis fields populated
    - No errors during graph execution
"""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging to see node execution
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

# Import from core module
from core.graph import build_council_graph
from core.state import GraphState, create_initial_state


def create_test_state() -> GraphState:
    """
    Create a test state with dummy data.

    Returns:
        GraphState: Initialized state with sample data for testing
    """
    return create_initial_state(
        asset_symbol="SOLUSD",
        candles_data=[
            {
                "timestamp": datetime.now(timezone.utc),
                "open": 100.0,
                "high": 105.0,
                "low": 98.0,
                "close": 103.0,
                "volume": 10000.0
            },
            {
                "timestamp": datetime.now(timezone.utc),
                "open": 103.0,
                "high": 108.0,
                "low": 101.0,
                "close": 106.0,
                "volume": 12000.0
            }
        ],
        sentiment_data=[
            {"text": "SOL looking bullish!", "source": "bluesky", "score": 0.8},
            {"text": "Crypto winter incoming?", "source": "telegram", "score": -0.5},
            {"text": "Test sentiment data", "source": "test", "score": 0.0}
        ]
    )


def verify_state(state: Dict[str, Any]) -> bool:
    """
    Verify the final state has all required fields populated.

    Args:
        state: The final state after graph execution

    Returns:
        bool: True if all verifications pass

    Raises:
        AssertionError: If any verification fails
    """
    print("\n[4] Verifying results...")

    # Verify technical analysis
    assert state.get("technical_analysis") is not None, "Technical analysis missing"
    tech = state["technical_analysis"]
    assert tech.get("signal") in ("BULLISH", "BEARISH", "NEUTRAL"), f"Invalid signal: {tech.get('signal')}"
    assert 0 <= tech.get("strength", -1) <= 100, f"Invalid strength: {tech.get('strength')}"
    print(f"    Technical Signal: {tech['signal']} (strength: {tech['strength']})")

    # Verify sentiment analysis
    assert state.get("sentiment_analysis") is not None, "Sentiment analysis missing"
    sentiment = state["sentiment_analysis"]
    assert 0 <= sentiment.get("fear_score", -1) <= 100, f"Invalid fear score: {sentiment.get('fear_score')}"
    print(f"    Sentiment Fear Score: {sentiment['fear_score']} (sources: {sentiment.get('source_count', 0)})")

    # Verify vision analysis
    assert state.get("vision_analysis") is not None, "Vision analysis missing"
    vision = state["vision_analysis"]
    assert isinstance(vision.get("patterns_detected"), list), "Patterns should be a list"
    assert isinstance(vision.get("is_valid"), bool), "is_valid should be boolean"
    print(f"    Vision Valid: {vision['is_valid']} (patterns: {len(vision['patterns_detected'])})")

    # Verify final decision
    assert state.get("final_decision") is not None, "Final decision missing"
    decision = state["final_decision"]
    assert decision.get("action") in ("BUY", "SELL", "HOLD"), f"Invalid action: {decision.get('action')}"
    assert 0 <= decision.get("confidence", -1) <= 100, f"Invalid confidence: {decision.get('confidence')}"
    assert decision.get("timestamp") is not None, "Decision timestamp missing"
    print(f"    Final Decision: {decision['action']} (confidence: {decision['confidence']}%)")

    # Verify no errors
    assert state.get("error") is None, f"Unexpected error: {state.get('error')}"
    print("    No errors detected")

    return True


def main() -> int:
    """
    Main verification function.

    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    print("=" * 60)
    print("LangGraph Council Verification Test")
    print("Story 2.1: LangGraph State Machine Setup")
    print("=" * 60)

    try:
        # Step 1: Build the graph
        print("\n[1] Building Council graph...")
        graph = build_council_graph()
        print("    Graph compiled successfully!")

        # Step 2: Create test state
        print("\n[2] Creating test state...")
        initial_state = create_test_state()
        print(f"    Asset: {initial_state['asset_symbol']}")
        print(f"    Candles: {len(initial_state['candles_data'])} entries")
        print(f"    Sentiment: {len(initial_state['sentiment_data'])} entries")

        # Step 3: Invoke the graph
        print("\n[3] Invoking graph (running all nodes)...")
        print("-" * 40)
        final_state = graph.invoke(initial_state)
        print("-" * 40)

        # Step 4: Verify results
        verify_state(final_state)

        # Success
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED - Graph flow verified!")
        print("=" * 60)
        print("\nSummary:")
        print(f"  - Asset: {final_state['asset_symbol']}")
        print(f"  - Technical: {final_state['technical_analysis']['signal']}")
        print(f"  - Sentiment Fear: {final_state['sentiment_analysis']['fear_score']}")
        print(f"  - Vision Valid: {final_state['vision_analysis']['is_valid']}")
        print(f"  - Decision: {final_state['final_decision']['action']}")
        print("\nGraph is ready for Epic 2 agent implementations!")

        return 0

    except AssertionError as e:
        print(f"\n[ERROR] Verification failed: {e}")
        return 1
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""
LangGraph State Graph Definition for the Council of AI Agents.

Story 2.1: LangGraph State Machine Setup
Story 5.9: Token Optimization - Conditional Vision

This module defines and builds the LangGraph state machine that
orchestrates the AI agents in the trading decision pipeline.

Graph Flow (V2 - Token Optimized):
    Start -> SentimentAgent -> TechnicalAgent -> [Conditional] -> MasterNode -> End
                                                      |
                                               (if potential BUY)
                                                      v
                                                VisionAgent

Vision is only called when sentiment + technical suggest a potential BUY,
reducing token usage by ~90% (Vision sends chart images = 50K tokens each).

Usage:
    from core.graph import build_council_graph

    graph = build_council_graph()
    initial_state = create_initial_state(asset_symbol="SOLUSD", ...)
    final_state = graph.invoke(initial_state)
"""

import logging
from typing import Any, Literal

from langgraph.graph import END, StateGraph

from core.state import GraphState
from nodes.master import master_node
from nodes.sentiment import sentiment_node
from nodes.technical import technical_node
from nodes.vision import vision_node

logger = logging.getLogger(__name__)


def should_run_vision(state: GraphState) -> Literal["vision_agent", "master_node"]:
    """
    Router function: Decide whether to run Vision agent.

    Story 5.9: Token Optimization

    Vision analysis is expensive (~50K tokens per chart image).
    Only run Vision when sentiment + technical suggest a potential BUY:
    - Fear score < 50 (some level of fear present)
    - Technical signal is BULLISH or NEUTRAL (not BEARISH)

    This reduces Vision calls from ~240/day to ~20/day, saving ~11M tokens.

    Args:
        state: Current graph state after sentiment + technical analysis

    Returns:
        "vision_agent" if Vision should run, "master_node" to skip Vision
    """
    sentiment = state.get("sentiment_analysis") or {}
    technical = state.get("technical_analysis") or {}
    asset = state.get("asset_symbol", "UNKNOWN")

    fear_score = sentiment.get("fear_score", 50)
    tech_signal = technical.get("signal", "NEUTRAL")

    # Conditions for running Vision (potential BUY opportunity)
    has_fear = fear_score < 50  # Some fear present
    not_bearish = tech_signal != "BEARISH"  # Not actively bearish

    if has_fear and not_bearish:
        logger.info(
            f"[Router] {asset}: Running Vision (fear={fear_score}, signal={tech_signal})"
        )
        return "vision_agent"
    else:
        logger.info(
            f"[Router] {asset}: Skipping Vision (fear={fear_score}, signal={tech_signal}) - saving tokens"
        )
        return "master_node"


def build_council_graph() -> Any:
    """
    Build the Council of Agents state graph.

    Constructs a LangGraph StateGraph with conditional Vision execution
    to optimize token usage (Story 5.9).

    Returns:
        Compiled StateGraph ready for invocation

    Graph Structure (Token Optimized):
        - Entry: sentiment_agent
        - Flow: sentiment -> technical -> [conditional] -> master
        - Vision only runs if sentiment + technical suggest potential BUY
        - Exit: END after master_node

    Token Savings:
        Vision sends ~50K tokens per chart image.
        By only running Vision on potential BUYs, we reduce from
        ~240 calls/day to ~20 calls/day, saving ~11M tokens/day.

    Example:
        graph = build_council_graph()
        result = graph.invoke({
            "asset_symbol": "SOLUSD",
            "candles_data": [...],
            "sentiment_data": [...],
            ...
        })
    """
    logger.info("Building Council of Agents state graph (token-optimized)...")

    # Create the state graph with GraphState type
    workflow = StateGraph(GraphState)

    # Add nodes - each node is a function that processes state
    workflow.add_node("sentiment_agent", sentiment_node)
    workflow.add_node("technical_agent", technical_node)
    workflow.add_node("vision_agent", vision_node)
    workflow.add_node("master_node", master_node)

    # Define edges with conditional Vision execution
    workflow.set_entry_point("sentiment_agent")

    # Sentiment -> Technical (always)
    workflow.add_edge("sentiment_agent", "technical_agent")

    # Technical -> Conditional routing (Vision or skip to Master)
    workflow.add_conditional_edges(
        "technical_agent",
        should_run_vision,
        {
            "vision_agent": "vision_agent",
            "master_node": "master_node",
        }
    )

    # Vision -> Master (if Vision ran)
    workflow.add_edge("vision_agent", "master_node")

    # Master node exits to END
    workflow.add_edge("master_node", END)

    # Compile the graph
    compiled_graph = workflow.compile()

    logger.info("Council graph compiled successfully (Vision conditional)")

    return compiled_graph


# Future V2: Parallel execution pattern
# This pattern allows Sentiment, Technical, and Vision agents to run
# concurrently since they are independent of each other.
#
# def build_council_graph_parallel() -> Any:
#     """
#     Build the Council graph with parallel agent execution.
#
#     In this version, the three analysis agents run in parallel,
#     and MasterNode waits for all to complete before synthesizing.
#
#     This is more efficient but requires careful state management.
#     """
#     from langgraph.graph import START
#
#     workflow = StateGraph(GraphState)
#
#     # Add nodes
#     workflow.add_node("sentiment_agent", sentiment_node)
#     workflow.add_node("technical_agent", technical_node)
#     workflow.add_node("vision_agent", vision_node)
#     workflow.add_node("master_node", master_node)
#
#     # Parallel edges from START
#     workflow.add_edge(START, "sentiment_agent")
#     workflow.add_edge(START, "technical_agent")
#     workflow.add_edge(START, "vision_agent")
#
#     # All converge to master_node
#     workflow.add_edge("sentiment_agent", "master_node")
#     workflow.add_edge("technical_agent", "master_node")
#     workflow.add_edge("vision_agent", "master_node")
#
#     # Master exits
#     workflow.add_edge("master_node", END)
#
#     return workflow.compile()


# Cached compiled graph instance
_council_graph = None


def get_council_graph() -> Any:
    """
    Get the cached Council graph instance.

    This function ensures the graph is only compiled once and reused
    for all subsequent invocations. Graph compilation is a relatively
    expensive operation, so caching is important for performance.

    Returns:
        Compiled StateGraph (cached)

    Usage:
        graph = get_council_graph()
        result = graph.invoke(initial_state)
    """
    global _council_graph
    if _council_graph is None:
        _council_graph = build_council_graph()
    return _council_graph

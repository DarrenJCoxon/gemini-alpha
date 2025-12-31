"""
LangGraph State Graph Definition for the Council of AI Agents.

Story 2.1: LangGraph State Machine Setup

This module defines and builds the LangGraph state machine that
orchestrates the AI agents in the trading decision pipeline.

Graph Flow (V1 - Sequential):
    Start -> SentimentAgent -> TechnicalAgent -> VisionAgent -> MasterNode -> End

Future Optimization (V2 - Parallel):
    The three analysis agents (Sentiment, Technical, Vision) are independent
    and could run in parallel, with MasterNode waiting for all to complete.

Usage:
    from core.graph import build_council_graph

    graph = build_council_graph()
    initial_state = create_initial_state(asset_symbol="SOLUSD", ...)
    final_state = graph.invoke(initial_state)
"""

import logging
from typing import Any

from langgraph.graph import END, StateGraph

from core.state import GraphState
from nodes.master import master_node
from nodes.sentiment import sentiment_node
from nodes.technical import technical_node
from nodes.vision import vision_node

logger = logging.getLogger(__name__)


def build_council_graph() -> Any:
    """
    Build the Council of Agents state graph.

    Constructs a LangGraph StateGraph with all agent nodes and
    edges defining the execution flow. Currently implements
    sequential execution for simplicity.

    Returns:
        Compiled StateGraph ready for invocation

    Graph Structure:
        - Entry: sentiment_agent
        - Flow: sentiment -> technical -> vision -> master
        - Exit: END after master_node

    Example:
        graph = build_council_graph()
        result = graph.invoke({
            "asset_symbol": "SOLUSD",
            "candles_data": [...],
            "sentiment_data": [...],
            ...
        })
    """
    logger.info("Building Council of Agents state graph...")

    # Create the state graph with GraphState type
    workflow = StateGraph(GraphState)

    # Add nodes - each node is a function that processes state
    workflow.add_node("sentiment_agent", sentiment_node)
    workflow.add_node("technical_agent", technical_node)
    workflow.add_node("vision_agent", vision_node)
    workflow.add_node("master_node", master_node)

    # Define edges (sequential flow for V1)
    # The entry point is where execution starts
    workflow.set_entry_point("sentiment_agent")

    # Connect nodes in sequence
    workflow.add_edge("sentiment_agent", "technical_agent")
    workflow.add_edge("technical_agent", "vision_agent")
    workflow.add_edge("vision_agent", "master_node")

    # Master node exits to END
    workflow.add_edge("master_node", END)

    # Compile the graph
    compiled_graph = workflow.compile()

    logger.info("Council graph compiled successfully")

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

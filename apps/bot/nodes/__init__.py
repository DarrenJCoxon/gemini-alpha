"""
LangGraph Agent Nodes for the Council of AI Agents.

Story 2.1: LangGraph State Machine Setup

This package contains all agent nodes that process the GraphState
in the trading decision pipeline:

- SentimentAgent: Analyzes social sentiment and fear/greed indicators
- TechnicalAgent: Performs technical analysis on price data
- VisionAgent: Analyzes chart patterns using vision LLM
- MasterNode: Synthesizes all analyses into final trading decision

Each node is a function that takes GraphState and returns GraphState,
following LangGraph's functional node pattern.
"""

from nodes.master import master_node
from nodes.sentiment import sentiment_node
from nodes.technical import technical_node
from nodes.vision import vision_node

__all__ = [
    "master_node",
    "sentiment_node",
    "technical_node",
    "vision_node",
]

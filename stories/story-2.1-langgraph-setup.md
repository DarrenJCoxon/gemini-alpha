# Story 2.1: LangGraph State Machine Setup

**Status:** Approved
**Epic:** 2 - Council of AI Agents (LangGraph)
**Priority:** Critical (Blocking for Epic 2)

---

## Story

**As a** AI Engineer,
**I want** to configure the LangGraph state definition and basic control flow,
**so that** we can pass the "Trading Context" between different agents in a structured way.

---

## Acceptance Criteria

1. `GraphState` TypedDict defined containing keys for: `asset_symbol`, `candles_data`, `sentiment_data`, `technical_analysis`, `sentiment_analysis`, `vision_analysis`, `final_decision`.
2. Basic Graph constructed with nodes: `SentimentAgent`, `TechnicalAgent`, `VisionAgent`, `MasterNode`.
3. Edges connected sequentially or in parallel (as per architecture).
4. Mock/Stub nodes created to verify the graph compiles and runs through the flow without errors.

---

## Tasks / Subtasks

### Phase 1: Dependency Installation

- [ ] **Install LangGraph and related dependencies**
  - [ ] Navigate to `apps/bot/` directory
  - [ ] Add to `requirements.txt`:
    ```
    langgraph>=0.0.10
    langchain>=0.1.0
    langchain-google-vertexai>=0.0.6
    google-cloud-aiplatform>=1.38.0
    ```
  - [ ] Install dependencies: `pip install -r requirements.txt`
  - [ ] Verify installation: `python -c "import langgraph; print(langgraph.__version__)"`

- [ ] **Configure Vertex AI credentials**
  - [ ] Add to `.env.example`:
    ```
    GOOGLE_CLOUD_PROJECT=your-project-id
    GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
    ```
  - [ ] Create `apps/bot/config.py` for environment variable loading
  - [ ] Verify Vertex AI SDK can initialize (will test in Story 2.2)

### Phase 2: Define Graph State

- [ ] **Create state definition module**
  - [ ] Create file `apps/bot/core/state.py`
  - [ ] Define `GraphState` TypedDict with all required fields:
    ```python
    from typing import TypedDict, Optional, List, Dict, Any
    from datetime import datetime

    class CandleData(TypedDict):
        timestamp: datetime
        open: float
        high: float
        low: float
        close: float
        volume: float

    class TechnicalAnalysis(TypedDict):
        signal: str  # "BULLISH", "BEARISH", "NEUTRAL"
        strength: int  # 0-100
        rsi: float
        sma_50: float
        sma_200: float
        volume_delta: float
        reasoning: str

    class SentimentAnalysis(TypedDict):
        fear_score: int  # 0-100 (lower = more fear)
        summary: str
        source_count: int

    class VisionAnalysis(TypedDict):
        patterns_detected: List[str]
        confidence_score: int  # 0-100
        description: str
        is_valid: bool  # False if "scam wick" detected

    class FinalDecision(TypedDict):
        action: str  # "BUY", "SELL", "HOLD"
        confidence: int  # 0-100
        reasoning: str
        timestamp: datetime

    class GraphState(TypedDict):
        asset_symbol: str
        candles_data: List[CandleData]
        sentiment_data: List[Dict[str, Any]]
        technical_analysis: Optional[TechnicalAnalysis]
        sentiment_analysis: Optional[SentimentAnalysis]
        vision_analysis: Optional[VisionAnalysis]
        final_decision: Optional[FinalDecision]
        error: Optional[str]
    ```
  - [ ] Add docstrings explaining each field's purpose
  - [ ] Export from `apps/bot/core/__init__.py`

### Phase 3: Create Placeholder Nodes

- [ ] **Create sentinel node directory structure**
  - [ ] Create `apps/bot/nodes/` directory
  - [ ] Create `apps/bot/nodes/__init__.py`

- [ ] **Create Technical Agent placeholder**
  - [ ] Create `apps/bot/nodes/technical.py`
  - [ ] Implement stub function:
    ```python
    from core.state import GraphState

    def technical_node(state: GraphState) -> GraphState:
        """Technical Analysis Agent - Stub implementation."""
        print(f"[TechnicalAgent] Processing {state['asset_symbol']}")
        state["technical_analysis"] = {
            "signal": "NEUTRAL",
            "strength": 50,
            "rsi": 50.0,
            "sma_50": 0.0,
            "sma_200": 0.0,
            "volume_delta": 0.0,
            "reasoning": "Stub implementation"
        }
        return state
    ```

- [ ] **Create Sentiment Agent placeholder**
  - [ ] Create `apps/bot/nodes/sentiment.py`
  - [ ] Implement stub function:
    ```python
    from core.state import GraphState

    def sentiment_node(state: GraphState) -> GraphState:
        """Sentiment Analysis Agent - Stub implementation."""
        print(f"[SentimentAgent] Processing {state['asset_symbol']}")
        state["sentiment_analysis"] = {
            "fear_score": 50,
            "summary": "Stub implementation - neutral sentiment",
            "source_count": 0
        }
        return state
    ```

- [ ] **Create Vision Agent placeholder**
  - [ ] Create `apps/bot/nodes/vision.py`
  - [ ] Implement stub function:
    ```python
    from core.state import GraphState

    def vision_node(state: GraphState) -> GraphState:
        """Vision Analysis Agent - Stub implementation."""
        print(f"[VisionAgent] Processing {state['asset_symbol']}")
        state["vision_analysis"] = {
            "patterns_detected": [],
            "confidence_score": 50,
            "description": "Stub implementation - no patterns analyzed",
            "is_valid": True
        }
        return state
    ```

- [ ] **Create Master Node placeholder**
  - [ ] Create `apps/bot/nodes/master.py`
  - [ ] Implement stub function:
    ```python
    from core.state import GraphState
    from datetime import datetime

    def master_node(state: GraphState) -> GraphState:
        """Master Synthesis Node - Stub implementation."""
        print(f"[MasterNode] Synthesizing decision for {state['asset_symbol']}")
        state["final_decision"] = {
            "action": "HOLD",
            "confidence": 50,
            "reasoning": "Stub implementation - defaulting to HOLD",
            "timestamp": datetime.utcnow()
        }
        return state
    ```

### Phase 4: Construct State Graph

- [ ] **Create graph definition module**
  - [ ] Create `apps/bot/core/graph.py`
  - [ ] Import LangGraph components:
    ```python
    from langgraph.graph import StateGraph, END
    from core.state import GraphState
    from nodes.technical import technical_node
    from nodes.sentiment import sentiment_node
    from nodes.vision import vision_node
    from nodes.master import master_node
    ```

- [ ] **Build sequential graph (V1)**
  - [ ] Define graph with sequential flow:
    ```python
    def build_council_graph() -> StateGraph:
        """Build the Council of Agents state graph."""
        workflow = StateGraph(GraphState)

        # Add nodes
        workflow.add_node("sentiment_agent", sentiment_node)
        workflow.add_node("technical_agent", technical_node)
        workflow.add_node("vision_agent", vision_node)
        workflow.add_node("master_node", master_node)

        # Define edges (sequential for V1)
        workflow.set_entry_point("sentiment_agent")
        workflow.add_edge("sentiment_agent", "technical_agent")
        workflow.add_edge("technical_agent", "vision_agent")
        workflow.add_edge("vision_agent", "master_node")
        workflow.add_edge("master_node", END)

        return workflow.compile()
    ```
  - [ ] Export `build_council_graph` function

- [ ] **Optional: Implement parallel execution branch**
  - [ ] Document parallel execution pattern for future optimization:
    ```python
    # Future V2: Parallel execution pattern
    # workflow.add_edge(START, "sentiment_agent")
    # workflow.add_edge(START, "technical_agent")
    # workflow.add_edge(START, "vision_agent")
    # workflow.add_edge("sentiment_agent", "master_node")
    # workflow.add_edge("technical_agent", "master_node")
    # workflow.add_edge("vision_agent", "master_node")
    ```
  - [ ] Add TODO comment noting this optimization for later

### Phase 5: Create Verification Script

- [ ] **Create test script**
  - [ ] Create `apps/bot/scripts/` directory
  - [ ] Create `apps/bot/scripts/test_graph.py`:
    ```python
    #!/usr/bin/env python3
    """
    Verification script for LangGraph Council setup.
    Runs the graph with dummy data to verify flow.
    """
    import sys
    sys.path.insert(0, '..')

    from core.graph import build_council_graph
    from core.state import GraphState
    from datetime import datetime

    def create_test_state() -> GraphState:
        """Create a test state with dummy data."""
        return {
            "asset_symbol": "SOLUSD",
            "candles_data": [
                {
                    "timestamp": datetime.utcnow(),
                    "open": 100.0,
                    "high": 105.0,
                    "low": 98.0,
                    "close": 103.0,
                    "volume": 10000.0
                }
            ],
            "sentiment_data": [
                {"text": "Test sentiment data", "source": "test"}
            ],
            "technical_analysis": None,
            "sentiment_analysis": None,
            "vision_analysis": None,
            "final_decision": None,
            "error": None
        }

    def main():
        print("=" * 60)
        print("LangGraph Council Verification Test")
        print("=" * 60)

        # Build graph
        print("\n[1] Building Council graph...")
        graph = build_council_graph()
        print("    Graph compiled successfully!")

        # Create test state
        print("\n[2] Creating test state...")
        initial_state = create_test_state()
        print(f"    Asset: {initial_state['asset_symbol']}")

        # Run graph
        print("\n[3] Invoking graph...")
        print("-" * 40)
        final_state = graph.invoke(initial_state)
        print("-" * 40)

        # Verify results
        print("\n[4] Verifying results...")

        assert final_state["technical_analysis"] is not None, "Technical analysis missing"
        print(f"    Technical: {final_state['technical_analysis']['signal']}")

        assert final_state["sentiment_analysis"] is not None, "Sentiment analysis missing"
        print(f"    Sentiment Fear Score: {final_state['sentiment_analysis']['fear_score']}")

        assert final_state["vision_analysis"] is not None, "Vision analysis missing"
        print(f"    Vision Valid: {final_state['vision_analysis']['is_valid']}")

        assert final_state["final_decision"] is not None, "Final decision missing"
        print(f"    Final Decision: {final_state['final_decision']['action']}")

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED - Graph flow verified!")
        print("=" * 60)

        return 0

    if __name__ == "__main__":
        sys.exit(main())
    ```

- [ ] **Run verification**
  - [ ] Navigate to `apps/bot/`
  - [ ] Execute: `python scripts/test_graph.py`
  - [ ] Verify all 4 nodes execute in order
  - [ ] Verify final state contains all analysis fields populated
  - [ ] Capture output for documentation

### Phase 6: Integration with Main Entry Point

- [ ] **Update main.py to use graph**
  - [ ] Add import for graph builder
  - [ ] Create function to load state from database (placeholder)
  - [ ] Add endpoint or scheduler hook for graph invocation
  - [ ] Example integration:
    ```python
    from core.graph import build_council_graph

    # Build graph once at startup
    council_graph = build_council_graph()

    async def run_council_session(asset_symbol: str):
        """Run a council session for the given asset."""
        # TODO: Load candles and sentiment from DB
        state = create_initial_state(asset_symbol)
        result = council_graph.invoke(state)
        return result
    ```

---

## Dev Notes

### Architecture Context

**Reference:** `docs/core/architecture.md` Section 6.1 (Backend Components)

The Council Engine is the core decision-making component of ContrarianAI. It uses LangGraph to orchestrate multiple AI agents:

```
State Graph Flow:
Start -> SentimentAgent -> TechnicalAgent -> VisionAgent -> MasterNode -> End

Alternative (V2): Parallel execution
Start ─┬─> SentimentAgent ──┐
       ├─> TechnicalAgent ──┼─> MasterNode -> End
       └─> VisionAgent ─────┘
```

**Key Design Decisions:**
1. **Sequential vs Parallel:** V1 uses sequential flow for simplicity. Parallel execution can be added later since Sentiment, Technical, and Vision agents are independent of each other.
2. **State Immutability:** LangGraph prefers immutable state updates. Each node should return a new state dict rather than mutating in place.
3. **Error Handling:** Add an `error` field to GraphState to capture failures without crashing the entire flow.

### Technical Specifications

**LangGraph Concepts:**
- `StateGraph`: Defines the graph structure with typed state
- `TypedDict`: Ensures type safety for state passing between nodes
- `END`: Special constant marking terminal node
- `compile()`: Converts graph definition to executable

**File Structure After Completion:**
```
apps/bot/
├── core/
│   ├── __init__.py
│   ├── state.py          # GraphState TypedDict
│   └── graph.py          # StateGraph definition
├── nodes/
│   ├── __init__.py
│   ├── technical.py      # Technical Agent (stub)
│   ├── sentiment.py      # Sentiment Agent (stub)
│   ├── vision.py         # Vision Agent (stub)
│   └── master.py         # Master Node (stub)
├── scripts/
│   └── test_graph.py     # Verification script
└── requirements.txt      # Updated with LangGraph deps
```

### Implementation Guidance

**State Design Rationale:**
- `candles_data`: List of OHLCV candles for technical analysis and chart generation
- `sentiment_data`: Raw sentiment log entries from database
- `technical_analysis`: Output from Technical Agent (RSI, SMAs, signal)
- `sentiment_analysis`: Output from Sentiment Agent (fear score, summary)
- `vision_analysis`: Output from Vision Agent (patterns, validity)
- `final_decision`: Master Node synthesis (action, reasoning)
- `error`: Captures any node failures for graceful degradation

**Vertex AI Configuration:**
```python
# config.py
import os
from google.cloud import aiplatform

def init_vertex_ai():
    """Initialize Vertex AI with project credentials."""
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("VERTEX_AI_LOCATION", "us-central1")

    aiplatform.init(
        project=project_id,
        location=location
    )
```

### Dependencies & Prerequisites

**Required Completions:**
- Story 1.1: Monorepo setup with Python environment
- Story 1.2: Database schema (for understanding data models)

**Environment Requirements:**
- Python 3.11+
- Virtual environment activated in `apps/bot/`
- Google Cloud credentials configured (can be placeholder for now)

### Downstream Dependencies

- **Story 2.2:** Implements actual Technical and Sentiment agent logic
- **Story 2.3:** Implements Vision Agent with chart generation
- **Story 2.4:** Implements Master Node synthesis and logging
- **All Epic 3-4 stories:** Depend on working graph flow

---

## Testing Strategy

### Unit Tests

- [ ] Test `GraphState` TypedDict validation with valid data
- [ ] Test `GraphState` TypedDict validation with missing fields
- [ ] Test each placeholder node returns expected stub values
- [ ] Test graph compilation does not throw errors

### Integration Tests

- [ ] Test full graph invocation with dummy state
- [ ] Test state propagation between all nodes
- [ ] Test graph handles empty candles_data gracefully
- [ ] Test graph handles empty sentiment_data gracefully

### Manual Testing Scenarios

1. Run `scripts/test_graph.py` - verify all nodes execute
2. Modify initial state values - verify they propagate correctly
3. Add print statements in each node - verify execution order
4. Test with intentionally broken state - verify error handling

### Acceptance Criteria Validation

- [ ] AC1: `GraphState` TypedDict contains all 7 required keys
- [ ] AC2: Graph has 4 nodes: SentimentAgent, TechnicalAgent, VisionAgent, MasterNode
- [ ] AC3: Edges connect nodes (sequential for V1)
- [ ] AC4: `test_graph.py` runs without errors and all assertions pass

---

## Technical Considerations

### Security

- Google Cloud credentials must never be committed to repository
- Use environment variables for all sensitive configuration
- Service account should have minimal required permissions

### Performance

- Graph compilation is a one-time operation (cache the compiled graph)
- Sequential execution is simpler but slower than parallel
- Plan for parallel execution optimization in V2

### Scalability

- State design supports adding new agents in future
- Graph structure allows inserting nodes without breaking flow
- Consider state checkpointing for debugging long sessions

### Edge Cases

- Handle case where candles_data is empty (no historical data)
- Handle case where sentiment_data is empty (no social signals)
- Handle case where Vertex AI credentials are invalid
- Handle node timeout (set reasonable limits)

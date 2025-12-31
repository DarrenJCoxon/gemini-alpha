### **File 1: `docs/stories/story-2.1.langgraph-setup.md`**

```markdown
# Story 2.1: LangGraph State Machine Setup

**Status:** Draft

## Story
**As a** AI Engineer,
**I want** to configure the LangGraph state definition and basic control flow,
**so that** we can pass the "Trading Context" between different agents in a structured way.

## Acceptance Criteria
1.  `GraphState` TypedDict defined containing keys for: `asset_symbol`, `candles_data`, `sentiment_data`, `technical_analysis`, `sentiment_analysis`, `vision_analysis`, `final_decision`.
2.  Basic Graph constructed with nodes: `SentimentAgent`, `TechnicalAgent`, `VisionAgent`, `MasterNode`.
3.  Edges connected sequentially or in parallel (as per architecture).
4.  Mock/Stub nodes created to verify the graph compiles and runs through the flow without errors.

## Tasks / Subtasks
- [ ] Dependency Installation
    - [ ] Install `langgraph`, `langchain`, `langchain-google-vertexai` in `apps/bot`.
- [ ] Define State
    - [ ] Create `apps/bot/core/state.py`.
    - [ ] Define `AgentState` using `TypedDict`.
- [ ] Construct Graph
    - [ ] Create `apps/bot/core/graph.py`.
    - [ ] Define placeholder functions for each node.
    - [ ] Define `workflow = StateGraph(AgentState)`.
    - [ ] Add nodes and edges (Start -> Sentiment -> Technical -> Vision -> Master -> End).
    - [ ] Compile the graph.
- [ ] Verification Script
    - [ ] Create a test script `scripts/test_graph.py` to invoke the graph with dummy input and print the state transitions.

## Dev Notes
- **Parallelization:** Consider running Sentiment, Technical, and Vision nodes in parallel since they don't depend on each other, only on the raw data. The Master node depends on all of them.
- **Reference:** See `docs/architecture.md` Section 6.1 (Backend Components).
```

---

### **File 2: `docs/stories/story-2.2.sentiment-technical-agents.md`**

```markdown
# Story 2.2: Sentiment & Technical Agents

**Status:** Draft

## Story
**As a** Quant,
**I want** to implement the logic for the Text (Sentiment) and Data (Technical) agents,
**so that** they produce scored outputs from raw database data.

## Acceptance Criteria
1.  **Technical Agent:** Calculates RSI (14), SMA (50/200), and Volume Delta using `pandas-ta`.
    *   Output: Structured dict with `signal` (BULLISH/BEARISH/NEUTRAL) and `strength` (0-100).
2.  **Sentiment Agent:** Uses Gemini 3 (Flash) to analyze text logs.
    *   Output: Structured dict with `fear_score` (0-100) and `summary`.
3.  Both agents update the `GraphState` correctly.
4.  Unit tests verify calculations and prompt outputs.

## Tasks / Subtasks
- [ ] Technical Agent Implementation
    - [ ] Install `pandas` and `pandas-ta`.
    - [ ] Implement `technical_node` in `apps/bot/nodes/technical.py`.
    - [ ] Logic: Convert DB candles to DataFrame -> Apply Indicators -> Simple heuristic scoring (e.g., if Price > SMA200 + RSI < 30 = Bullish).
- [ ] Sentiment Agent Implementation
    - [ ] Configure Vertex AI SDK with Gemini 3 Flash.
    - [ ] Create System Prompt: "You are a Crypto Sentiment Analyst. Analyze these tweets/news..."
    - [ ] Implement `sentiment_node` in `apps/bot/nodes/sentiment.py`.
    - [ ] Logic: Retrieve recent `SentimentLog` entries -> Send to LLM -> Parse JSON output.
- [ ] Integration
    - [ ] Hook nodes into the main LangGraph.

## Dev Notes
- **Technical Logic:** Keep it simple for V1. Using `pandas-ta` is efficient.
- **Sentiment Prompt:** Ensure output is strictly JSON to avoid parsing errors. Use Gemini's "Response Schema" feature if available.
```

---

### **File 3: `docs/stories/story-2.3.vision-agent.md`**

```markdown
# Story 2.3: Vision Agent & Chart Generation

**Status:** Draft

## Story
**As a** Developer,
**I want** to generate a chart image and pass it to Gemini Vision,
**so that** the AI can "see" price patterns and identify "scam wicks" or accumulation zones.

## Acceptance Criteria
1.  Python `mplfinance` (or `matplotlib`) generates a static PNG of the last 100 candles (15m timeframe).
2.  Image passed to **Gemini 3 Pro** (Vision model).
3.  Prompt instructs AI to look for specific patterns (Double Bottom, Wyckoff Spring, Support retests).
4.  Output is a text description + "Visual Confidence" score.

## Tasks / Subtasks
- [ ] Chart Generation Utility
    - [ ] Install `mplfinance`.
    - [ ] Create function `generate_chart_image(candles) -> bytes`.
    - [ ] Style chart: Dark background, Green/Red candles, maybe overlay MA lines.
- [ ] Vision Node Implementation
    - [ ] Create `vision_node` in `apps/bot/nodes/vision.py`.
    - [ ] Prompt Engineering: "Analyze this crypto chart. Identify support levels and reversal patterns..."
    - [ ] Call Vertex AI with Image + Prompt.
- [ ] State Update
    - [ ] Store analysis in `GraphState['vision_analysis']`.

## Dev Notes
- **Performance:** Generating images can be slow. Ensure this doesn't time out the 15-minute window. Keep the plot simple.
- **Privacy:** We don't need to save these images to disk/S3 permanently for V1, just keep in memory for the API call, OR save to temp folder if debugging needed.
```

---

### **File 4: `docs/stories/story-2.4.master-node-logging.md`**

```markdown
# Story 2.4: Master Node & Signal Logging

**Status:** Draft

## Story
**As a** Strategy Lead,
**I want** the Master Node to synthesize the 3 agent inputs and log the decision to the database,
**so that** we can audit the "Council's" performance (Paper Trading).

## Acceptance Criteria
1.  Master Node prompt written: "Act as a Risk Manager. Review Sentiment (Fear: {x}), Technicals ({y}), Vision ({z}). Only Buy if..."
2.  Strict logic applied: **Sentiment < 20 AND Technicals = Bullish**.
3.  Result saved to `CouncilSession` database table.
4.  NO trade executed yet (Paper Trading Mode only).

## Tasks / Subtasks
- [ ] Master Node Implementation
    - [ ] Create `master_node` in `apps/bot/nodes/master.py`.
    - [ ] Construct Context Prompt containing outputs from previous 3 agents.
    - [ ] Call Gemini 3 Pro to make final decision (BUY, SELL, HOLD) + Reasoning.
- [ ] Database Logger
    - [ ] Create service `apps/bot/services/session_logger.py`.
    - [ ] Function to write `CouncilSession` record using SQLModel.
- [ ] Main Loop Integration
    - [ ] Update `main.py` scheduler to run the full `workflow.invoke()` chain.
    - [ ] Log the result to console and DB.

## Dev Notes
- **Reasoning Log:** This is the most important field for the UI. Ensure the LLM explains *why* it made the decision in clear text.
- **Safety:** Verify `Trade` table is NOT touched in this story. We are strictly logging `CouncilSession`.
```

---

**Epic 2 is mapped.**

Once **Story 1.1** (Monorepo Setup) is complete, you can technically start **Story 2.1** (LangGraph) in parallel with the data ingestors if you have multiple developers (or multiple agents working).

**Ready to move to Epic 3 or start coding?**
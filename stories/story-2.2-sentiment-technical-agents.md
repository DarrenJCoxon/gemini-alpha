# Story 2.2: Sentiment & Technical Agents

**Status:** approved 
**Epic:** 2 - Council of AI Agents (LangGraph)
**Priority:** High

---

## Story

**As a** Quant,
**I want** to implement the logic for the Text (Sentiment) and Data (Technical) agents,
**so that** they produce scored outputs from raw database data.

---

## Acceptance Criteria

1. **Technical Agent:** Calculates RSI (14), SMA (50/200), and Volume Delta using `pandas-ta`.
   - Output: Structured dict with `signal` (BULLISH/BEARISH/NEUTRAL) and `strength` (0-100).
2. **Sentiment Agent:** Uses Gemini 3 (Flash) to analyze text logs.
   - Output: Structured dict with `fear_score` (0-100) and `summary`.
3. Both agents update the `GraphState` correctly.
4. Unit tests verify calculations and prompt outputs.

---

## Tasks / Subtasks

### Phase 1: Technical Agent Dependencies

- [ ] **Install pandas and pandas-ta**
  - [ ] Add to `apps/bot/requirements.txt`:
    ```
    pandas>=2.1.0
    pandas-ta>=0.3.14b0
    numpy>=1.26.0
    ```
  - [ ] Install: `pip install -r requirements.txt`
  - [ ] Verify: `python -c "import pandas_ta; print('pandas-ta installed')"`

### Phase 2: Technical Agent Implementation

- [ ] **Create technical analysis utilities**
  - [ ] Create `apps/bot/services/technical_utils.py`
  - [ ] Implement candle data to DataFrame converter:
    ```python
    import pandas as pd
    from typing import List, Dict, Any

    def candles_to_dataframe(candles: List[Dict[str, Any]]) -> pd.DataFrame:
        """Convert candle data list to pandas DataFrame."""
        df = pd.DataFrame(candles)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        df = df.sort_index()
        return df
    ```

- [ ] **Implement indicator calculations**
  - [ ] Add RSI calculation (14-period):
    ```python
    import pandas_ta as ta

    def calculate_rsi(df: pd.DataFrame, period: int = 14) -> float:
        """Calculate RSI indicator."""
        rsi = ta.rsi(df['close'], length=period)
        return rsi.iloc[-1] if not rsi.empty else 50.0
    ```
  - [ ] Add SMA calculations (50 and 200 period):
    ```python
    def calculate_smas(df: pd.DataFrame) -> tuple[float, float]:
        """Calculate SMA 50 and SMA 200."""
        sma_50 = ta.sma(df['close'], length=50)
        sma_200 = ta.sma(df['close'], length=200)
        return (
            sma_50.iloc[-1] if not sma_50.empty and not pd.isna(sma_50.iloc[-1]) else 0.0,
            sma_200.iloc[-1] if not sma_200.empty and not pd.isna(sma_200.iloc[-1]) else 0.0
        )
    ```
  - [ ] Add Volume Delta calculation:
    ```python
    def calculate_volume_delta(df: pd.DataFrame, period: int = 20) -> float:
        """Calculate volume change vs average."""
        if len(df) < period:
            return 0.0
        avg_volume = df['volume'].rolling(period).mean().iloc[-1]
        current_volume = df['volume'].iloc[-1]
        if avg_volume == 0:
            return 0.0
        return ((current_volume - avg_volume) / avg_volume) * 100
    ```

- [ ] **Implement signal scoring heuristic**
  - [ ] Create scoring function:
    ```python
    def calculate_technical_signal(
        rsi: float,
        sma_50: float,
        sma_200: float,
        current_price: float,
        volume_delta: float
    ) -> tuple[str, int, str]:
        """
        Calculate technical signal based on indicators.

        Returns: (signal, strength, reasoning)

        Signal Logic:
        - BULLISH: Price > SMA200, RSI < 40 (oversold bounce), positive volume
        - BEARISH: Price < SMA200, RSI > 70 (overbought), negative volume
        - NEUTRAL: Mixed signals
        """
        bullish_points = 0
        bearish_points = 0
        reasons = []

        # Price vs SMA200 (Golden Cross territory)
        if sma_200 > 0 and current_price > sma_200:
            bullish_points += 30
            reasons.append(f"Price ${current_price:.2f} above SMA200 ${sma_200:.2f}")
        elif sma_200 > 0:
            bearish_points += 30
            reasons.append(f"Price ${current_price:.2f} below SMA200 ${sma_200:.2f}")

        # RSI conditions
        if rsi < 30:
            bullish_points += 40  # Heavily oversold = buy opportunity
            reasons.append(f"RSI {rsi:.1f} indicates extreme oversold")
        elif rsi < 40:
            bullish_points += 20
            reasons.append(f"RSI {rsi:.1f} indicates oversold")
        elif rsi > 70:
            bearish_points += 40
            reasons.append(f"RSI {rsi:.1f} indicates overbought")
        elif rsi > 60:
            bearish_points += 20
            reasons.append(f"RSI {rsi:.1f} approaching overbought")

        # Volume confirmation
        if volume_delta > 50:
            bullish_points += 15
            reasons.append(f"Volume {volume_delta:.1f}% above average (accumulation)")
        elif volume_delta < -30:
            bearish_points += 15
            reasons.append(f"Volume {volume_delta:.1f}% below average")

        # SMA crossover (50 vs 200)
        if sma_50 > 0 and sma_200 > 0:
            if sma_50 > sma_200:
                bullish_points += 15
                reasons.append("SMA50 above SMA200 (Golden Cross)")
            else:
                bearish_points += 15
                reasons.append("SMA50 below SMA200 (Death Cross)")

        # Determine signal
        total_points = bullish_points + bearish_points
        if total_points == 0:
            return "NEUTRAL", 50, "Insufficient data for analysis"

        if bullish_points > bearish_points:
            strength = min(100, int((bullish_points / total_points) * 100))
            return "BULLISH", strength, " | ".join(reasons)
        elif bearish_points > bullish_points:
            strength = min(100, int((bearish_points / total_points) * 100))
            return "BEARISH", strength, " | ".join(reasons)
        else:
            return "NEUTRAL", 50, " | ".join(reasons)
    ```

- [ ] **Update Technical Node implementation**
  - [ ] Replace stub in `apps/bot/nodes/technical.py`:
    ```python
    from core.state import GraphState, TechnicalAnalysis
    from services.technical_utils import (
        candles_to_dataframe,
        calculate_rsi,
        calculate_smas,
        calculate_volume_delta,
        calculate_technical_signal
    )

    def technical_node(state: GraphState) -> GraphState:
        """
        Technical Analysis Agent.
        Analyzes price data using RSI, SMA, and Volume indicators.
        """
        print(f"[TechnicalAgent] Analyzing {state['asset_symbol']}...")

        candles = state.get("candles_data", [])
        if len(candles) < 14:  # Minimum for RSI calculation
            state["technical_analysis"] = {
                "signal": "NEUTRAL",
                "strength": 0,
                "rsi": 50.0,
                "sma_50": 0.0,
                "sma_200": 0.0,
                "volume_delta": 0.0,
                "reasoning": "Insufficient candle data for analysis"
            }
            return state

        try:
            df = candles_to_dataframe(candles)
            current_price = df['close'].iloc[-1]

            rsi = calculate_rsi(df)
            sma_50, sma_200 = calculate_smas(df)
            volume_delta = calculate_volume_delta(df)

            signal, strength, reasoning = calculate_technical_signal(
                rsi, sma_50, sma_200, current_price, volume_delta
            )

            state["technical_analysis"] = {
                "signal": signal,
                "strength": strength,
                "rsi": round(rsi, 2),
                "sma_50": round(sma_50, 2),
                "sma_200": round(sma_200, 2),
                "volume_delta": round(volume_delta, 2),
                "reasoning": reasoning
            }

            print(f"[TechnicalAgent] Signal: {signal} (Strength: {strength})")

        except Exception as e:
            state["technical_analysis"] = {
                "signal": "NEUTRAL",
                "strength": 0,
                "rsi": 50.0,
                "sma_50": 0.0,
                "sma_200": 0.0,
                "volume_delta": 0.0,
                "reasoning": f"Error during analysis: {str(e)}"
            }
            state["error"] = f"Technical analysis error: {str(e)}"

        return state
    ```

### Phase 3: Sentiment Agent Dependencies

- [ ] **Configure Vertex AI SDK for Gemini 3 Flash**
  - [ ] Add to `apps/bot/requirements.txt`:
    ```
    google-generativeai>=0.3.0
    ```
  - [ ] Install: `pip install -r requirements.txt`

- [ ] **Create Gemini client configuration**
  - [ ] Update `apps/bot/config.py`:
    ```python
    import os
    import google.generativeai as genai

    def get_gemini_flash_model():
        """Get configured Gemini 3 Flash model for text analysis."""
        api_key = os.getenv("GOOGLE_AI_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_AI_API_KEY not set")

        genai.configure(api_key=api_key)

        # Gemini 3 Flash - optimized for fast text analysis
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",  # Update to Gemini 3 when available
            generation_config={
                "temperature": 0.3,  # Low temperature for consistent analysis
                "max_output_tokens": 1024,
            }
        )
        return model
    ```
  - [ ] Add to `.env.example`:
    ```
    GOOGLE_AI_API_KEY=your-gemini-api-key
    ```

### Phase 4: Sentiment Agent Implementation

- [ ] **Create sentiment analysis utilities**
  - [ ] Create `apps/bot/services/sentiment_utils.py`:
    ```python
    import json
    from typing import List, Dict, Any, Optional

    SENTIMENT_SYSTEM_PROMPT = """You are a Crypto Sentiment Analyst specializing in detecting market fear and greed.

    Analyze the provided social media posts, news headlines, and market commentary.

    Focus on identifying:
    1. FEAR indicators: panic selling, capitulation, extreme pessimism, "it's going to zero"
    2. GREED indicators: FOMO, "to the moon", excessive optimism, price targets
    3. NEUTRAL indicators: factual analysis, balanced views

    Output your analysis as JSON with this exact structure:
    {
        "fear_score": <integer 0-100, where 0=extreme fear, 100=extreme greed>,
        "dominant_emotion": "<FEAR|GREED|NEUTRAL>",
        "summary": "<2-3 sentence summary of overall sentiment>",
        "key_themes": ["<theme1>", "<theme2>", "<theme3>"]
    }

    IMPORTANT:
    - For CONTRARIAN trading, we BUY when fear_score is LOW (extreme fear = buying opportunity)
    - A fear_score of 10-20 indicates extreme fear (potential buy signal)
    - A fear_score of 80-90 indicates extreme greed (potential sell signal)

    Output ONLY valid JSON, no additional text."""

    def format_sentiment_data_for_prompt(sentiment_data: List[Dict[str, Any]]) -> str:
        """Format sentiment log entries for LLM prompt."""
        if not sentiment_data:
            return "No sentiment data available."

        formatted = []
        for i, entry in enumerate(sentiment_data[:20], 1):  # Limit to 20 entries
            text = entry.get("text", entry.get("content", ""))
            source = entry.get("source", "unknown")
            timestamp = entry.get("timestamp", "")
            formatted.append(f"{i}. [{source}] {text}")

        return "\n".join(formatted)

    def parse_sentiment_response(response_text: str) -> Dict[str, Any]:
        """Parse LLM JSON response to sentiment dict."""
        try:
            # Try to extract JSON from response
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            data = json.loads(response_text.strip())

            return {
                "fear_score": int(data.get("fear_score", 50)),
                "dominant_emotion": data.get("dominant_emotion", "NEUTRAL"),
                "summary": data.get("summary", "Unable to determine sentiment"),
                "key_themes": data.get("key_themes", [])
            }
        except json.JSONDecodeError:
            return {
                "fear_score": 50,
                "dominant_emotion": "NEUTRAL",
                "summary": f"Failed to parse LLM response: {response_text[:100]}",
                "key_themes": []
            }
    ```

- [ ] **Update Sentiment Node implementation**
  - [ ] Replace stub in `apps/bot/nodes/sentiment.py`:
    ```python
    from core.state import GraphState, SentimentAnalysis
    from services.sentiment_utils import (
        SENTIMENT_SYSTEM_PROMPT,
        format_sentiment_data_for_prompt,
        parse_sentiment_response
    )
    from config import get_gemini_flash_model

    def sentiment_node(state: GraphState) -> GraphState:
        """
        Sentiment Analysis Agent.
        Uses Gemini 3 Flash to analyze social sentiment data.
        """
        print(f"[SentimentAgent] Analyzing sentiment for {state['asset_symbol']}...")

        sentiment_data = state.get("sentiment_data", [])

        if not sentiment_data:
            state["sentiment_analysis"] = {
                "fear_score": 50,  # Neutral when no data
                "summary": "No sentiment data available for analysis",
                "source_count": 0
            }
            return state

        try:
            # Format data for prompt
            formatted_data = format_sentiment_data_for_prompt(sentiment_data)

            # Build prompt
            user_prompt = f"""Analyze the following social media and news data for {state['asset_symbol']}:

{formatted_data}

Provide your sentiment analysis as JSON."""

            # Call Gemini Flash
            model = get_gemini_flash_model()
            response = model.generate_content([
                SENTIMENT_SYSTEM_PROMPT,
                user_prompt
            ])

            # Parse response
            parsed = parse_sentiment_response(response.text)

            state["sentiment_analysis"] = {
                "fear_score": parsed["fear_score"],
                "summary": parsed["summary"],
                "source_count": len(sentiment_data)
            }

            print(f"[SentimentAgent] Fear Score: {parsed['fear_score']}/100")

        except Exception as e:
            state["sentiment_analysis"] = {
                "fear_score": 50,
                "summary": f"Error during sentiment analysis: {str(e)}",
                "source_count": len(sentiment_data)
            }
            state["error"] = f"Sentiment analysis error: {str(e)}"

        return state
    ```

### Phase 5: Database Integration Helpers

- [ ] **Create data loading utilities**
  - [ ] Create `apps/bot/services/data_loader.py`:
    ```python
    from typing import List, Dict, Any, Optional
    from datetime import datetime, timedelta
    from sqlmodel import Session, select
    from database import engine
    # Import SQLModel models (mirrors Prisma schema)
    from models.candle import Candle
    from models.sentiment_log import SentimentLog
    from models.asset import Asset

    def load_candles_for_asset(
        asset_id: str,
        limit: int = 200,
        session: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Load recent candles for an asset."""
        own_session = session is None
        if own_session:
            session = Session(engine)

        try:
            statement = (
                select(Candle)
                .where(Candle.asset_id == asset_id)
                .order_by(Candle.timestamp.desc())
                .limit(limit)
            )
            candles = session.exec(statement).all()

            return [
                {
                    "timestamp": c.timestamp,
                    "open": float(c.open),
                    "high": float(c.high),
                    "low": float(c.low),
                    "close": float(c.close),
                    "volume": float(c.volume)
                }
                for c in reversed(candles)  # Oldest first for TA
            ]
        finally:
            if own_session:
                session.close()

    def load_sentiment_for_asset(
        asset_symbol: str,
        hours: int = 24,
        session: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Load recent sentiment logs for an asset."""
        own_session = session is None
        if own_session:
            session = Session(engine)

        try:
            since = datetime.utcnow() - timedelta(hours=hours)
            statement = (
                select(SentimentLog)
                .where(
                    SentimentLog.symbol == asset_symbol,
                    SentimentLog.timestamp >= since
                )
                .order_by(SentimentLog.timestamp.desc())
                .limit(50)
            )
            logs = session.exec(statement).all()

            return [
                {
                    "text": log.content,
                    "source": log.source,
                    "timestamp": log.timestamp
                }
                for log in logs
            ]
        finally:
            if own_session:
                session.close()
    ```

### Phase 6: Unit Tests

- [ ] **Create technical analysis tests**
  - [ ] Create `apps/bot/tests/test_technical.py`:
    ```python
    import pytest
    import pandas as pd
    from datetime import datetime, timedelta
    from services.technical_utils import (
        candles_to_dataframe,
        calculate_rsi,
        calculate_smas,
        calculate_volume_delta,
        calculate_technical_signal
    )

    @pytest.fixture
    def sample_candles():
        """Generate 200 sample candles for testing."""
        candles = []
        base_price = 100.0
        base_time = datetime.utcnow() - timedelta(hours=200)

        for i in range(200):
            # Simulate slight uptrend with noise
            price = base_price + (i * 0.1) + ((-1) ** i * 2)
            candles.append({
                "timestamp": base_time + timedelta(hours=i),
                "open": price - 1,
                "high": price + 2,
                "low": price - 2,
                "close": price,
                "volume": 10000 + (i * 100)
            })
        return candles

    def test_candles_to_dataframe(sample_candles):
        df = candles_to_dataframe(sample_candles)
        assert len(df) == 200
        assert list(df.columns) == ['open', 'high', 'low', 'close', 'volume']
        assert df.index.name == 'timestamp'

    def test_calculate_rsi(sample_candles):
        df = candles_to_dataframe(sample_candles)
        rsi = calculate_rsi(df)
        assert 0 <= rsi <= 100

    def test_calculate_smas(sample_candles):
        df = candles_to_dataframe(sample_candles)
        sma_50, sma_200 = calculate_smas(df)
        assert sma_50 > 0
        assert sma_200 > 0

    def test_calculate_volume_delta(sample_candles):
        df = candles_to_dataframe(sample_candles)
        delta = calculate_volume_delta(df)
        assert isinstance(delta, float)

    def test_bullish_signal():
        """Test bullish signal generation."""
        signal, strength, reasoning = calculate_technical_signal(
            rsi=25.0,  # Oversold
            sma_50=110.0,
            sma_200=100.0,  # Golden cross
            current_price=115.0,  # Above SMA200
            volume_delta=60.0  # High volume
        )
        assert signal == "BULLISH"
        assert strength > 50

    def test_bearish_signal():
        """Test bearish signal generation."""
        signal, strength, reasoning = calculate_technical_signal(
            rsi=75.0,  # Overbought
            sma_50=90.0,
            sma_200=100.0,  # Death cross
            current_price=85.0,  # Below SMA200
            volume_delta=-40.0  # Low volume
        )
        assert signal == "BEARISH"
        assert strength > 50
    ```

- [ ] **Create sentiment analysis tests**
  - [ ] Create `apps/bot/tests/test_sentiment.py`:
    ```python
    import pytest
    from services.sentiment_utils import (
        format_sentiment_data_for_prompt,
        parse_sentiment_response
    )

    def test_format_empty_data():
        result = format_sentiment_data_for_prompt([])
        assert result == "No sentiment data available."

    def test_format_sentiment_data():
        data = [
            {"text": "Bitcoin crashing!", "source": "twitter"},
            {"text": "HODL strong", "source": "reddit"}
        ]
        result = format_sentiment_data_for_prompt(data)
        assert "[twitter]" in result
        assert "[reddit]" in result
        assert "Bitcoin crashing!" in result

    def test_parse_valid_json():
        response = '{"fear_score": 25, "dominant_emotion": "FEAR", "summary": "Market panic", "key_themes": ["crash"]}'
        parsed = parse_sentiment_response(response)
        assert parsed["fear_score"] == 25
        assert parsed["dominant_emotion"] == "FEAR"

    def test_parse_json_with_markdown():
        response = '```json\n{"fear_score": 75, "dominant_emotion": "GREED", "summary": "FOMO", "key_themes": []}\n```'
        parsed = parse_sentiment_response(response)
        assert parsed["fear_score"] == 75

    def test_parse_invalid_json():
        response = "This is not JSON"
        parsed = parse_sentiment_response(response)
        assert parsed["fear_score"] == 50  # Default neutral
    ```

- [ ] **Run tests**
  - [ ] Execute: `cd apps/bot && pytest tests/ -v`
  - [ ] Verify all tests pass
  - [ ] Check test coverage: `pytest tests/ --cov=services --cov=nodes`

---

## Dev Notes

### Architecture Context

**Reference:** `docs/core/architecture.md` Section 6.1 (Backend Components)

The Technical and Sentiment agents are the "data" agents in the Council. They process raw information:

```
Technical Agent: Candles (OHLCV) -> pandas-ta -> Signal + Strength
Sentiment Agent: SentimentLogs -> Gemini Flash -> Fear Score + Summary
```

**ContrarianAI Philosophy:**
The system is designed for CONTRARIAN trading:
- **LOW fear score (0-20) = POTENTIAL BUY** (everyone panicking = accumulation zone)
- **HIGH fear score (80-100) = POTENTIAL SELL** (everyone euphoric = distribution zone)
- Technical confirmation required to validate sentiment signal

### Technical Specifications

**Technical Analysis Parameters:**
- RSI Period: 14 (industry standard)
- SMA Fast: 50 periods
- SMA Slow: 200 periods (Golden/Death Cross indicator)
- Volume Delta: 20-period average comparison

**Gemini Model Selection:**
- **Gemini 3 Flash**: Used for sentiment (fast, cost-effective for text)
- **Gemini 3 Pro**: Reserved for Vision Agent (better image understanding)

**Signal Scoring Logic:**
```
BULLISH conditions (each adds points):
- Price > SMA200: +30 points
- RSI < 30: +40 points (extreme oversold)
- RSI < 40: +20 points (oversold)
- Volume > 150% average: +15 points
- SMA50 > SMA200: +15 points (Golden Cross)

BEARISH conditions (each adds points):
- Price < SMA200: +30 points
- RSI > 70: +40 points (extreme overbought)
- RSI > 60: +20 points (overbought)
- Volume < 70% average: +15 points
- SMA50 < SMA200: +15 points (Death Cross)

Final signal = direction with more points
Strength = winner_points / total_points * 100
```

### Implementation Guidance

**pandas-ta Usage:**
```python
import pandas_ta as ta

# RSI
df.ta.rsi(length=14)

# SMA
df.ta.sma(length=50)
df.ta.sma(length=200)

# All indicators at once (alternative)
df.ta.strategy("momentum")  # Adds multiple columns
```

**Gemini Prompt Engineering Best Practices:**
1. Use low temperature (0.3) for consistent analysis
2. Request JSON output explicitly
3. Provide examples of expected output format
4. Handle markdown code blocks in response parsing
5. Set reasonable token limits to control costs

**Error Handling Patterns:**
- Always return a valid state, even on error
- Set neutral values (50) when analysis fails
- Log errors to `state["error"]` for Master Node awareness
- Never raise exceptions that would crash the graph

### Dependencies & Prerequisites

**Required Completions:**
- Story 2.1: LangGraph state machine with GraphState defined
- Story 1.2: Database schema with Candle and SentimentLog models
- Story 1.3: Kraken ingestor populating Candle table
- Story 1.4: Sentiment ingestor populating SentimentLog table

**Environment Requirements:**
- Python 3.11+ with virtual environment
- `GOOGLE_AI_API_KEY` environment variable set
- Database populated with test data (at least 200 candles)

### Downstream Dependencies

- **Story 2.3:** Vision Agent uses same GraphState pattern
- **Story 2.4:** Master Node consumes technical_analysis and sentiment_analysis

---

## Testing Strategy

### Unit Tests

- [ ] Test `candles_to_dataframe` with valid data
- [ ] Test `candles_to_dataframe` with empty data
- [ ] Test RSI calculation returns value 0-100
- [ ] Test SMA calculation with insufficient data
- [ ] Test volume delta calculation
- [ ] Test signal scoring with bullish conditions
- [ ] Test signal scoring with bearish conditions
- [ ] Test signal scoring with neutral conditions
- [ ] Test sentiment prompt formatting
- [ ] Test sentiment JSON parsing (valid)
- [ ] Test sentiment JSON parsing (invalid)

### Integration Tests

- [ ] Test technical_node with real candle data from DB
- [ ] Test sentiment_node with real sentiment logs from DB
- [ ] Test both nodes in sequence via graph invocation
- [ ] Test error handling when API key is invalid
- [ ] Test error handling when database is empty

### Manual Testing Scenarios

1. Run technical analysis on SOLUSD with 200+ candles
2. Verify RSI matches TradingView/external source
3. Run sentiment analysis on recent tweets/news
4. Verify fear score aligns with market perception
5. Test with extreme market conditions (crash, pump)

### Acceptance Criteria Validation

- [ ] AC1: Technical Agent outputs dict with `signal`, `strength`, RSI, SMAs, volume delta
- [ ] AC2: Sentiment Agent outputs dict with `fear_score` (0-100), `summary`
- [ ] AC3: Both agents correctly update GraphState
- [ ] AC4: Unit tests pass for all calculations and parsing

---

## Technical Considerations

### Security

- API keys stored in environment variables only
- Never log raw API responses (may contain sensitive data)
- Rate limit awareness for Gemini API calls

### Performance

- pandas-ta is optimized for vectorized operations
- Limit sentiment data to last 24 hours to reduce LLM tokens
- Cache DataFrame conversions if processing multiple assets

### Scalability

- Technical analysis is computationally light
- Gemini API has rate limits - batch requests if needed
- Consider caching sentiment analysis for short periods

### Edge Cases

- Handle < 14 candles (can't calculate RSI)
- Handle < 50 candles (can't calculate SMA50)
- Handle < 200 candles (can't calculate SMA200)
- Handle empty sentiment data (return neutral score)
- Handle Gemini API timeout
- Handle malformed JSON from Gemini

"""
Tests for Council endpoints in main.py.

Story 2.1: LangGraph State Machine Setup

Tests the API endpoints for Council session execution.
"""

from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    return TestClient(app)


class TestCouncilTestEndpoint:
    """Tests for GET /api/council/test endpoint."""

    def test_council_test_returns_success(self, client):
        """Test council test endpoint returns success status."""
        response = client.get("/api/council/test")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_council_test_graph_compiled(self, client):
        """Test council test confirms graph compiled."""
        response = client.get("/api/council/test")

        assert response.status_code == 200
        data = response.json()
        assert data["graph_compiled"] is True

    def test_council_test_returns_test_asset(self, client):
        """Test council test uses SOLUSD as test asset."""
        response = client.get("/api/council/test")

        assert response.status_code == 200
        data = response.json()
        assert data["test_asset"] == "SOLUSD"

    def test_council_test_decision_action(self, client):
        """Test council test returns HOLD action (stub)."""
        response = client.get("/api/council/test")

        assert response.status_code == 200
        data = response.json()
        assert data["decision_action"] == "HOLD"

    def test_council_test_decision_confidence(self, client):
        """Test council test returns valid confidence from multi-factor analysis."""
        response = client.get("/api/council/test")

        assert response.status_code == 200
        data = response.json()
        # Story 5.3: Confidence now calculated from multi-factor weights
        assert 0 <= data["decision_confidence"] <= 100

    def test_council_test_all_nodes_executed(self, client):
        """Test council test confirms all nodes executed."""
        response = client.get("/api/council/test")

        assert response.status_code == 200
        data = response.json()
        assert data["all_nodes_executed"] is True


class TestCouncilSessionEndpoint:
    """Tests for POST /api/council/session endpoint."""

    def test_session_basic_request(self, client):
        """Test basic session request returns 200."""
        response = client.post(
            "/api/council/session",
            json={"asset_symbol": "SOLUSD"}
        )

        assert response.status_code == 200

    def test_session_returns_asset_symbol(self, client):
        """Test session returns requested asset symbol."""
        response = client.post(
            "/api/council/session",
            json={"asset_symbol": "BTCUSD"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["asset_symbol"] == "BTCUSD"

    def test_session_returns_technical_analysis(self, client):
        """Test session returns technical analysis."""
        response = client.post(
            "/api/council/session",
            json={"asset_symbol": "SOLUSD"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["technical_analysis"] is not None
        assert "signal" in data["technical_analysis"]

    def test_session_returns_sentiment_analysis(self, client):
        """Test session returns sentiment analysis."""
        response = client.post(
            "/api/council/session",
            json={"asset_symbol": "SOLUSD"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["sentiment_analysis"] is not None
        assert "fear_score" in data["sentiment_analysis"]

    def test_session_returns_vision_analysis(self, client):
        """Test session returns vision analysis."""
        response = client.post(
            "/api/council/session",
            json={"asset_symbol": "SOLUSD"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["vision_analysis"] is not None
        assert "is_valid" in data["vision_analysis"]

    def test_session_returns_final_decision(self, client):
        """Test session returns final decision."""
        response = client.post(
            "/api/council/session",
            json={"asset_symbol": "SOLUSD"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["final_decision"] is not None
        assert "action" in data["final_decision"]
        assert "confidence" in data["final_decision"]

    def test_session_no_error_on_success(self, client):
        """Test session has no error on successful execution."""
        response = client.post(
            "/api/council/session",
            json={"asset_symbol": "SOLUSD"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is None

    def test_session_with_candles_data(self, client):
        """Test session accepts candles_data."""
        candles = [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "open": 100.0,
                "high": 105.0,
                "low": 98.0,
                "close": 103.0,
                "volume": 10000.0
            }
        ]
        response = client.post(
            "/api/council/session",
            json={
                "asset_symbol": "SOLUSD",
                "candles_data": candles
            }
        )

        assert response.status_code == 200

    def test_session_with_sentiment_data(self, client):
        """Test session accepts sentiment_data."""
        sentiment = [
            {"text": "SOL looking bullish!", "source": "twitter"}
        ]
        response = client.post(
            "/api/council/session",
            json={
                "asset_symbol": "SOLUSD",
                "sentiment_data": sentiment
            }
        )

        assert response.status_code == 200

    def test_session_with_all_data(self, client):
        """Test session accepts both candles and sentiment data."""
        response = client.post(
            "/api/council/session",
            json={
                "asset_symbol": "ETHUSD",
                "candles_data": [
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "open": 2000.0,
                        "high": 2100.0,
                        "low": 1950.0,
                        "close": 2050.0,
                        "volume": 5000.0
                    }
                ],
                "sentiment_data": [
                    {"text": "ETH to the moon!", "source": "telegram"}
                ]
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["asset_symbol"] == "ETHUSD"


class TestCouncilSessionValidation:
    """Tests for request validation on session endpoint."""

    def test_session_requires_asset_symbol(self, client):
        """Test session requires asset_symbol field."""
        response = client.post(
            "/api/council/session",
            json={}
        )

        # Should return 422 Unprocessable Entity
        assert response.status_code == 422

    def test_session_empty_symbol_accepted(self, client):
        """Test session accepts empty string symbol (but processes it)."""
        response = client.post(
            "/api/council/session",
            json={"asset_symbol": ""}
        )

        # Empty string is technically valid for the request
        assert response.status_code == 200

    def test_session_various_symbols(self, client):
        """Test session works with various asset symbols."""
        symbols = ["SOLUSD", "BTCUSD", "ETHUSD", "XRPUSD", "ADAUSD"]

        for symbol in symbols:
            response = client.post(
                "/api/council/session",
                json={"asset_symbol": symbol}
            )
            assert response.status_code == 200
            assert response.json()["asset_symbol"] == symbol


class TestCouncilSessionStubBehavior:
    """Tests verifying behavior with insufficient/no data in session responses."""

    def test_session_insufficient_data_technical_neutral(self, client):
        """Test session returns NEUTRAL technical signal when no data provided."""
        response = client.post(
            "/api/council/session",
            json={"asset_symbol": "SOLUSD"}
        )

        data = response.json()
        # With no candle data, technical analysis returns NEUTRAL with 0 strength
        assert data["technical_analysis"]["signal"] == "NEUTRAL"
        assert data["technical_analysis"]["strength"] == 0  # No confidence without data

    def test_session_stub_sentiment_neutral(self, client):
        """Test session stub returns neutral fear score."""
        response = client.post(
            "/api/council/session",
            json={"asset_symbol": "SOLUSD"}
        )

        data = response.json()
        assert data["sentiment_analysis"]["fear_score"] == 50

    def test_session_stub_vision_valid(self, client):
        """Test session vision returns is_valid=False with no data."""
        response = client.post(
            "/api/council/session",
            json={"asset_symbol": "SOLUSD"}
        )

        data = response.json()
        # Story 2.4: With no candles, vision returns is_valid=False
        assert data["vision_analysis"]["is_valid"] is False

    def test_session_stub_decision_hold(self, client):
        """Test session stub returns HOLD decision with multi-factor analysis."""
        response = client.post(
            "/api/council/session",
            json={"asset_symbol": "SOLUSD"}
        )

        data = response.json()
        assert data["final_decision"]["action"] == "HOLD"
        # Story 5.3: Confidence now calculated from multi-factor weights
        assert 0 <= data["final_decision"]["confidence"] <= 100

    def test_session_decision_has_timestamp(self, client):
        """Test session decision includes timestamp."""
        response = client.post(
            "/api/council/session",
            json={"asset_symbol": "SOLUSD"}
        )

        data = response.json()
        assert "timestamp" in data["final_decision"]
        # Timestamp should be ISO format string
        assert isinstance(data["final_decision"]["timestamp"], str)

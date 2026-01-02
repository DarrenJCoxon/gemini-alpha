"""
Santiment API client for on-chain data (Story 5.6).

This module provides async API access to Santiment GraphQL API for:
- Exchange inflow/outflow data
- Whale transaction tracking
- Funding rates (via alternative metrics)

API Documentation: https://academy.santiment.net/sanapi/
GraphQL Explorer: https://api.santiment.net/graphiql
"""

import httpx
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from decimal import Decimal
import logging

from config import get_config

logger = logging.getLogger(__name__)


# Mapping from trading symbols to Santiment slugs
SYMBOL_TO_SLUG = {
    "BTCUSD": "bitcoin",
    "ETHUSD": "ethereum",
    "SOLUSD": "solana",
    "AVAXUSD": "avalanche",
    "LINKUSD": "chainlink",
    "ADAUSD": "cardano",
    "DOTUSD": "polkadot",
    "MATICUSD": "matic-network",
    "ATOMUSD": "cosmos",
    "UNIUSD": "uniswap",
    "AAVEUSD": "aave",
    "XRPUSD": "ripple",
    "DOGEUSD": "dogecoin",
    "SHIBUSDUSD": "shiba-inu",
    "LTCUSD": "litecoin",
}


class SantimentClient:
    """
    Async client for Santiment GraphQL on-chain data API.

    Provides methods for fetching:
    - Exchange flows (inflow/outflow/netflow)
    - Whale transactions (large wallet movements)
    - Various on-chain metrics
    """

    BASE_URL = "https://api.santiment.net/graphql"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Santiment client.

        Args:
            api_key: Optional API key override. If not provided,
                     uses SANTIMENT_API_KEY from environment.
        """
        config = get_config()
        self.api_key = api_key or config.onchain.santiment_api_key

        if not self.api_key:
            raise ValueError("SANTIMENT_API_KEY not configured")

        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Apikey {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    def _get_slug(self, symbol: str) -> Optional[str]:
        """Map trading symbol to Santiment slug."""
        return SYMBOL_TO_SLUG.get(symbol.upper())

    async def _execute_query(self, query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a GraphQL query.

        Args:
            query: GraphQL query string
            variables: Optional query variables

        Returns:
            Query response data

        Raises:
            httpx.HTTPError: On network errors
            ValueError: On API errors
        """
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        response = await self.client.post(self.BASE_URL, json=payload)
        response.raise_for_status()

        data = response.json()

        if "errors" in data:
            error_msg = data["errors"][0].get("message", "Unknown GraphQL error")
            raise ValueError(f"Santiment API error: {error_msg}")

        return data.get("data", {})

    async def get_exchange_flow(
        self,
        symbol: str,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get exchange inflow/outflow data for an asset.

        Args:
            symbol: Trading symbol (e.g., "BTCUSD")
            days: Number of days of history

        Returns:
            List of flow records with datetime, inflow, outflow, netflow
        """
        slug = self._get_slug(symbol)
        if not slug:
            logger.warning(f"No Santiment slug mapping for {symbol}")
            return []

        from_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        query = """
        query($slug: String!, $from: DateTime!, $to: DateTime!) {
            inflow: getMetric(metric: "exchange_inflow_usd") {
                timeseriesData(slug: $slug, from: $from, to: $to, interval: "1d") {
                    datetime
                    value
                }
            }
            outflow: getMetric(metric: "exchange_outflow_usd") {
                timeseriesData(slug: $slug, from: $from, to: $to, interval: "1d") {
                    datetime
                    value
                }
            }
        }
        """

        try:
            data = await self._execute_query(query, {
                "slug": slug,
                "from": from_date,
                "to": to_date
            })

            inflow_data = data.get("inflow", {}).get("timeseriesData", [])
            outflow_data = data.get("outflow", {}).get("timeseriesData", [])

            # Merge inflow and outflow data
            flows = []
            outflow_map = {d["datetime"]: d["value"] for d in outflow_data}

            for inflow in inflow_data:
                dt = inflow["datetime"]
                inflow_val = float(inflow["value"] or 0)
                outflow_val = float(outflow_map.get(dt, 0) or 0)

                flows.append({
                    "datetime": dt,
                    "inflow_usd": inflow_val,
                    "outflow_usd": outflow_val,
                    "netflow_usd": inflow_val - outflow_val
                })

            logger.info(f"Fetched {len(flows)} exchange flow records for {symbol}")
            return flows

        except Exception as e:
            logger.error(f"Error fetching exchange flow for {symbol}: {e}")
            return []

    async def get_whale_transactions(
        self,
        symbol: str,
        days: int = 7,
        threshold: str = "100k"
    ) -> List[Dict[str, Any]]:
        """
        Get whale transaction count for an asset.

        Args:
            symbol: Trading symbol (e.g., "BTCUSD")
            days: Number of days of history
            threshold: "100k" or "1m" for $100K or $1M threshold

        Returns:
            List of whale activity records
        """
        slug = self._get_slug(symbol)
        if not slug:
            logger.warning(f"No Santiment slug mapping for {symbol}")
            return []

        metric = f"whale_transaction_count_{threshold}_usd_to_inf"
        from_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        query = """
        query($slug: String!, $from: DateTime!, $to: DateTime!, $metric: String!) {
            getMetric(metric: $metric) {
                timeseriesData(slug: $slug, from: $from, to: $to, interval: "1d") {
                    datetime
                    value
                }
            }
        }
        """

        try:
            data = await self._execute_query(query, {
                "slug": slug,
                "from": from_date,
                "to": to_date,
                "metric": metric
            })

            timeseries = data.get("getMetric", {}).get("timeseriesData", [])

            results = []
            for record in timeseries:
                results.append({
                    "datetime": record["datetime"],
                    "whale_tx_count": int(record["value"] or 0),
                    "threshold": threshold
                })

            logger.info(f"Fetched {len(results)} whale activity records for {symbol}")
            return results

        except Exception as e:
            logger.error(f"Error fetching whale transactions for {symbol}: {e}")
            return []

    async def get_funding_rate(
        self,
        symbol: str,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get perpetual futures funding rate for an asset.

        Note: Santiment uses 'funding_rate_buys_exchanges_aggregated' metric.

        Args:
            symbol: Trading symbol (e.g., "BTCUSD")
            days: Number of days of history

        Returns:
            List of funding rate records
        """
        slug = self._get_slug(symbol)
        if not slug:
            logger.warning(f"No Santiment slug mapping for {symbol}")
            return []

        from_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Try the aggregated funding rate metric
        query = """
        query($slug: String!, $from: DateTime!, $to: DateTime!) {
            getMetric(metric: "bitmex_perpetual_funding_rate") {
                timeseriesData(slug: $slug, from: $from, to: $to, interval: "8h") {
                    datetime
                    value
                }
            }
        }
        """

        try:
            data = await self._execute_query(query, {
                "slug": slug,
                "from": from_date,
                "to": to_date
            })

            timeseries = data.get("getMetric", {}).get("timeseriesData", [])

            results = []
            for record in timeseries:
                results.append({
                    "datetime": record["datetime"],
                    "funding_rate": float(record["value"] or 0),
                    "exchange": "bitmex"
                })

            logger.info(f"Fetched {len(results)} funding rate records for {symbol}")
            return results

        except Exception as e:
            logger.warning(f"Funding rate not available for {symbol}: {e}")
            return []

    async def get_stablecoin_exchange_balance(
        self,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get stablecoin reserves on exchanges (buying power indicator).

        Returns:
            List of stablecoin reserve records
        """
        from_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        query = """
        query($from: DateTime!, $to: DateTime!) {
            usdt: getMetric(metric: "exchange_balance") {
                timeseriesData(slug: "tether", from: $from, to: $to, interval: "1d") {
                    datetime
                    value
                }
            }
            usdc: getMetric(metric: "exchange_balance") {
                timeseriesData(slug: "usd-coin", from: $from, to: $to, interval: "1d") {
                    datetime
                    value
                }
            }
        }
        """

        try:
            data = await self._execute_query(query, {
                "from": from_date,
                "to": to_date
            })

            usdt_data = data.get("usdt", {}).get("timeseriesData", [])
            usdc_data = data.get("usdc", {}).get("timeseriesData", [])

            # Merge USDT and USDC data
            usdc_map = {d["datetime"]: d["value"] for d in usdc_data}

            results = []
            for usdt in usdt_data:
                dt = usdt["datetime"]
                usdt_val = float(usdt["value"] or 0)
                usdc_val = float(usdc_map.get(dt, 0) or 0)

                results.append({
                    "datetime": dt,
                    "usdt_balance": usdt_val,
                    "usdc_balance": usdc_val,
                    "total_stablecoin": usdt_val + usdc_val
                })

            logger.info(f"Fetched {len(results)} stablecoin reserve records")
            return results

        except Exception as e:
            logger.error(f"Error fetching stablecoin reserves: {e}")
            return []

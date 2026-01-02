"""
On-chain data ingestor for Story 5.6: On-Chain Data Integration.

This module ingests on-chain data from Santiment (primary) or CryptoQuant (fallback)
and stores it in the database. Called by the scheduler every 15 minutes.

Data Types:
- Exchange flows (inflow/outflow)
- Whale transactions
- Funding rates
- Stablecoin reserves
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, List, Optional, Union
import logging

from config import get_config
from database import get_session_maker
from models.onchain import (
    ExchangeFlow,
    WhaleActivity,
    FundingRate,
    StablecoinReserves
)

logger = logging.getLogger(__name__)
config = get_config()


class OnChainIngestor:
    """
    Ingests on-chain data from Santiment or CryptoQuant and stores in database.

    Handles:
    - Exchange flow ingestion
    - Whale activity aggregation
    - Funding rate collection
    - Stablecoin reserve tracking
    """

    def __init__(self):
        """Initialize the ingestor."""
        self.client = None
        self.provider: Optional[str] = None

    async def initialize(self) -> bool:
        """
        Initialize the on-chain client.

        Tries Santiment first (primary), then CryptoQuant (fallback).

        Returns:
            True if client was initialized, False if not configured
        """
        # Try Santiment first (primary provider)
        if config.onchain.santiment_api_key:
            try:
                from services.santiment_client import SantimentClient
                self.client = SantimentClient()
                self.provider = "santiment"
                logger.info("OnChainIngestor initialized with Santiment client")
                return True
            except Exception as e:
                logger.warning(f"Santiment initialization failed: {e}")

        # Try CryptoQuant as fallback
        if config.onchain.cryptoquant_api_key:
            try:
                from services.cryptoquant_client import CryptoQuantClient
                self.client = CryptoQuantClient()
                self.provider = "cryptoquant"
                logger.info("OnChainIngestor initialized with CryptoQuant client")
                return True
            except Exception as e:
                logger.warning(f"CryptoQuant initialization failed: {e}")

        logger.warning("No on-chain data provider configured (need SANTIMENT_API_KEY or CRYPTOQUANT_API_KEY)")
        return False

    async def ingest_exchange_flows(
        self,
        symbols: List[str]
    ) -> int:
        """
        Ingest exchange flow data for given symbols.

        Args:
            symbols: List of trading symbols (e.g., ["BTCUSD", "ETHUSD"])

        Returns:
            Number of records ingested
        """
        if not self.client:
            return 0

        count = 0
        session_maker = get_session_maker()

        async with session_maker() as session:
            for symbol in symbols:
                try:
                    if self.provider == "santiment":
                        flows = await self.client.get_exchange_flow(
                            symbol=symbol,
                            days=config.onchain.lookback_days
                        )
                        for flow in flows:
                            record = ExchangeFlow(
                                asset_symbol=symbol,
                                timestamp=datetime.fromisoformat(flow["datetime"].replace("Z", "+00:00")),
                                inflow_usd=Decimal(str(flow["inflow_usd"])),
                                outflow_usd=Decimal(str(flow["outflow_usd"])),
                                net_flow_usd=Decimal(str(flow["netflow_usd"])),
                                source="santiment"
                            )
                            session.add(record)
                            count += 1
                    else:
                        # CryptoQuant format
                        asset = self._map_symbol_cryptoquant(symbol)
                        if not asset:
                            continue
                        flows = await self.client.get_exchange_flow(
                            asset=asset,
                            window="day",
                            limit=config.onchain.lookback_days
                        )
                        for flow in flows:
                            record = ExchangeFlow(
                                asset_symbol=symbol,
                                timestamp=flow["timestamp"],
                                inflow_usd=flow["inflow"],
                                outflow_usd=flow["outflow"],
                                net_flow_usd=flow["netflow"],
                                source="cryptoquant"
                            )
                            session.add(record)
                            count += 1

                except Exception as e:
                    logger.error(f"Error ingesting exchange flows for {symbol}: {e}")
                    continue

            await session.commit()

        logger.info(f"Ingested {count} exchange flow records")
        return count

    async def ingest_whale_activity(
        self,
        symbols: List[str]
    ) -> int:
        """
        Ingest whale transaction data.

        Args:
            symbols: List of trading symbols

        Returns:
            Number of records ingested
        """
        if not self.client:
            return 0

        count = 0
        session_maker = get_session_maker()

        async with session_maker() as session:
            for symbol in symbols:
                try:
                    if self.provider == "santiment":
                        # Santiment returns daily whale tx counts
                        transactions = await self.client.get_whale_transactions(
                            symbol=symbol,
                            days=config.onchain.lookback_days,
                            threshold="100k"
                        )
                        for tx in transactions:
                            record = WhaleActivity(
                                asset_symbol=symbol,
                                timestamp=datetime.fromisoformat(tx["datetime"].replace("Z", "+00:00")),
                                large_tx_count=tx["whale_tx_count"],
                                total_whale_volume_usd=Decimal("0"),  # Not provided by Santiment
                                source="santiment"
                            )
                            session.add(record)
                            count += 1
                    else:
                        # CryptoQuant format with aggregation
                        asset = self._map_symbol_cryptoquant(symbol)
                        if not asset:
                            continue
                        transactions = await self.client.get_whale_transactions(
                            asset=asset,
                            min_value_usd=1000000,
                            limit=100
                        )
                        # Aggregate by hour
                        hourly_aggregates: Dict[datetime, Dict[str, Any]] = {}
                        for tx in transactions:
                            hour = tx["timestamp"].replace(minute=0, second=0, microsecond=0)
                            if hour not in hourly_aggregates:
                                hourly_aggregates[hour] = {
                                    "count": 0,
                                    "total_volume": Decimal("0"),
                                    "buy_volume": Decimal("0"),
                                    "sell_volume": Decimal("0")
                                }
                            hourly_aggregates[hour]["count"] += 1
                            hourly_aggregates[hour]["total_volume"] += tx["value_usd"]
                            if tx["to_type"] == "exchange":
                                hourly_aggregates[hour]["sell_volume"] += tx["value_usd"]
                            elif tx["from_type"] == "exchange":
                                hourly_aggregates[hour]["buy_volume"] += tx["value_usd"]

                        for hour, agg in hourly_aggregates.items():
                            record = WhaleActivity(
                                asset_symbol=symbol,
                                timestamp=hour,
                                large_tx_count=agg["count"],
                                total_whale_volume_usd=agg["total_volume"],
                                whale_buy_volume=agg["buy_volume"],
                                whale_sell_volume=agg["sell_volume"],
                                source="cryptoquant"
                            )
                            session.add(record)
                            count += 1

                except Exception as e:
                    logger.error(f"Error ingesting whale activity for {symbol}: {e}")
                    continue

            await session.commit()

        logger.info(f"Ingested {count} whale activity records")
        return count

    async def ingest_funding_rates(
        self,
        symbols: List[str]
    ) -> int:
        """
        Ingest funding rate data.

        Args:
            symbols: List of trading symbols

        Returns:
            Number of records ingested
        """
        if not self.client:
            return 0

        count = 0
        session_maker = get_session_maker()

        async with session_maker() as session:
            for symbol in symbols:
                try:
                    if self.provider == "santiment":
                        rates = await self.client.get_funding_rate(
                            symbol=symbol,
                            days=config.onchain.lookback_days
                        )
                        for rate in rates:
                            record = FundingRate(
                                asset_symbol=symbol,
                                timestamp=datetime.fromisoformat(rate["datetime"].replace("Z", "+00:00")),
                                exchange=rate.get("exchange", "aggregated"),
                                funding_rate=Decimal(str(rate["funding_rate"])),
                                source="santiment"
                            )
                            session.add(record)
                            count += 1
                    else:
                        # CryptoQuant format
                        asset = self._map_symbol_cryptoquant(symbol)
                        if not asset:
                            continue
                        rates = await self.client.get_funding_rates(
                            asset=asset,
                            exchange="all",
                            limit=24
                        )
                        for rate in rates:
                            record = FundingRate(
                                asset_symbol=symbol,
                                timestamp=rate["timestamp"],
                                exchange=rate["exchange"],
                                funding_rate=rate["funding_rate"],
                                open_interest_usd=rate["open_interest"],
                                source="cryptoquant"
                            )
                            session.add(record)
                            count += 1

                except Exception as e:
                    logger.error(f"Error ingesting funding rates for {symbol}: {e}")
                    continue

            await session.commit()

        logger.info(f"Ingested {count} funding rate records")
        return count

    async def ingest_stablecoin_reserves(self) -> int:
        """
        Ingest stablecoin reserve data.

        Returns:
            Number of records ingested
        """
        if not self.client:
            return 0

        try:
            count = 0
            session_maker = get_session_maker()

            async with session_maker() as session:
                if self.provider == "santiment":
                    reserves = await self.client.get_stablecoin_exchange_balance(
                        days=config.onchain.lookback_days
                    )
                    for i, res in enumerate(reserves):
                        # Calculate change percentages
                        change_24h_pct = None
                        change_7d_pct = None

                        if i + 1 < len(reserves):
                            prev = reserves[i + 1]
                            if prev["total_stablecoin"] > 0:
                                change_24h_pct = Decimal(str(
                                    (res["total_stablecoin"] - prev["total_stablecoin"])
                                    / prev["total_stablecoin"] * 100
                                ))

                        if i + 7 < len(reserves):
                            prev_7d = reserves[i + 7]
                            if prev_7d["total_stablecoin"] > 0:
                                change_7d_pct = Decimal(str(
                                    (res["total_stablecoin"] - prev_7d["total_stablecoin"])
                                    / prev_7d["total_stablecoin"] * 100
                                ))

                        record = StablecoinReserves(
                            timestamp=datetime.fromisoformat(res["datetime"].replace("Z", "+00:00")),
                            total_reserves_usd=Decimal(str(res["total_stablecoin"])),
                            usdt_reserves=Decimal(str(res["usdt_balance"])),
                            usdc_reserves=Decimal(str(res["usdc_balance"])),
                            change_24h_pct=change_24h_pct,
                            change_7d_pct=change_7d_pct,
                            source="santiment"
                        )
                        session.add(record)
                        count += 1
                else:
                    # CryptoQuant format
                    reserves = await self.client.get_stablecoin_reserves(
                        limit=config.onchain.lookback_days
                    )
                    for i, res in enumerate(reserves):
                        change_24h_pct = None
                        change_7d_pct = None

                        if i + 1 < len(reserves):
                            prev = reserves[i + 1]
                            if prev["total_reserve"] > 0:
                                change_24h_pct = Decimal(str(
                                    (float(res["total_reserve"]) - float(prev["total_reserve"]))
                                    / float(prev["total_reserve"]) * 100
                                ))

                        if i + 7 < len(reserves):
                            prev_7d = reserves[i + 7]
                            if prev_7d["total_reserve"] > 0:
                                change_7d_pct = Decimal(str(
                                    (float(res["total_reserve"]) - float(prev_7d["total_reserve"]))
                                    / float(prev_7d["total_reserve"]) * 100
                                ))

                        record = StablecoinReserves(
                            timestamp=res["timestamp"],
                            total_reserves_usd=res["total_reserve"],
                            usdt_reserves=res["usdt_reserve"],
                            usdc_reserves=res["usdc_reserve"],
                            change_24h_pct=change_24h_pct,
                            change_7d_pct=change_7d_pct,
                            source="cryptoquant"
                        )
                        session.add(record)
                        count += 1

                await session.commit()

            logger.info(f"Ingested {count} stablecoin reserve records")
            return count

        except Exception as e:
            logger.error(f"Error ingesting stablecoin reserves: {e}")
            return 0

    async def run_full_ingestion(
        self,
        symbols: List[str]
    ) -> Dict[str, int]:
        """
        Run full on-chain data ingestion.

        Args:
            symbols: List of trading symbols to ingest

        Returns:
            Dict with ingestion statistics
        """
        results = {
            "exchange_flows": await self.ingest_exchange_flows(symbols),
            "whale_activity": await self.ingest_whale_activity(symbols),
            "funding_rates": await self.ingest_funding_rates(symbols),
            "stablecoin_reserves": await self.ingest_stablecoin_reserves()
        }

        total = sum(results.values())
        logger.info(f"On-chain ingestion complete ({self.provider}): {total} total records")
        logger.debug(f"On-chain ingestion breakdown: {results}")

        return results

    def _map_symbol_cryptoquant(self, symbol: str) -> Optional[str]:
        """
        Map trading symbol to CryptoQuant asset format.

        Args:
            symbol: Trading symbol (e.g., "BTCUSD")

        Returns:
            CryptoQuant asset format (e.g., "btc") or None if not supported
        """
        mapping = {
            "BTCUSD": "btc",
            "ETHUSD": "eth",
            "BTC": "btc",
            "ETH": "eth",
            "XBTUSD": "btc",
        }

        if symbol in mapping:
            return mapping[symbol]

        for key, value in mapping.items():
            if symbol.startswith(key[:3]):
                return value

        logger.debug(f"No CryptoQuant mapping for symbol: {symbol}")
        return None

    async def close(self) -> None:
        """Cleanup resources."""
        if self.client:
            await self.client.close()
            self.client = None
            self.provider = None


# Global ingestor instance (lazy initialization)
_ingestor: Optional[OnChainIngestor] = None


async def get_onchain_ingestor() -> OnChainIngestor:
    """
    Get or create the global OnChainIngestor instance.

    Returns:
        Initialized OnChainIngestor instance
    """
    global _ingestor
    if _ingestor is None:
        _ingestor = OnChainIngestor()
        await _ingestor.initialize()
    return _ingestor


async def close_onchain_ingestor() -> None:
    """Close the global OnChainIngestor if it exists."""
    global _ingestor
    if _ingestor is not None:
        await _ingestor.close()
        _ingestor = None

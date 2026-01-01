'use client';

import { useState, useEffect, useCallback } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { RefreshCw, AlertTriangle, Wifi } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Trade, TradeWithMetrics } from '@/types/trade';
import { fetchOpenTrades } from '@/app/dashboard/trades/actions';
import { TradeCard } from './trade-card';
import { useTradeListener } from '@/hooks/use-trade-listener';
import { useAssetPriceListener } from '@/hooks/use-asset-price-listener';

interface ActiveTradesProps {
  initialTrades?: TradeWithMetrics[];
  className?: string;
}

/**
 * Container component for displaying active trading positions.
 * Shows P&L summary and at-risk trade warnings.
 * Integrates Supabase Realtime for live updates.
 */
export function ActiveTrades({ initialTrades = [], className }: ActiveTradesProps) {
  const [trades, setTrades] = useState<TradeWithMetrics[]>(initialTrades);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Handle new trade inserted
  const handleTradeInsert = useCallback((trade: Trade) => {
    if (trade.status !== 'OPEN') return;

    // Convert to TradeWithMetrics
    const tradeWithMetrics: TradeWithMetrics = {
      ...trade,
      currentPrice: trade.entryPrice, // Will be updated by price listener
      unrealizedPnl: 0,
      unrealizedPnlPercent: 0,
      distanceToStopPercent:
        ((trade.entryPrice - trade.stopLossPrice) / trade.entryPrice) * 100,
      distanceToTakeProfitPercent: trade.takeProfitPrice
        ? ((trade.takeProfitPrice - trade.entryPrice) / trade.entryPrice) * 100
        : null,
    };

    setTrades((prev) => {
      if (prev.some((t) => t.id === trade.id)) return prev;
      return [tradeWithMetrics, ...prev];
    });
  }, []);

  // Handle trade updated (status change, stop loss moved, etc.)
  const handleTradeUpdate = useCallback((trade: Trade) => {
    setTrades((prev) => {
      // If no longer open, remove from list
      if (trade.status !== 'OPEN') {
        return prev.filter((t) => t.id !== trade.id);
      }

      // Update existing trade
      return prev.map((t) => {
        if (t.id !== trade.id) return t;

        return {
          ...t,
          ...trade,
          // Recalculate metrics
          unrealizedPnl: (t.currentPrice - trade.entryPrice) * trade.size,
          unrealizedPnlPercent:
            ((t.currentPrice - trade.entryPrice) / trade.entryPrice) * 100,
          distanceToStopPercent:
            ((t.currentPrice - trade.stopLossPrice) / t.currentPrice) * 100,
          distanceToTakeProfitPercent: trade.takeProfitPrice
            ? ((trade.takeProfitPrice - t.currentPrice) / t.currentPrice) * 100
            : null,
        };
      });
    });
  }, []);

  // Handle trade deleted
  const handleTradeDelete = useCallback((tradeId: string) => {
    setTrades((prev) => prev.filter((t) => t.id !== tradeId));
  }, []);

  // Enable trade listener
  useTradeListener({
    onTradeInsert: handleTradeInsert,
    onTradeUpdate: handleTradeUpdate,
    onTradeDelete: handleTradeDelete,
    showToasts: true,
  });

  // Handle price updates for real-time P&L
  const handlePriceUpdate = useCallback(
    ({ assetId, lastPrice }: { assetId: string; lastPrice: number }) => {
      setTrades((prev) =>
        prev.map((trade) => {
          if (trade.assetId !== assetId) return trade;

          const unrealizedPnl = (lastPrice - trade.entryPrice) * trade.size;
          const unrealizedPnlPercent =
            ((lastPrice - trade.entryPrice) / trade.entryPrice) * 100;
          const distanceToStopPercent =
            ((lastPrice - trade.stopLossPrice) / lastPrice) * 100;
          const distanceToTakeProfitPercent = trade.takeProfitPrice
            ? ((trade.takeProfitPrice - lastPrice) / lastPrice) * 100
            : null;

          return {
            ...trade,
            currentPrice: lastPrice,
            unrealizedPnl,
            unrealizedPnlPercent,
            distanceToStopPercent,
            distanceToTakeProfitPercent,
          };
        })
      );
    },
    []
  );

  // Get asset IDs from current trades for filtered price updates
  const tradeAssetIds = trades.map((t) => t.assetId);

  // Enable price listener for active trade assets
  useAssetPriceListener({
    onPriceUpdate: handlePriceUpdate,
    assetIds: tradeAssetIds.length > 0 ? tradeAssetIds : undefined,
  });

  const loadTrades = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await fetchOpenTrades();
      setTrades(data);
    } catch (err) {
      setError('Failed to load trades');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (initialTrades.length === 0) {
      loadTrades();
    }
  }, [initialTrades.length, loadTrades]);

  // Calculate total P&L
  const totalPnl = trades.reduce((sum, t) => sum + t.unrealizedPnl, 0);
  const totalPnlPercent =
    trades.length > 0
      ? trades.reduce((sum, t) => sum + t.unrealizedPnlPercent, 0) / trades.length
      : 0;

  // Find trades close to stop loss
  const atRiskTrades = trades.filter((t) => t.distanceToStopPercent < 2);

  return (
    <div className={cn('flex flex-col h-full', className)} data-testid="active-trades">
      {/* Header with Realtime Status */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold text-zinc-100">Active Positions</h2>
            <Wifi
              className="h-4 w-4 text-emerald-500 animate-pulse"
              aria-label="Realtime connected"
              data-testid="realtime-indicator"
            />
          </div>
          <p className="text-sm text-zinc-400">
            {trades.length} open trade{trades.length !== 1 ? 's' : ''}
          </p>
        </div>
        <Button
          size="sm"
          variant="ghost"
          onClick={loadTrades}
          disabled={isLoading}
          className="h-8"
          aria-label="Refresh trades"
          data-testid="refresh-button"
        >
          <RefreshCw className={cn('h-4 w-4', isLoading && 'animate-spin')} />
        </Button>
      </div>

      {/* Summary Stats */}
      {trades.length > 0 && (
        <div
          className="grid grid-cols-2 gap-3 mb-4 p-3 bg-zinc-950 rounded-lg"
          data-testid="summary-stats"
        >
          <div>
            <p className="text-xs text-zinc-500">Total Unrealized P&L</p>
            <p
              className={cn(
                'text-lg font-bold font-mono transition-colors',
                totalPnl >= 0 ? 'text-emerald-500' : 'text-rose-500'
              )}
              data-testid="total-pnl"
            >
              {totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)}
            </p>
          </div>
          <div>
            <p className="text-xs text-zinc-500">Avg ROI</p>
            <p
              className={cn(
                'text-lg font-bold font-mono transition-colors',
                totalPnlPercent >= 0 ? 'text-emerald-500' : 'text-rose-500'
              )}
              data-testid="avg-roi"
            >
              {totalPnlPercent >= 0 ? '+' : ''}
              {totalPnlPercent.toFixed(2)}%
            </p>
          </div>
        </div>
      )}

      {/* At Risk Warning */}
      {atRiskTrades.length > 0 && (
        <div
          className="flex items-center gap-2 p-2 bg-amber-500/10 border border-amber-500/50 rounded-md mb-4"
          role="alert"
          data-testid="at-risk-warning"
        >
          <AlertTriangle className="h-4 w-4 text-amber-500" aria-hidden="true" />
          <span className="text-xs text-amber-500">
            {atRiskTrades.length} trade{atRiskTrades.length !== 1 ? 's' : ''} within 2%
            of stop loss
          </span>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div
          className="bg-rose-500/10 border border-rose-500/50 text-rose-500 p-3 rounded-md mb-4"
          role="alert"
          data-testid="error-message"
        >
          {error}
        </div>
      )}

      {/* Trades list */}
      <ScrollArea className="flex-1">
        <div className="space-y-3 pr-4">
          {isLoading && trades.length === 0 && (
            <>
              <TradeCardSkeleton />
              <TradeCardSkeleton />
            </>
          )}

          {trades.map((trade) => (
            <TradeCard key={trade.id} trade={trade} />
          ))}

          {/* Empty state */}
          {!isLoading && trades.length === 0 && (
            <div className="text-center py-8 text-zinc-500" data-testid="empty-state">
              <p>No active positions</p>
              <p className="text-sm mt-2">
                Trades will appear here when the bot opens positions
              </p>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

function TradeCardSkeleton() {
  return (
    <div
      className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 space-y-3"
      data-testid="trade-card-skeleton"
    >
      <div className="flex items-center justify-between">
        <Skeleton className="h-5 w-24 bg-zinc-800" />
        <Skeleton className="h-8 w-20 bg-zinc-800" />
      </div>
      <Skeleton className="h-12 w-full bg-zinc-800" />
      <Skeleton className="h-6 w-full bg-zinc-800" />
    </div>
  );
}

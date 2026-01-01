'use client';

import { useState, useEffect, useCallback } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { RefreshCw, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { TradeWithMetrics } from '@/types/trade';
import { fetchOpenTrades } from '@/app/dashboard/trades/actions';
import { TradeCard } from './trade-card';

interface ActiveTradesProps {
  initialTrades?: TradeWithMetrics[];
  className?: string;
}

/**
 * Container component for displaying active trading positions.
 * Shows P&L summary and at-risk trade warnings.
 */
export function ActiveTrades({ initialTrades = [], className }: ActiveTradesProps) {
  const [trades, setTrades] = useState<TradeWithMetrics[]>(initialTrades);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
  const totalPnlPercent = trades.length > 0
    ? trades.reduce((sum, t) => sum + t.unrealizedPnlPercent, 0) / trades.length
    : 0;

  // Find trades close to stop loss
  const atRiskTrades = trades.filter((t) => t.distanceToStopPercent < 2);

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-zinc-100">Active Positions</h2>
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
        >
          <RefreshCw className={cn('h-4 w-4', isLoading && 'animate-spin')} />
        </Button>
      </div>

      {/* Summary Stats */}
      {trades.length > 0 && (
        <div className="grid grid-cols-2 gap-3 mb-4 p-3 bg-zinc-950 rounded-lg">
          <div>
            <p className="text-xs text-zinc-500">Total Unrealized P&L</p>
            <p
              className={cn(
                'text-lg font-bold font-mono',
                totalPnl >= 0 ? 'text-emerald-500' : 'text-rose-500'
              )}
            >
              {totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)}
            </p>
          </div>
          <div>
            <p className="text-xs text-zinc-500">Avg ROI</p>
            <p
              className={cn(
                'text-lg font-bold font-mono',
                totalPnlPercent >= 0 ? 'text-emerald-500' : 'text-rose-500'
              )}
            >
              {totalPnlPercent >= 0 ? '+' : ''}{totalPnlPercent.toFixed(2)}%
            </p>
          </div>
        </div>
      )}

      {/* At Risk Warning */}
      {atRiskTrades.length > 0 && (
        <div
          className="flex items-center gap-2 p-2 bg-amber-500/10 border border-amber-500/50 rounded-md mb-4"
          role="alert"
        >
          <AlertTriangle className="h-4 w-4 text-amber-500" aria-hidden="true" />
          <span className="text-xs text-amber-500">
            {atRiskTrades.length} trade{atRiskTrades.length !== 1 ? 's' : ''} within 2% of stop loss
          </span>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div
          className="bg-rose-500/10 border border-rose-500/50 text-rose-500 p-3 rounded-md mb-4"
          role="alert"
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
            <div className="text-center py-8 text-zinc-500">
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
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <Skeleton className="h-5 w-24 bg-zinc-800" />
        <Skeleton className="h-8 w-20 bg-zinc-800" />
      </div>
      <Skeleton className="h-12 w-full bg-zinc-800" />
      <Skeleton className="h-6 w-full bg-zinc-800" />
    </div>
  );
}

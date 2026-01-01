'use client';

import { formatDistanceToNow } from 'date-fns';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { TradeWithMetrics } from '@/types/trade';
import { StopLossIndicator } from './stop-loss-indicator';
import { Sparkline } from './sparkline';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface TradeCardProps {
  trade: TradeWithMetrics;
  priceHistory?: number[]; // Optional sparkline data
  className?: string;
}

/**
 * Trade card displaying position details, P&L, and stop loss progress.
 */
export function TradeCard({ trade, priceHistory, className }: TradeCardProps) {
  const isProfit = trade.unrealizedPnlPercent >= 0;

  return (
    <Card
      className={cn(
        'bg-zinc-900 border-zinc-800 transition-all',
        className
      )}
    >
      <CardHeader className="p-4 pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-zinc-100 font-mono">
              {trade.asset?.symbol || trade.assetId}
            </span>
            <Badge
              variant="outline"
              className={cn(
                'text-xs',
                trade.direction === 'LONG'
                  ? 'border-emerald-500/50 text-emerald-500'
                  : 'border-rose-500/50 text-rose-500'
              )}
            >
              {trade.direction}
            </Badge>
          </div>

          {/* Sparkline */}
          {priceHistory && priceHistory.length > 0 && (
            <Sparkline data={priceHistory} isPositive={isProfit} />
          )}
        </div>
      </CardHeader>

      <CardContent className="p-4 pt-0 space-y-4">
        {/* P&L Display */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-zinc-500">Unrealized P&L</p>
            <div className="flex items-center gap-2">
              {isProfit ? (
                <TrendingUp className="h-5 w-5 text-emerald-500" aria-label="Profit" />
              ) : (
                <TrendingDown className="h-5 w-5 text-rose-500" aria-label="Loss" />
              )}
              <span
                className={cn(
                  'text-2xl font-bold font-mono',
                  isProfit ? 'text-emerald-500' : 'text-rose-500'
                )}
              >
                {isProfit ? '+' : ''}{trade.unrealizedPnlPercent.toFixed(2)}%
              </span>
            </div>
            <p
              className={cn(
                'text-sm font-mono',
                isProfit ? 'text-emerald-500' : 'text-rose-500'
              )}
            >
              {isProfit ? '+' : ''}${trade.unrealizedPnl.toFixed(2)}
            </p>
          </div>

          {/* Price Info */}
          <div className="text-right">
            <div className="text-xs text-zinc-500">
              Entry: <span className="font-mono text-zinc-400">${trade.entryPrice.toFixed(2)}</span>
            </div>
            <div className="text-xs text-zinc-500">
              Current: <span className="font-mono text-zinc-100">${trade.currentPrice.toFixed(2)}</span>
            </div>
            <div className="text-xs text-zinc-500">
              Size: <span className="font-mono text-zinc-400">{trade.size.toFixed(4)}</span>
            </div>
          </div>
        </div>

        {/* Stop Loss Indicator */}
        <StopLossIndicator
          entryPrice={trade.entryPrice}
          currentPrice={trade.currentPrice}
          stopLossPrice={trade.stopLossPrice}
          takeProfitPrice={trade.takeProfitPrice}
          direction={trade.direction}
        />

        {/* Footer */}
        <div className="flex items-center justify-between text-xs text-zinc-500">
          <span>
            Opened {formatDistanceToNow(trade.entryTime, { addSuffix: true })}
          </span>
          <span
            className={cn(
              'font-mono',
              trade.distanceToStopPercent < 2 ? 'text-rose-500' : 'text-zinc-400'
            )}
          >
            {trade.distanceToStopPercent.toFixed(1)}% to stop
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

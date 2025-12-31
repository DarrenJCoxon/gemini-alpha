# Story 4.3: Active Positions & Market Scanner

**Status:** Draft
**Epic:** 4 - Mission Control Dashboard (Next.js)
**Priority:** High

---

## Story

**As a** User,
**I want** to see my open trades and a heatmap of potential opportunities,
**so that** I know my current P&L and what the bot is watching.

---

## Acceptance Criteria

1. **Active Trades Widget:** Displays `Trade` records where `status = OPEN`.
    - Shows Entry Price, Current Price (mocked/fetched), and live P&L %.
    - Visualizes the distance to the "Stop Loss."
2. **Market Scanner:** Table showing the Top 30 Assets.
    - Columns: Symbol, Last Price, Sentiment Score, Tech Signal.
    - Sortable by "Fear Score" (Sentiment).

---

## Tasks / Subtasks

### Phase 1: TypeScript Types & Data Models

- [ ] **Define Trade Types**
  - [ ] Create `types/trade.ts`:
    ```typescript
    export type TradeStatus = 'OPEN' | 'CLOSED' | 'STOPPED_OUT' | 'TAKE_PROFIT';
    export type TradeDirection = 'LONG' | 'SHORT';

    export interface Trade {
      id: string;
      assetId: string;
      status: TradeStatus;
      direction: TradeDirection;
      entryPrice: number;
      size: number;
      entryTime: Date;
      stopLossPrice: number;
      takeProfitPrice: number | null;
      exitPrice: number | null;
      exitTime: Date | null;
      pnl: number | null;  // Realized P&L (after close)
      createdAt: Date;
      updatedAt: Date;
      // Joined data
      asset?: {
        symbol: string;
        lastPrice: number;
      };
    }

    export interface TradeWithMetrics extends Trade {
      currentPrice: number;
      unrealizedPnl: number;      // Current price - Entry price
      unrealizedPnlPercent: number;
      distanceToStopPercent: number;
      distanceToTakeProfitPercent: number | null;
    }
    ```

- [ ] **Define Scanner Types**
  - [ ] Create `types/scanner.ts`:
    ```typescript
    export interface ScannerAsset {
      id: string;
      symbol: string;
      lastPrice: number;
      priceChange15m: number;      // Percentage change
      sentimentScore: number | null;  // From latest council session
      technicalSignal: string | null; // "BULLISH" | "BEARISH" | "NEUTRAL"
      technicalStrength: number | null;
      lastSessionTime: Date | null;
    }

    export type SortField = 'symbol' | 'lastPrice' | 'sentimentScore' | 'technicalSignal';
    export type SortDirection = 'asc' | 'desc';

    export interface ScannerFilters {
      sortBy: SortField;
      sortDirection: SortDirection;
      limit?: number;
    }
    ```

### Phase 2: Data Fetching Layer

- [ ] **Create Trade Fetching Actions**
  - [ ] Create `app/dashboard/trades/actions.ts`:
    ```typescript
    'use server';

    import { createClient } from '@/lib/supabase/server';
    import { Trade, TradeWithMetrics } from '@/types/trade';

    export async function fetchOpenTrades(): Promise<TradeWithMetrics[]> {
      const supabase = await createClient();

      const { data, error } = await supabase
        .from('trades')
        .select(`
          *,
          asset:assets (
            symbol,
            lastPrice:last_price
          )
        `)
        .eq('status', 'OPEN')
        .order('entry_time', { ascending: false });

      if (error) {
        console.error('Error fetching open trades:', error);
        throw new Error('Failed to fetch open trades');
      }

      // Transform and calculate metrics
      return data.map((t: any) => {
        const currentPrice = t.asset?.lastPrice || t.entry_price;
        const unrealizedPnl = (currentPrice - t.entry_price) * t.size;
        const unrealizedPnlPercent = ((currentPrice - t.entry_price) / t.entry_price) * 100;
        const distanceToStopPercent = ((currentPrice - t.stop_loss_price) / currentPrice) * 100;
        const distanceToTakeProfitPercent = t.take_profit_price
          ? ((t.take_profit_price - currentPrice) / currentPrice) * 100
          : null;

        return {
          id: t.id,
          assetId: t.asset_id,
          status: t.status,
          direction: t.direction || 'LONG',
          entryPrice: parseFloat(t.entry_price),
          size: parseFloat(t.size),
          entryTime: new Date(t.entry_time),
          stopLossPrice: parseFloat(t.stop_loss_price),
          takeProfitPrice: t.take_profit_price ? parseFloat(t.take_profit_price) : null,
          exitPrice: t.exit_price ? parseFloat(t.exit_price) : null,
          exitTime: t.exit_time ? new Date(t.exit_time) : null,
          pnl: t.pnl ? parseFloat(t.pnl) : null,
          createdAt: new Date(t.created_at),
          updatedAt: new Date(t.updated_at),
          asset: t.asset ? {
            symbol: t.asset.symbol,
            lastPrice: parseFloat(t.asset.lastPrice),
          } : undefined,
          currentPrice,
          unrealizedPnl,
          unrealizedPnlPercent,
          distanceToStopPercent,
          distanceToTakeProfitPercent,
        };
      });
    }

    export async function fetchTradeHistory(limit = 20): Promise<Trade[]> {
      const supabase = await createClient();

      const { data, error } = await supabase
        .from('trades')
        .select(`
          *,
          asset:assets (
            symbol,
            lastPrice:last_price
          )
        `)
        .in('status', ['CLOSED', 'STOPPED_OUT', 'TAKE_PROFIT'])
        .order('exit_time', { ascending: false })
        .limit(limit);

      if (error) {
        console.error('Error fetching trade history:', error);
        throw new Error('Failed to fetch trade history');
      }

      return data.map((t: any) => ({
        id: t.id,
        assetId: t.asset_id,
        status: t.status,
        direction: t.direction || 'LONG',
        entryPrice: parseFloat(t.entry_price),
        size: parseFloat(t.size),
        entryTime: new Date(t.entry_time),
        stopLossPrice: parseFloat(t.stop_loss_price),
        takeProfitPrice: t.take_profit_price ? parseFloat(t.take_profit_price) : null,
        exitPrice: t.exit_price ? parseFloat(t.exit_price) : null,
        exitTime: t.exit_time ? new Date(t.exit_time) : null,
        pnl: t.pnl ? parseFloat(t.pnl) : null,
        createdAt: new Date(t.created_at),
        updatedAt: new Date(t.updated_at),
        asset: t.asset ? {
          symbol: t.asset.symbol,
          lastPrice: parseFloat(t.asset.lastPrice),
        } : undefined,
      }));
    }
    ```

- [ ] **Create Scanner Fetching Actions**
  - [ ] Create `app/dashboard/scanner/actions.ts`:
    ```typescript
    'use server';

    import { createClient } from '@/lib/supabase/server';
    import { ScannerAsset, ScannerFilters } from '@/types/scanner';

    export async function fetchScannerAssets(
      filters: ScannerFilters = { sortBy: 'sentimentScore', sortDirection: 'asc' }
    ): Promise<ScannerAsset[]> {
      const supabase = await createClient();

      // Get all active assets with their latest council session
      const { data: assets, error: assetsError } = await supabase
        .from('assets')
        .select('*')
        .eq('is_active', true)
        .limit(filters.limit || 30);

      if (assetsError) {
        console.error('Error fetching assets:', assetsError);
        throw new Error('Failed to fetch scanner assets');
      }

      // Get latest council session for each asset
      const assetIds = assets.map((a: any) => a.id);

      const { data: sessions, error: sessionsError } = await supabase
        .from('council_sessions')
        .select('*')
        .in('asset_id', assetIds)
        .order('timestamp', { ascending: false });

      if (sessionsError) {
        console.error('Error fetching sessions:', sessionsError);
      }

      // Get latest candles for price change calculation
      const { data: candles, error: candlesError } = await supabase
        .from('candles')
        .select('*')
        .in('asset_id', assetIds)
        .order('timestamp', { ascending: false })
        .limit(assetIds.length * 2);  // 2 candles per asset for comparison

      // Build scanner data
      const scannerData: ScannerAsset[] = assets.map((asset: any) => {
        // Find latest session for this asset
        const latestSession = sessions?.find((s: any) => s.asset_id === asset.id);

        // Find candles for price change
        const assetCandles = candles?.filter((c: any) => c.asset_id === asset.id) || [];
        const latestCandle = assetCandles[0];
        const previousCandle = assetCandles[1];
        const priceChange15m = latestCandle && previousCandle
          ? ((latestCandle.close - previousCandle.close) / previousCandle.close) * 100
          : 0;

        return {
          id: asset.id,
          symbol: asset.symbol,
          lastPrice: parseFloat(asset.last_price) || 0,
          priceChange15m,
          sentimentScore: latestSession?.sentiment_score ?? null,
          technicalSignal: latestSession?.technical_signal ?? null,
          technicalStrength: latestSession?.technical_strength ?? null,
          lastSessionTime: latestSession?.timestamp ? new Date(latestSession.timestamp) : null,
        };
      });

      // Sort data
      return sortScannerData(scannerData, filters.sortBy, filters.sortDirection);
    }

    function sortScannerData(
      data: ScannerAsset[],
      sortBy: ScannerFilters['sortBy'],
      direction: ScannerFilters['sortDirection']
    ): ScannerAsset[] {
      return [...data].sort((a, b) => {
        let aVal: any = a[sortBy];
        let bVal: any = b[sortBy];

        // Handle null values - push to end
        if (aVal === null) return 1;
        if (bVal === null) return -1;

        // String comparison
        if (typeof aVal === 'string') {
          aVal = aVal.toLowerCase();
          bVal = bVal.toLowerCase();
        }

        if (direction === 'asc') {
          return aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
        } else {
          return aVal > bVal ? -1 : aVal < bVal ? 1 : 0;
        }
      });
    }
    ```

### Phase 3: Trade Card Component

- [ ] **Create Stop Loss Progress Indicator**
  - [ ] Create `components/trades/stop-loss-indicator.tsx`:
    ```typescript
    import { cn } from '@/lib/utils';

    interface StopLossIndicatorProps {
      entryPrice: number;
      currentPrice: number;
      stopLossPrice: number;
      takeProfitPrice?: number | null;
      className?: string;
    }

    export function StopLossIndicator({
      entryPrice,
      currentPrice,
      stopLossPrice,
      takeProfitPrice,
      className,
    }: StopLossIndicatorProps) {
      // Calculate positions as percentages
      // Range: stopLoss (0%) to takeProfit (100%), entry in middle
      const range = takeProfitPrice
        ? takeProfitPrice - stopLossPrice
        : (entryPrice - stopLossPrice) * 2;  // Double distance to stop if no TP

      const effectiveMax = takeProfitPrice || entryPrice + (entryPrice - stopLossPrice);

      const entryPercent = ((entryPrice - stopLossPrice) / range) * 100;
      const currentPercent = ((currentPrice - stopLossPrice) / range) * 100;

      // Clamp current price indicator between 0-100
      const clampedCurrent = Math.max(0, Math.min(100, currentPercent));

      // Determine if in profit or loss
      const isProfit = currentPrice >= entryPrice;

      return (
        <div className={cn('space-y-1', className)}>
          <div className="flex justify-between text-xs font-mono text-zinc-500">
            <span>Stop: ${stopLossPrice.toFixed(2)}</span>
            {takeProfitPrice && <span>TP: ${takeProfitPrice.toFixed(2)}</span>}
          </div>

          <div className="relative h-3 bg-zinc-800 rounded-full overflow-hidden">
            {/* Entry marker */}
            <div
              className="absolute top-0 bottom-0 w-0.5 bg-zinc-400 z-10"
              style={{ left: `${entryPercent}%` }}
              title={`Entry: $${entryPrice.toFixed(2)}`}
            />

            {/* Current position fill */}
            <div
              className={cn(
                'absolute top-0 bottom-0 left-0 transition-all duration-300',
                isProfit ? 'bg-emerald-500/50' : 'bg-rose-500/50'
              )}
              style={{ width: `${clampedCurrent}%` }}
            />

            {/* Current price marker */}
            <div
              className={cn(
                'absolute top-0 bottom-0 w-1 rounded-full z-20 transition-all duration-300',
                isProfit ? 'bg-emerald-500' : 'bg-rose-500'
              )}
              style={{ left: `${clampedCurrent}%`, transform: 'translateX(-50%)' }}
              title={`Current: $${currentPrice.toFixed(2)}`}
            />
          </div>

          <div className="flex justify-between text-xs">
            <span className="text-rose-500">Risk Zone</span>
            <span className="text-emerald-500">Profit Zone</span>
          </div>
        </div>
      );
    }
    ```

- [ ] **Create Mini Sparkline Component**
  - [ ] Install Recharts: `pnpm add recharts`
  - [ ] Create `components/trades/sparkline.tsx`:
    ```typescript
    'use client';

    import { LineChart, Line, ResponsiveContainer, YAxis } from 'recharts';
    import { cn } from '@/lib/utils';

    interface SparklineProps {
      data: number[];  // Array of close prices
      isPositive?: boolean;
      className?: string;
    }

    export function Sparkline({ data, isPositive, className }: SparklineProps) {
      // Convert to chart format
      const chartData = data.map((value, index) => ({ value, index }));

      // Determine color based on trend if not specified
      const trend = isPositive ?? (data.length > 1 ? data[data.length - 1] > data[0] : true);
      const color = trend ? '#10b981' : '#f43f5e';  // emerald-500 or rose-500

      return (
        <div className={cn('h-8 w-20', className)}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <YAxis domain={['dataMin', 'dataMax']} hide />
              <Line
                type="monotone"
                dataKey="value"
                stroke={color}
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      );
    }
    ```

- [ ] **Create Trade Card Component**
  - [ ] Create `components/trades/trade-card.tsx`:
    ```typescript
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
      priceHistory?: number[];  // Optional sparkline data
      className?: string;
    }

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
                    <TrendingUp className="h-5 w-5 text-emerald-500" />
                  ) : (
                    <TrendingDown className="h-5 w-5 text-rose-500" />
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
    ```

### Phase 4: Active Trades Widget

- [ ] **Create Active Trades Container**
  - [ ] Create `components/trades/active-trades.tsx`:
    ```typescript
    'use client';

    import { useState, useEffect } from 'react';
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

    export function ActiveTrades({ initialTrades = [], className }: ActiveTradesProps) {
      const [trades, setTrades] = useState<TradeWithMetrics[]>(initialTrades);
      const [isLoading, setIsLoading] = useState(false);
      const [error, setError] = useState<string | null>(null);

      useEffect(() => {
        if (initialTrades.length === 0) {
          loadTrades();
        }
      }, []);

      const loadTrades = async () => {
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
      };

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
            <div className="flex items-center gap-2 p-2 bg-amber-500/10 border border-amber-500/50 rounded-md mb-4">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              <span className="text-xs text-amber-500">
                {atRiskTrades.length} trade{atRiskTrades.length !== 1 ? 's' : ''} within 2% of stop loss
              </span>
            </div>
          )}

          {/* Error state */}
          {error && (
            <div className="bg-rose-500/10 border border-rose-500/50 text-rose-500 p-3 rounded-md mb-4">
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
    ```

### Phase 5: Scanner Table with TanStack Table

- [ ] **Install TanStack Table**
  - [ ] Run `pnpm add @tanstack/react-table`

- [ ] **Create Scanner Table Component**
  - [ ] Create `components/scanner/scanner-table.tsx`:
    ```typescript
    'use client';

    import { useState, useMemo } from 'react';
    import {
      useReactTable,
      getCoreRowModel,
      getSortedRowModel,
      SortingState,
      flexRender,
      ColumnDef,
    } from '@tanstack/react-table';
    import {
      Table,
      TableBody,
      TableCell,
      TableHead,
      TableHeader,
      TableRow,
    } from '@/components/ui/table';
    import { Badge } from '@/components/ui/badge';
    import { cn } from '@/lib/utils';
    import { ScannerAsset } from '@/types/scanner';
    import { TrendingUp, TrendingDown, Minus, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';
    import { formatDistanceToNow } from 'date-fns';

    interface ScannerTableProps {
      assets: ScannerAsset[];
      onRowClick?: (asset: ScannerAsset) => void;
      className?: string;
    }

    export function ScannerTable({ assets, onRowClick, className }: ScannerTableProps) {
      const [sorting, setSorting] = useState<SortingState>([
        { id: 'sentimentScore', desc: false },  // Low sentiment (fear) first
      ]);

      const columns: ColumnDef<ScannerAsset>[] = useMemo(
        () => [
          {
            accessorKey: 'symbol',
            header: ({ column }) => (
              <SortableHeader column={column}>Symbol</SortableHeader>
            ),
            cell: ({ row }) => (
              <span className="font-mono font-semibold text-zinc-100">
                {row.original.symbol}
              </span>
            ),
          },
          {
            accessorKey: 'lastPrice',
            header: ({ column }) => (
              <SortableHeader column={column}>Price</SortableHeader>
            ),
            cell: ({ row }) => (
              <div className="font-mono text-right">
                <span className="text-zinc-100">
                  ${row.original.lastPrice.toFixed(2)}
                </span>
                <div
                  className={cn(
                    'text-xs',
                    row.original.priceChange15m >= 0 ? 'text-emerald-500' : 'text-rose-500'
                  )}
                >
                  {row.original.priceChange15m >= 0 ? '+' : ''}
                  {row.original.priceChange15m.toFixed(2)}%
                </div>
              </div>
            ),
          },
          {
            accessorKey: 'sentimentScore',
            header: ({ column }) => (
              <SortableHeader column={column}>Fear</SortableHeader>
            ),
            cell: ({ row }) => {
              const score = row.original.sentimentScore;
              if (score === null) {
                return <span className="text-zinc-500">--</span>;
              }

              // Lower score = more fear = green (buying opportunity)
              const colorClass = score < 20
                ? 'text-emerald-500'
                : score < 40
                ? 'text-emerald-400'
                : score < 60
                ? 'text-zinc-400'
                : score < 80
                ? 'text-rose-400'
                : 'text-rose-500';

              return (
                <span className={cn('font-mono', colorClass)}>
                  {score}
                </span>
              );
            },
            sortingFn: (rowA, rowB) => {
              const a = rowA.original.sentimentScore ?? 999;
              const b = rowB.original.sentimentScore ?? 999;
              return a - b;
            },
          },
          {
            accessorKey: 'technicalSignal',
            header: ({ column }) => (
              <SortableHeader column={column}>Signal</SortableHeader>
            ),
            cell: ({ row }) => {
              const signal = row.original.technicalSignal;
              if (!signal) {
                return <span className="text-zinc-500">--</span>;
              }

              const Icon = signal === 'BULLISH'
                ? TrendingUp
                : signal === 'BEARISH'
                ? TrendingDown
                : Minus;

              const colorClass = signal === 'BULLISH'
                ? 'text-emerald-500'
                : signal === 'BEARISH'
                ? 'text-rose-500'
                : 'text-zinc-400';

              return (
                <div className={cn('flex items-center gap-1', colorClass)}>
                  <Icon className="h-3 w-3" />
                  <span className="text-xs">{signal}</span>
                </div>
              );
            },
          },
        ],
        []
      );

      const table = useReactTable({
        data: assets,
        columns,
        state: { sorting },
        onSortingChange: setSorting,
        getCoreRowModel: getCoreRowModel(),
        getSortedRowModel: getSortedRowModel(),
      });

      return (
        <div className={cn('rounded-md border border-zinc-800', className)}>
          <Table>
            <TableHeader>
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id} className="border-zinc-800 hover:bg-transparent">
                  {headerGroup.headers.map((header) => (
                    <TableHead
                      key={header.id}
                      className="text-zinc-400 text-xs h-9"
                    >
                      {header.isPlaceholder
                        ? null
                        : flexRender(header.column.columnDef.header, header.getContext())}
                    </TableHead>
                  ))}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {table.getRowModel().rows.length > 0 ? (
                table.getRowModel().rows.map((row) => (
                  <TableRow
                    key={row.id}
                    className={cn(
                      'border-zinc-800 transition-colors',
                      onRowClick && 'cursor-pointer hover:bg-zinc-800/50'
                    )}
                    onClick={() => onRowClick?.(row.original)}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <TableCell key={cell.id} className="py-2 text-sm">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell
                    colSpan={columns.length}
                    className="h-24 text-center text-zinc-500"
                  >
                    No assets found
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      );
    }

    function SortableHeader({
      column,
      children,
    }: {
      column: any;
      children: React.ReactNode;
    }) {
      const sorted = column.getIsSorted();

      return (
        <button
          className="flex items-center gap-1 hover:text-zinc-100 transition-colors"
          onClick={() => column.toggleSorting(sorted === 'asc')}
        >
          {children}
          {sorted === 'asc' ? (
            <ArrowUp className="h-3 w-3" />
          ) : sorted === 'desc' ? (
            <ArrowDown className="h-3 w-3" />
          ) : (
            <ArrowUpDown className="h-3 w-3 opacity-50" />
          )}
        </button>
      );
    }
    ```

- [ ] **Create Market Scanner Container**
  - [ ] Create `components/scanner/market-scanner.tsx`:
    ```typescript
    'use client';

    import { useState, useEffect } from 'react';
    import { Button } from '@/components/ui/button';
    import { RefreshCw } from 'lucide-react';
    import { cn } from '@/lib/utils';
    import { ScannerAsset } from '@/types/scanner';
    import { fetchScannerAssets } from '@/app/dashboard/scanner/actions';
    import { ScannerTable } from './scanner-table';

    interface MarketScannerProps {
      initialAssets?: ScannerAsset[];
      onAssetSelect?: (asset: ScannerAsset) => void;
      className?: string;
    }

    export function MarketScanner({
      initialAssets = [],
      onAssetSelect,
      className,
    }: MarketScannerProps) {
      const [assets, setAssets] = useState<ScannerAsset[]>(initialAssets);
      const [isLoading, setIsLoading] = useState(false);
      const [error, setError] = useState<string | null>(null);

      useEffect(() => {
        if (initialAssets.length === 0) {
          loadAssets();
        }
      }, []);

      const loadAssets = async () => {
        setIsLoading(true);
        setError(null);

        try {
          const data = await fetchScannerAssets();
          setAssets(data);
        } catch (err) {
          setError('Failed to load scanner data');
          console.error(err);
        } finally {
          setIsLoading(false);
        }
      };

      // Count opportunities (low fear score)
      const opportunities = assets.filter(
        (a) => a.sentimentScore !== null && a.sentimentScore < 20
      );

      return (
        <div className={cn('flex flex-col h-full', className)}>
          {/* Header */}
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-semibold text-zinc-100">Market Scanner</h2>
              <p className="text-sm text-zinc-400">
                {opportunities.length} high-fear asset{opportunities.length !== 1 ? 's' : ''}
              </p>
            </div>
            <Button
              size="sm"
              variant="ghost"
              onClick={loadAssets}
              disabled={isLoading}
              className="h-8"
            >
              <RefreshCw className={cn('h-4 w-4', isLoading && 'animate-spin')} />
            </Button>
          </div>

          {/* Error state */}
          {error && (
            <div className="bg-rose-500/10 border border-rose-500/50 text-rose-500 p-3 rounded-md mb-4 text-sm">
              {error}
            </div>
          )}

          {/* Scanner Table */}
          <div className="flex-1 overflow-auto">
            <ScannerTable
              assets={assets}
              onRowClick={onAssetSelect}
            />
          </div>
        </div>
      );
    }
    ```

### Phase 6: Page Integration

- [ ] **Create Trades Page**
  - [ ] Create `app/dashboard/trades/page.tsx`:
    ```typescript
    import { Metadata } from 'next';
    import { ActiveTrades } from '@/components/trades/active-trades';
    import { fetchOpenTrades } from './actions';

    export const metadata: Metadata = {
      title: 'Active Trades | ContrarianAI',
      description: 'Monitor your open trading positions',
    };

    export default async function TradesPage() {
      const trades = await fetchOpenTrades();

      return (
        <div className="h-[calc(100vh-8rem)]">
          <ActiveTrades initialTrades={trades} />
        </div>
      );
    }
    ```

- [ ] **Create Scanner Page**
  - [ ] Create `app/dashboard/scanner/page.tsx`:
    ```typescript
    import { Metadata } from 'next';
    import { MarketScanner } from '@/components/scanner/market-scanner';
    import { fetchScannerAssets } from './actions';

    export const metadata: Metadata = {
      title: 'Market Scanner | ContrarianAI',
      description: 'Scan market for trading opportunities',
    };

    export default async function ScannerPage() {
      const assets = await fetchScannerAssets();

      return (
        <div className="h-[calc(100vh-8rem)]">
          <MarketScanner initialAssets={assets} />
        </div>
      );
    }
    ```

- [ ] **Update Dashboard Overview with Active Components**
  - [ ] Update `app/dashboard/page.tsx`:
    ```typescript
    import { Metadata } from 'next';
    import { CouncilFeed } from '@/components/council/council-feed';
    import { ActiveTrades } from '@/components/trades/active-trades';
    import { MarketScanner } from '@/components/scanner/market-scanner';
    import { fetchCouncilSessions } from './council/actions';
    import { fetchOpenTrades } from './trades/actions';
    import { fetchScannerAssets } from './scanner/actions';

    export const metadata: Metadata = {
      title: 'Dashboard | ContrarianAI',
      description: 'ContrarianAI Mission Control Dashboard',
    };

    export default async function DashboardPage() {
      // Parallel data fetching
      const [councilData, trades, scannerAssets] = await Promise.all([
        fetchCouncilSessions({ limit: 10 }),
        fetchOpenTrades(),
        fetchScannerAssets({ limit: 30 }),
      ]);

      return (
        <div className="space-y-6">
          <h1 className="text-2xl font-bold text-zinc-100">Mission Control</h1>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            {/* Council Feed - 40% */}
            <div className="lg:col-span-5 bg-zinc-900 rounded-lg border border-zinc-800 p-4 h-[600px]">
              <CouncilFeed initialSessions={councilData.sessions} />
            </div>

            {/* Active Trades - 35% */}
            <div className="lg:col-span-4 bg-zinc-900 rounded-lg border border-zinc-800 p-4 h-[600px]">
              <ActiveTrades initialTrades={trades} />
            </div>

            {/* Scanner - 25% */}
            <div className="lg:col-span-3 bg-zinc-900 rounded-lg border border-zinc-800 p-4 h-[600px]">
              <MarketScanner initialAssets={scannerAssets} />
            </div>
          </div>
        </div>
      );
    }
    ```

### Phase 7: Testing & Verification

- [ ] **Create Test Data Scripts**
  - [ ] Create seed script for Trade records
  - [ ] Create seed script for Asset records with price data

- [ ] **Manual Testing Checklist**
  - [ ] Navigate to `/dashboard/trades`
  - [ ] Verify trade cards display with correct P&L colors
  - [ ] Verify stop loss indicator shows correct position
  - [ ] Verify sparkline renders (if price data available)
  - [ ] Verify "at risk" warning appears for close stops
  - [ ] Navigate to `/dashboard/scanner`
  - [ ] Verify table displays all 30 assets
  - [ ] Click column headers to sort
  - [ ] Verify sorting by Fear Score works (low first)
  - [ ] Verify fear score colors (green = fear, red = greed)
  - [ ] Navigate to `/dashboard` (overview)
  - [ ] Verify 3-column layout displays correctly
  - [ ] Test on mobile viewport - verify stacked layout

---

## Dev Notes

### Architecture Context

**Reference:** `docs/core/architecture.md` Section 4.1 (Trade Entity)
**Reference:** `docs/core/uiux.md` Section 6.2-6.3 (Trade Card, Scanner Table)

**Database Schema (Trade):**
```sql
CREATE TABLE trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID REFERENCES assets(id),
    status VARCHAR(20) NOT NULL,  -- OPEN, CLOSED, STOPPED_OUT, TAKE_PROFIT
    direction VARCHAR(10) DEFAULT 'LONG',
    entry_price DECIMAL(20, 8) NOT NULL,
    size DECIMAL(20, 8) NOT NULL,
    entry_time TIMESTAMPTZ NOT NULL,
    stop_loss_price DECIMAL(20, 8) NOT NULL,
    take_profit_price DECIMAL(20, 8),
    exit_price DECIMAL(20, 8),
    exit_time TIMESTAMPTZ,
    pnl DECIMAL(20, 8),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Technical Specifications

**Trade Card Metrics (Calculated Client-Side):**
```
unrealizedPnl = (currentPrice - entryPrice) * size
unrealizedPnlPercent = ((currentPrice - entryPrice) / entryPrice) * 100
distanceToStopPercent = ((currentPrice - stopLossPrice) / currentPrice) * 100
```

**Scanner Sorting:**
- Default sort: Fear Score ascending (lowest = most fear = best opportunity)
- All columns sortable via TanStack Table
- Null values pushed to end of sort

**Color Coding (from uiux.md):**
| Element | Positive | Negative |
|---------|----------|----------|
| P&L Text | `text-emerald-500` | `text-rose-500` |
| Sparkline | `stroke="#10b981"` | `stroke="#f43f5e"` |
| Fear Score (low) | `text-emerald-500` | - |
| Fear Score (high) | - | `text-rose-500` |

### Implementation Guidance

**Real-time Price for P&L:**
For V1, we use the `lastPrice` from the Asset table (updated by Kraken ingest every 15 minutes). For more accurate real-time P&L:
1. Consider client-side fetch to Kraken public ticker API
2. Or use Supabase Realtime to subscribe to Asset price updates

**TanStack Table Best Practices:**
- Use `useMemo` for column definitions (prevents re-renders)
- Implement custom sorting functions for nullable columns
- Keep table compact for "information density" principle

**Stop Loss Indicator Math:**
```
range = takeProfitPrice - stopLossPrice (or 2x entry-to-stop distance)
entryPercent = (entryPrice - stopLossPrice) / range * 100
currentPercent = (currentPrice - stopLossPrice) / range * 100
```

### Accessibility Requirements

- Stop loss progress bar must have `role="progressbar"` (implicit via tooltip)
- Table must be keyboard navigable
- Sortable headers must indicate sort direction via aria
- Color should not be sole indicator - use icons (TrendingUp/Down)
- Warning messages must be perceivable (not just color)

### Dependencies & Prerequisites

**Required Completions:**
- Story 4.1: Layout, authentication, Shadcn components
- Story 4.2: Council feed (for dashboard integration)
- Story 1.2: Database schema with Trade and Asset tables
- Story 3.x: Trade records being written by bot

**Required Shadcn Components:**
- Table (installed in 4.1)
- Card (installed in 4.1)
- Badge (installed in 4.1)
- ScrollArea (installed in 4.1)
- Button (installed in 4.1)

**Additional Dependencies:**
- `recharts` for Sparkline charts
- `@tanstack/react-table` for Scanner table
- `date-fns` for time formatting (installed in 4.2)

### Downstream Dependencies

- **Story 4.4**: Will add realtime subscription to auto-update trades and scanner

---

## Testing Strategy

### Unit Tests

- [ ] Test `StopLossIndicator` calculates positions correctly
- [ ] Test `StopLossIndicator` handles missing takeProfit
- [ ] Test `Sparkline` renders with positive/negative colors
- [ ] Test `TradeCard` displays all metrics correctly
- [ ] Test `ScannerTable` sorting works for all columns
- [ ] Test null value handling in scanner sort

### Integration Tests

- [ ] Test `fetchOpenTrades` returns correct structure
- [ ] Test `fetchScannerAssets` joins data correctly
- [ ] Test parallel data fetching on dashboard page

### Manual Testing Scenarios

1. Create test trade at loss - verify red styling
2. Create test trade at profit - verify green styling
3. Create trade close to stop - verify warning appears
4. Sort scanner by Fear - verify lowest first
5. Click scanner row - verify callback fires
6. Test with empty trades - verify empty state
7. Test with empty assets - verify empty table state

### Acceptance Criteria Validation

- [ ] AC1a: Active Trades shows OPEN trades only
- [ ] AC1b: Entry Price, Current Price, P&L % displayed
- [ ] AC1c: Stop Loss distance visualized with progress bar
- [ ] AC2a: Scanner shows Top 30 assets in table
- [ ] AC2b: Columns include Symbol, Price, Sentiment, Signal
- [ ] AC2c: Table sortable by Fear Score

---

## Technical Considerations

### Security

- Server Actions validate filters before querying
- No direct database access from client
- Sensitive trade data protected by auth middleware

### Performance

- Parallel data fetching on dashboard (`Promise.all`)
- TanStack Table uses virtualization-ready architecture
- Sparkline uses minimal data points for performance
- Consider debouncing price updates for P&L calculation

### Scalability

- Scanner limited to 30 assets (configurable)
- Trade cards use efficient re-renders (React.memo candidate)
- Consider pagination for trade history

### Edge Cases

- No open trades: Display helpful empty state
- Asset without price data: Show last known price
- Missing sentiment data: Display "--" placeholder
- Very large P&L: Ensure number formatting handles it
- Network error: Display retry button

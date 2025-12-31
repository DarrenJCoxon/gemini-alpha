# Story 4.4: Realtime Realization (Supabase)

**Status:** Draft
**Epic:** 4 - Mission Control Dashboard (Next.js)
**Priority:** High

---

## Story

**As a** User,
**I want** the dashboard to update automatically when the bot acts,
**so that** I don't have to manually refresh the page to see new signals.

---

## Acceptance Criteria

1. Dashboard subscribes to Supabase Realtime changes on `CouncilSession` and `Trade` tables.
2. When a new Council Session is inserted (by the Python bot), the Feed automatically shows the new card at the top.
3. When a Trade status changes (e.g., STOPPED OUT), the Active Trades UI updates instantly.
4. Toast notifications appear for major events ("New Buy Signal: SOL/USD").

---

## Tasks / Subtasks

### Phase 1: Supabase Realtime Client Setup

- [ ] **Create Realtime Client Utility**
  - [ ] Create `lib/supabase/realtime.ts`:
    ```typescript
    import { createClient } from './client';
    import { RealtimeChannel, RealtimePostgresChangesPayload } from '@supabase/supabase-js';

    export type RealtimeEventType = 'INSERT' | 'UPDATE' | 'DELETE';

    export interface RealtimeSubscription {
      channel: RealtimeChannel;
      unsubscribe: () => void;
    }

    /**
     * Subscribe to realtime changes on a specific table.
     *
     * @param table - The table name to subscribe to
     * @param event - The event type (INSERT, UPDATE, DELETE, or *)
     * @param callback - Function called when changes occur
     * @param filter - Optional filter string (e.g., "status=eq.OPEN")
     * @returns Subscription object with unsubscribe method
     */
    export function subscribeToTable<T extends Record<string, any>>(
      table: string,
      event: RealtimeEventType | '*',
      callback: (payload: RealtimePostgresChangesPayload<T>) => void,
      filter?: string
    ): RealtimeSubscription {
      const supabase = createClient();

      const channelName = `${table}-${event}-${Date.now()}`;

      const channel = supabase
        .channel(channelName)
        .on(
          'postgres_changes',
          {
            event: event === '*' ? undefined : event,
            schema: 'public',
            table,
            filter,
          },
          callback
        )
        .subscribe((status) => {
          console.log(`[Realtime] ${channelName} subscription status:`, status);
        });

      return {
        channel,
        unsubscribe: () => {
          console.log(`[Realtime] Unsubscribing from ${channelName}`);
          supabase.removeChannel(channel);
        },
      };
    }

    /**
     * Subscribe to multiple tables at once.
     */
    export function subscribeToMultipleTables(
      subscriptions: Array<{
        table: string;
        event: RealtimeEventType | '*';
        callback: (payload: any) => void;
        filter?: string;
      }>
    ): () => void {
      const subs = subscriptions.map((config) =>
        subscribeToTable(config.table, config.event, config.callback, config.filter)
      );

      return () => {
        subs.forEach((sub) => sub.unsubscribe());
      };
    }
    ```

- [ ] **Enable Realtime in Supabase Dashboard**
  - [ ] Navigate to Supabase Dashboard > Database > Replication
  - [ ] Enable realtime for `council_sessions` table
  - [ ] Enable realtime for `trades` table
  - [ ] Enable realtime for `assets` table (for price updates)
  - [ ] Verify Publication includes all required tables

### Phase 2: Council Session Realtime Hook

- [ ] **Create useCouncilListener Hook**
  - [ ] Create `hooks/use-council-listener.ts`:
    ```typescript
    'use client';

    import { useEffect, useCallback, useRef } from 'react';
    import { subscribeToTable } from '@/lib/supabase/realtime';
    import { CouncilSession, DecisionType } from '@/types/council';
    import { toast } from 'sonner';

    interface UseCouncilListenerOptions {
      onNewSession: (session: CouncilSession) => void;
      showToasts?: boolean;
    }

    /**
     * Hook to listen for new council session inserts via Supabase Realtime.
     */
    export function useCouncilListener({
      onNewSession,
      showToasts = true,
    }: UseCouncilListenerOptions) {
      const callbackRef = useRef(onNewSession);

      // Keep callback ref updated
      useEffect(() => {
        callbackRef.current = onNewSession;
      }, [onNewSession]);

      useEffect(() => {
        const { unsubscribe } = subscribeToTable(
          'council_sessions',
          'INSERT',
          (payload) => {
            console.log('[CouncilListener] New session received:', payload);

            const newRecord = payload.new;
            if (!newRecord) return;

            // Transform to CouncilSession type
            const session: CouncilSession = {
              id: newRecord.id,
              assetId: newRecord.asset_id,
              timestamp: new Date(newRecord.timestamp),
              sentimentScore: newRecord.sentiment_score,
              technicalSignal: newRecord.technical_signal,
              technicalStrength: newRecord.technical_strength,
              technicalDetails: newRecord.technical_details,
              visionAnalysis: newRecord.vision_analysis,
              visionConfidence: newRecord.vision_confidence,
              visionValid: newRecord.vision_valid,
              finalDecision: newRecord.final_decision as DecisionType,
              decisionConfidence: newRecord.decision_confidence,
              reasoningLog: newRecord.reasoning_log,
              createdAt: new Date(newRecord.created_at),
              // Asset will be fetched separately or passed
              asset: undefined,
            };

            // Trigger callback
            callbackRef.current(session);

            // Show toast notification
            if (showToasts) {
              showSessionToast(session);
            }
          }
        );

        return () => {
          unsubscribe();
        };
      }, [showToasts]);
    }

    function showSessionToast(session: CouncilSession) {
      const decision = session.finalDecision;
      const assetSymbol = session.asset?.symbol || session.assetId;

      switch (decision) {
        case 'BUY':
          toast.success(`New BUY Signal: ${assetSymbol}`, {
            description: `Fear Score: ${session.sentimentScore} | Confidence: ${session.decisionConfidence}%`,
            duration: 8000,
          });
          break;

        case 'SELL':
          toast.error(`SELL Signal: ${assetSymbol}`, {
            description: `Confidence: ${session.decisionConfidence}%`,
            duration: 8000,
          });
          break;

        case 'HOLD':
          // Only show HOLD toasts for significant decisions
          if (session.decisionConfidence > 70) {
            toast.info(`Council Decision: HOLD ${assetSymbol}`, {
              description: session.reasoningLog.slice(0, 100) + '...',
              duration: 5000,
            });
          }
          break;
      }
    }
    ```

### Phase 3: Trade Realtime Hook

- [ ] **Create useTradeListener Hook**
  - [ ] Create `hooks/use-trade-listener.ts`:
    ```typescript
    'use client';

    import { useEffect, useCallback, useRef } from 'react';
    import { subscribeToTable } from '@/lib/supabase/realtime';
    import { Trade, TradeStatus } from '@/types/trade';
    import { toast } from 'sonner';

    interface UseTradeListenerOptions {
      onTradeInsert?: (trade: Trade) => void;
      onTradeUpdate?: (trade: Trade) => void;
      onTradeDelete?: (tradeId: string) => void;
      showToasts?: boolean;
    }

    /**
     * Hook to listen for trade changes via Supabase Realtime.
     */
    export function useTradeListener({
      onTradeInsert,
      onTradeUpdate,
      onTradeDelete,
      showToasts = true,
    }: UseTradeListenerOptions) {
      const insertRef = useRef(onTradeInsert);
      const updateRef = useRef(onTradeUpdate);
      const deleteRef = useRef(onTradeDelete);

      // Keep refs updated
      useEffect(() => {
        insertRef.current = onTradeInsert;
        updateRef.current = onTradeUpdate;
        deleteRef.current = onTradeDelete;
      }, [onTradeInsert, onTradeUpdate, onTradeDelete]);

      useEffect(() => {
        // Subscribe to all trade changes
        const { unsubscribe } = subscribeToTable(
          'trades',
          '*',
          (payload) => {
            console.log('[TradeListener] Trade event:', payload.eventType, payload);

            const transformTrade = (record: any): Trade => ({
              id: record.id,
              assetId: record.asset_id,
              status: record.status as TradeStatus,
              direction: record.direction || 'LONG',
              entryPrice: parseFloat(record.entry_price),
              size: parseFloat(record.size),
              entryTime: new Date(record.entry_time),
              stopLossPrice: parseFloat(record.stop_loss_price),
              takeProfitPrice: record.take_profit_price ? parseFloat(record.take_profit_price) : null,
              exitPrice: record.exit_price ? parseFloat(record.exit_price) : null,
              exitTime: record.exit_time ? new Date(record.exit_time) : null,
              pnl: record.pnl ? parseFloat(record.pnl) : null,
              createdAt: new Date(record.created_at),
              updatedAt: new Date(record.updated_at),
            });

            switch (payload.eventType) {
              case 'INSERT':
                if (insertRef.current && payload.new) {
                  const trade = transformTrade(payload.new);
                  insertRef.current(trade);

                  if (showToasts) {
                    toast.success(`Trade Opened: ${trade.assetId}`, {
                      description: `Entry: $${trade.entryPrice.toFixed(2)} | Size: ${trade.size.toFixed(4)}`,
                      duration: 6000,
                    });
                  }
                }
                break;

              case 'UPDATE':
                if (updateRef.current && payload.new) {
                  const trade = transformTrade(payload.new);
                  const oldStatus = (payload.old as any)?.status;
                  const newStatus = trade.status;

                  updateRef.current(trade);

                  // Show toast for status changes
                  if (showToasts && oldStatus !== newStatus) {
                    showTradeStatusToast(trade, oldStatus, newStatus);
                  }
                }
                break;

              case 'DELETE':
                if (deleteRef.current && payload.old) {
                  deleteRef.current((payload.old as any).id);
                }
                break;
            }
          }
        );

        return () => {
          unsubscribe();
        };
      }, [showToasts]);
    }

    function showTradeStatusToast(trade: Trade, oldStatus: string, newStatus: TradeStatus) {
      switch (newStatus) {
        case 'STOPPED_OUT':
          toast.error(`Trade Stopped Out: ${trade.assetId}`, {
            description: `P&L: $${trade.pnl?.toFixed(2) || '0.00'}`,
            duration: 8000,
          });
          break;

        case 'TAKE_PROFIT':
          toast.success(`Take Profit Hit: ${trade.assetId}`, {
            description: `P&L: +$${trade.pnl?.toFixed(2) || '0.00'}`,
            duration: 8000,
          });
          break;

        case 'CLOSED':
          const isProfit = (trade.pnl || 0) >= 0;
          if (isProfit) {
            toast.success(`Trade Closed: ${trade.assetId}`, {
              description: `P&L: +$${trade.pnl?.toFixed(2) || '0.00'}`,
              duration: 6000,
            });
          } else {
            toast.warning(`Trade Closed: ${trade.assetId}`, {
              description: `P&L: $${trade.pnl?.toFixed(2) || '0.00'}`,
              duration: 6000,
            });
          }
          break;
      }
    }
    ```

### Phase 4: Asset Price Realtime Hook

- [ ] **Create useAssetPriceListener Hook**
  - [ ] Create `hooks/use-asset-price-listener.ts`:
    ```typescript
    'use client';

    import { useEffect, useRef } from 'react';
    import { subscribeToTable } from '@/lib/supabase/realtime';

    interface AssetPriceUpdate {
      assetId: string;
      symbol: string;
      lastPrice: number;
    }

    interface UseAssetPriceListenerOptions {
      onPriceUpdate: (update: AssetPriceUpdate) => void;
      assetIds?: string[];  // Optional filter to specific assets
    }

    /**
     * Hook to listen for asset price updates via Supabase Realtime.
     * Updates when the `last_price` column changes on the assets table.
     */
    export function useAssetPriceListener({
      onPriceUpdate,
      assetIds,
    }: UseAssetPriceListenerOptions) {
      const callbackRef = useRef(onPriceUpdate);

      useEffect(() => {
        callbackRef.current = onPriceUpdate;
      }, [onPriceUpdate]);

      useEffect(() => {
        const { unsubscribe } = subscribeToTable(
          'assets',
          'UPDATE',
          (payload) => {
            const newRecord = payload.new;
            const oldRecord = payload.old as any;

            if (!newRecord) return;

            // Only trigger if price actually changed
            if (newRecord.last_price === oldRecord?.last_price) return;

            // Filter by asset IDs if provided
            if (assetIds && !assetIds.includes(newRecord.id)) return;

            callbackRef.current({
              assetId: newRecord.id,
              symbol: newRecord.symbol,
              lastPrice: parseFloat(newRecord.last_price),
            });
          }
        );

        return () => {
          unsubscribe();
        };
      }, [assetIds]);
    }
    ```

### Phase 5: Integrate Realtime into Council Feed

- [ ] **Update CouncilFeed Component with Realtime**
  - [ ] Update `components/council/council-feed.tsx`:
    ```typescript
    'use client';

    import { useState, useEffect, useCallback } from 'react';
    import { ScrollArea } from '@/components/ui/scroll-area';
    import { Skeleton } from '@/components/ui/skeleton';
    import { Button } from '@/components/ui/button';
    import { RefreshCw, Wifi, WifiOff } from 'lucide-react';
    import { cn } from '@/lib/utils';
    import { CouncilSession, CouncilFeedFilters, DecisionType } from '@/types/council';
    import { fetchCouncilSessions } from '@/app/dashboard/council/actions';
    import { CouncilCard } from './council-card';
    import { useInfiniteScroll } from '@/hooks/use-infinite-scroll';
    import { useCouncilListener } from '@/hooks/use-council-listener';

    interface CouncilFeedProps {
      initialSessions?: CouncilSession[];
      className?: string;
    }

    export function CouncilFeed({ initialSessions = [], className }: CouncilFeedProps) {
      const [sessions, setSessions] = useState<CouncilSession[]>(initialSessions);
      const [isLoading, setIsLoading] = useState(false);
      const [isRefreshing, setIsRefreshing] = useState(false);
      const [hasMore, setHasMore] = useState(true);
      const [cursor, setCursor] = useState<string | null>(null);
      const [error, setError] = useState<string | null>(null);
      const [filter, setFilter] = useState<DecisionType | null>(null);
      const [newSessionIds, setNewSessionIds] = useState<Set<string>>(new Set());

      // Realtime listener for new sessions
      const handleNewSession = useCallback((session: CouncilSession) => {
        // Add to top of list
        setSessions((prev) => {
          // Avoid duplicates
          if (prev.some((s) => s.id === session.id)) return prev;

          // Apply current filter
          if (filter && session.finalDecision !== filter) return prev;

          return [session, ...prev];
        });

        // Mark as new for animation
        setNewSessionIds((prev) => new Set(prev).add(session.id));

        // Remove "new" status after animation completes
        setTimeout(() => {
          setNewSessionIds((prev) => {
            const updated = new Set(prev);
            updated.delete(session.id);
            return updated;
          });
        }, 1000);
      }, [filter]);

      // Enable realtime listener
      useCouncilListener({
        onNewSession: handleNewSession,
        showToasts: true,
      });

      // ... rest of component remains the same as Story 4.2 ...
      // (loadSessions, handleRefresh, handleFilterChange, etc.)

      // Fetch initial data if not provided
      useEffect(() => {
        if (initialSessions.length === 0) {
          loadSessions();
        }
      }, []);

      const loadSessions = useCallback(async (reset = false) => {
        if (isLoading) return;

        setIsLoading(true);
        setError(null);

        try {
          const filters: CouncilFeedFilters = {
            cursor: reset ? undefined : cursor || undefined,
            decision: filter || undefined,
          };

          const result = await fetchCouncilSessions(filters);

          if (reset) {
            setSessions(result.sessions);
          } else {
            setSessions((prev) => [...prev, ...result.sessions]);
          }

          setCursor(result.nextCursor);
          setHasMore(result.hasMore);
        } catch (err) {
          setError('Failed to load council sessions');
          console.error(err);
        } finally {
          setIsLoading(false);
        }
      }, [cursor, filter, isLoading]);

      const handleRefresh = async () => {
        setIsRefreshing(true);
        setCursor(null);
        await loadSessions(true);
        setIsRefreshing(false);
      };

      const handleFilterChange = (newFilter: DecisionType | null) => {
        setFilter(newFilter);
        setCursor(null);
        setSessions([]);
        setHasMore(true);
      };

      useEffect(() => {
        loadSessions(true);
      }, [filter]);

      const { loadMoreRef } = useInfiniteScroll({
        onLoadMore: () => loadSessions(),
        hasMore,
        isLoading,
      });

      return (
        <div className={cn('flex flex-col h-full', className)}>
          {/* Header with Realtime Status */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-zinc-100">Council Chamber</h2>
              <Wifi className="h-4 w-4 text-emerald-500 animate-pulse" aria-label="Realtime connected" />
            </div>
            <div className="flex items-center gap-2">
              {/* Filter buttons */}
              <div className="flex gap-1">
                <Button
                  size="sm"
                  variant={filter === null ? 'secondary' : 'ghost'}
                  onClick={() => handleFilterChange(null)}
                  className="text-xs h-7"
                >
                  All
                </Button>
                <Button
                  size="sm"
                  variant={filter === 'BUY' ? 'secondary' : 'ghost'}
                  onClick={() => handleFilterChange('BUY')}
                  className="text-xs h-7 text-emerald-500"
                >
                  Buy
                </Button>
                <Button
                  size="sm"
                  variant={filter === 'SELL' ? 'secondary' : 'ghost'}
                  onClick={() => handleFilterChange('SELL')}
                  className="text-xs h-7 text-rose-500"
                >
                  Sell
                </Button>
              </div>

              {/* Refresh button */}
              <Button
                size="sm"
                variant="ghost"
                onClick={handleRefresh}
                disabled={isRefreshing}
                className="h-7"
              >
                <RefreshCw
                  className={cn('h-4 w-4', isRefreshing && 'animate-spin')}
                />
              </Button>
            </div>
          </div>

          {/* Error state */}
          {error && (
            <div className="bg-rose-500/10 border border-rose-500/50 text-rose-500 p-3 rounded-md mb-4">
              {error}
            </div>
          )}

          {/* Feed content */}
          <ScrollArea className="flex-1">
            <div className="space-y-4 pr-4">
              {sessions.map((session) => (
                <CouncilCard
                  key={session.id}
                  session={session}
                  isNew={newSessionIds.has(session.id)}
                />
              ))}

              {/* Loading skeletons */}
              {isLoading && (
                <>
                  <CouncilCardSkeleton />
                  <CouncilCardSkeleton />
                </>
              )}

              {/* Load more trigger */}
              {hasMore && <div ref={loadMoreRef} className="h-4" />}

              {/* Empty state */}
              {!isLoading && sessions.length === 0 && (
                <div className="text-center py-12 text-zinc-500">
                  <p>No council sessions found</p>
                  <p className="text-sm mt-2">
                    Sessions will appear here when the bot makes decisions
                  </p>
                </div>
              )}

              {/* End of list */}
              {!hasMore && sessions.length > 0 && (
                <p className="text-center text-zinc-500 text-sm py-4">
                  No more sessions to load
                </p>
              )}
            </div>
          </ScrollArea>
        </div>
      );
    }

    function CouncilCardSkeleton() {
      return (
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Skeleton className="h-5 w-20 bg-zinc-800" />
              <Skeleton className="h-4 w-24 bg-zinc-800" />
            </div>
            <Skeleton className="h-6 w-16 bg-zinc-800" />
          </div>
          <Skeleton className="h-12 w-full bg-zinc-800" />
          <Skeleton className="h-4 w-32 bg-zinc-800" />
        </div>
      );
    }
    ```

### Phase 6: Integrate Realtime into Active Trades

- [ ] **Update ActiveTrades Component with Realtime**
  - [ ] Update `components/trades/active-trades.tsx`:
    ```typescript
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
          distanceToStopPercent: ((trade.entryPrice - trade.stopLossPrice) / trade.entryPrice) * 100,
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
              unrealizedPnlPercent: ((t.currentPrice - trade.entryPrice) / trade.entryPrice) * 100,
              distanceToStopPercent: ((t.currentPrice - trade.stopLossPrice) / t.currentPrice) * 100,
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
      const handlePriceUpdate = useCallback(({ assetId, lastPrice }: { assetId: string; lastPrice: number }) => {
        setTrades((prev) =>
          prev.map((trade) => {
            if (trade.assetId !== assetId) return trade;

            const unrealizedPnl = (lastPrice - trade.entryPrice) * trade.size;
            const unrealizedPnlPercent = ((lastPrice - trade.entryPrice) / trade.entryPrice) * 100;
            const distanceToStopPercent = ((lastPrice - trade.stopLossPrice) / lastPrice) * 100;
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
      }, []);

      // Get asset IDs from current trades for filtered price updates
      const tradeAssetIds = trades.map((t) => t.assetId);

      // Enable price listener for active trade assets
      useAssetPriceListener({
        onPriceUpdate: handlePriceUpdate,
        assetIds: tradeAssetIds.length > 0 ? tradeAssetIds : undefined,
      });

      // ... rest of component (loadTrades, summary stats, etc.) ...

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
          {/* Header with Realtime Status */}
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold text-zinc-100">Active Positions</h2>
                <Wifi className="h-4 w-4 text-emerald-500 animate-pulse" aria-label="Realtime connected" />
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
                    'text-lg font-bold font-mono transition-colors',
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
                    'text-lg font-bold font-mono transition-colors',
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

### Phase 7: Toast Notification Setup

- [ ] **Configure Sonner Toast Provider**
  - [ ] Update `app/layout.tsx`:
    ```typescript
    import { Inter, JetBrains_Mono } from 'next/font/google';
    import { Toaster } from '@/components/ui/sonner';
    import './globals.css';

    const inter = Inter({
      subsets: ['latin'],
      variable: '--font-inter',
    });

    const jetbrainsMono = JetBrains_Mono({
      subsets: ['latin'],
      variable: '--font-mono',
    });

    export default function RootLayout({
      children,
    }: {
      children: React.ReactNode;
    }) {
      return (
        <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable} dark`}>
          <body className="bg-zinc-950 text-zinc-100 antialiased">
            {children}
            <Toaster
              theme="dark"
              position="top-right"
              toastOptions={{
                style: {
                  background: '#18181b',  // zinc-900
                  border: '1px solid #27272a',  // zinc-800
                  color: '#f4f4f5',  // zinc-100
                },
              }}
            />
          </body>
        </html>
      );
    }
    ```

- [ ] **Create Custom Toast Styles**
  - [ ] Add to `app/globals.css`:
    ```css
    /* Sonner toast customizations */
    [data-sonner-toast][data-type="success"] [data-icon] {
      color: #10b981;  /* emerald-500 */
    }

    [data-sonner-toast][data-type="error"] [data-icon] {
      color: #f43f5e;  /* rose-500 */
    }

    [data-sonner-toast][data-type="warning"] [data-icon] {
      color: #f59e0b;  /* amber-500 */
    }

    [data-sonner-toast][data-type="info"] [data-icon] {
      color: #3b82f6;  /* blue-500 */
    }
    ```

### Phase 8: Connection Status Indicator

- [ ] **Create Realtime Status Hook**
  - [ ] Create `hooks/use-realtime-status.ts`:
    ```typescript
    'use client';

    import { useState, useEffect } from 'react';
    import { createClient } from '@/lib/supabase/client';

    export type RealtimeStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

    /**
     * Hook to track the overall Supabase Realtime connection status.
     */
    export function useRealtimeStatus(): RealtimeStatus {
      const [status, setStatus] = useState<RealtimeStatus>('connecting');

      useEffect(() => {
        const supabase = createClient();

        // Create a test channel to monitor connection status
        const channel = supabase
          .channel('connection-status')
          .subscribe((status) => {
            switch (status) {
              case 'SUBSCRIBED':
                setStatus('connected');
                break;
              case 'CLOSED':
              case 'TIMED_OUT':
                setStatus('disconnected');
                break;
              case 'CHANNEL_ERROR':
                setStatus('error');
                break;
              default:
                setStatus('connecting');
            }
          });

        return () => {
          supabase.removeChannel(channel);
        };
      }, []);

      return status;
    }
    ```

- [ ] **Create Connection Status Component**
  - [ ] Create `components/layout/realtime-status.tsx`:
    ```typescript
    'use client';

    import { Badge } from '@/components/ui/badge';
    import { Wifi, WifiOff, Loader2 } from 'lucide-react';
    import { cn } from '@/lib/utils';
    import { useRealtimeStatus, RealtimeStatus } from '@/hooks/use-realtime-status';

    export function RealtimeStatusIndicator() {
      const status = useRealtimeStatus();

      const config: Record<RealtimeStatus, { icon: React.ReactNode; text: string; className: string }> = {
        connecting: {
          icon: <Loader2 className="h-3 w-3 animate-spin" />,
          text: 'Connecting',
          className: 'border-amber-500/50 text-amber-500',
        },
        connected: {
          icon: <Wifi className="h-3 w-3" />,
          text: 'Live',
          className: 'border-emerald-500/50 text-emerald-500',
        },
        disconnected: {
          icon: <WifiOff className="h-3 w-3" />,
          text: 'Offline',
          className: 'border-rose-500/50 text-rose-500',
        },
        error: {
          icon: <WifiOff className="h-3 w-3" />,
          text: 'Error',
          className: 'border-rose-500/50 text-rose-500',
        },
      };

      const { icon, text, className } = config[status];

      return (
        <Badge
          variant="outline"
          className={cn('gap-1.5 text-xs', className)}
          aria-label={`Realtime connection: ${text}`}
        >
          {icon}
          {text}
        </Badge>
      );
    }
    ```

- [ ] **Add Status to TopBar**
  - [ ] Update `components/layout/top-bar.tsx` to include RealtimeStatusIndicator

### Phase 9: Testing & Verification

- [ ] **Create Realtime Testing Script**
  - [ ] Create `scripts/test-realtime.ts`:
    ```typescript
    #!/usr/bin/env ts-node
    /**
     * Script to test realtime by inserting records into Supabase.
     * Run while dashboard is open to verify updates appear.
     *
     * Usage: npx tsx scripts/test-realtime.ts
     */
    import { createClient } from '@supabase/supabase-js';

    const supabase = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_KEY!  // Service key for inserting
    );

    async function insertTestSession() {
      const { data, error } = await supabase
        .from('council_sessions')
        .insert({
          asset_id: 'test-asset-id',
          timestamp: new Date().toISOString(),
          sentiment_score: 15,
          technical_signal: 'BULLISH',
          technical_strength: 75,
          vision_confidence: 70,
          vision_valid: true,
          final_decision: 'BUY',
          decision_confidence: 85,
          reasoning_log: 'Test session for realtime verification',
        })
        .select()
        .single();

      if (error) {
        console.error('Error inserting session:', error);
      } else {
        console.log('Inserted session:', data);
      }
    }

    insertTestSession();
    ```

- [ ] **Manual Testing Checklist**
  - [ ] Open dashboard in browser
  - [ ] Verify "Live" indicator shows in header
  - [ ] Insert a council session via Supabase Table Editor
  - [ ] Verify new card appears at top of feed with animation
  - [ ] Verify toast notification appears for BUY/SELL signals
  - [ ] Insert a new trade via Table Editor
  - [ ] Verify trade card appears in Active Positions
  - [ ] Update trade status to STOPPED_OUT
  - [ ] Verify trade is removed from Active Positions
  - [ ] Verify toast notification for stop out
  - [ ] Update asset price
  - [ ] Verify P&L updates in trade card (if open trades exist)
  - [ ] Disconnect network briefly
  - [ ] Verify status indicator changes
  - [ ] Reconnect and verify updates resume

---

## Dev Notes

### Architecture Context

**Reference:** `docs/core/architecture.md` Section 2.3 (Frontend reads via Supabase)
**Reference:** `docs/core/uiux.md` Section 7 (Realtime Updates, Toasts)

Supabase Realtime uses WebSocket connections to push database changes to clients. The flow:

```
Python Bot (Railway)
    │
    ▼ INSERT/UPDATE
PostgreSQL (Supabase)
    │
    ▼ CDC (Change Data Capture)
Supabase Realtime Server
    │
    ▼ WebSocket push
Next.js Dashboard (Browser)
    │
    ▼ Update React state
UI Re-renders
```

### Technical Specifications

**Supabase Realtime Requirements:**
1. Tables must be added to the Realtime publication
2. Row Level Security (RLS) policies affect what changes clients can receive
3. Client must subscribe to specific table/event combinations
4. Channels should be cleaned up on component unmount

**WebSocket Payload Structure:**
```typescript
{
  eventType: 'INSERT' | 'UPDATE' | 'DELETE',
  new: Record<string, any>,  // New row data (INSERT/UPDATE)
  old: Record<string, any>,  // Old row data (UPDATE/DELETE)
  schema: 'public',
  table: 'council_sessions',
}
```

**Toast Types (Sonner):**
- `toast.success()` - Green icon, for BUY signals, profitable closes
- `toast.error()` - Red icon, for SELL signals, stop outs
- `toast.warning()` - Yellow icon, for warnings, losses
- `toast.info()` - Blue icon, for informational HOLD signals

### Implementation Guidance

**Cleanup Pattern (Critical):**
Always clean up subscriptions in useEffect return:
```typescript
useEffect(() => {
  const { unsubscribe } = subscribeToTable(...);
  return () => unsubscribe();  // CRITICAL: Prevent memory leaks
}, []);
```

**Callback Refs Pattern:**
Use refs for callbacks to avoid re-creating subscriptions:
```typescript
const callbackRef = useRef(callback);
useEffect(() => { callbackRef.current = callback; }, [callback]);
// Use callbackRef.current in subscription
```

**Duplicate Prevention:**
Always check for duplicates when adding realtime items:
```typescript
setSessions((prev) => {
  if (prev.some((s) => s.id === newSession.id)) return prev;
  return [newSession, ...prev];
});
```

### Accessibility Requirements

- Connection status must be announced to screen readers via aria-label
- Toast notifications should not be the only feedback mechanism
- Visual indicators (icon + text) for status changes
- Allow users to dismiss toasts

### Dependencies & Prerequisites

**Required Completions:**
- Story 4.1: Base layout and Supabase client setup
- Story 4.2: Council Feed component
- Story 4.3: Active Trades component
- Supabase Realtime enabled for tables

**Supabase Configuration:**
1. Enable Realtime in project settings
2. Add `council_sessions`, `trades`, `assets` to publication
3. Configure RLS policies for authenticated users

**Required Shadcn Components:**
- Sonner (installed in 4.1)
- Badge (installed in 4.1)

### Downstream Dependencies

- No direct downstream dependencies
- This completes the Epic 4 UI functionality

---

## Testing Strategy

### Unit Tests

- [ ] Test `subscribeToTable` creates proper channel
- [ ] Test `subscribeToTable` unsubscribe cleans up
- [ ] Test `useCouncilListener` transforms payloads correctly
- [ ] Test `useTradeListener` handles all event types
- [ ] Test `useAssetPriceListener` filters by asset IDs

### Integration Tests

- [ ] Test full flow: Insert record -> Receive in hook -> Update state
- [ ] Test reconnection after disconnect
- [ ] Test multiple subscriptions don't interfere

### Manual Testing Scenarios

1. Open dashboard, wait for "Live" indicator
2. Insert council session with BUY - verify card + toast
3. Insert council session with SELL - verify card + toast (red)
4. Insert trade - verify trade card appears
5. Update trade stop loss - verify card updates
6. Close trade (status = CLOSED) - verify card removed, toast shown
7. Update asset price - verify P&L updates in real-time
8. Disconnect WiFi - verify status changes to "Offline"
9. Reconnect - verify status returns to "Live"
10. Rapid inserts - verify no duplicates

### Acceptance Criteria Validation

- [ ] AC1: Dashboard subscribes to CouncilSession and Trade changes
- [ ] AC2: New council sessions appear at top without refresh
- [ ] AC3: Trade status changes reflect instantly
- [ ] AC4: Toast notifications appear for major events

---

## Technical Considerations

### Security

- Realtime respects RLS policies - users only see their data
- Subscription channels are isolated per client
- No sensitive data in toast messages

### Performance

- Limit number of active subscriptions (one per table type)
- Debounce rapid price updates if needed
- Use refs for callbacks to prevent re-subscriptions
- Clean up channels on unmount

### Scalability

- Supabase handles connection scaling
- Consider batch updates for high-frequency price changes
- May need worker for price aggregation at scale

### Edge Cases

- Initial load race condition: Handle if realtime update arrives before initial fetch
- Subscription failure: Show reconnect button, graceful degradation
- Invalid payload: Validate before updating state
- Duplicate events: Deduplicate by ID
- Tab switching: Consider pausing subscriptions for inactive tabs (future optimization)

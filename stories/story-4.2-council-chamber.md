# Story 4.2: The Council Chamber Feed

**Status:** Draft
**Epic:** 4 - Mission Control Dashboard (Next.js)
**Priority:** High

---

## Story

**As a** User,
**I want** to see a live chat-style feed of the AI Agents' deliberation,
**so that** I verify the reasoning behind every Buy/Hold/Sell decision.

---

## Acceptance Criteria

1. **Council Feed Component:** Fetches `CouncilSession` records from Supabase.
2. **Visualization:** Displays sessions as a vertical stream of cards.
    - Header: Asset + Timestamp + Decision.
    - Body: Collapsible details showing Sentiment Score, Tech Indicators, and the Reasoning Text.
3. **Visual Polish:** Use color coding (Green for Buy, Red for Sell, Grey for Hold).
4. **Performance:** Uses "Infinite Scroll" or simple Pagination to handle history.

---

## Tasks / Subtasks

### Phase 1: Database Types & Prisma Setup

- [ ] **Define TypeScript Types for CouncilSession**
  - [ ] Create `types/council.ts`:
    ```typescript
    export type DecisionType = 'BUY' | 'SELL' | 'HOLD';

    export interface CouncilSession {
      id: string;
      assetId: string;
      timestamp: Date;
      sentimentScore: number;        // 0-100 (lower = fear)
      technicalSignal: string;       // "BULLISH" | "BEARISH" | "NEUTRAL"
      technicalStrength: number;     // 0-100
      technicalDetails: string | null;  // JSON string
      visionAnalysis: string | null;
      visionConfidence: number;
      visionValid: boolean;
      finalDecision: DecisionType;
      decisionConfidence: number;
      reasoningLog: string;
      createdAt: Date;
      // Joined data
      asset?: {
        symbol: string;
        lastPrice: number;
      };
    }

    export interface TechnicalDetails {
      rsi: number | null;
      sma_50: number | null;
      sma_200: number | null;
      volume_delta: number | null;
      reasoning: string | null;
    }

    export interface CouncilFeedFilters {
      assetSymbol?: string;
      decision?: DecisionType;
      limit?: number;
      cursor?: string;  // For cursor-based pagination
    }
    ```

- [ ] **Verify Prisma Schema Includes CouncilSession**
  - [ ] Check `packages/database/prisma/schema.prisma` has `CouncilSession` model
  - [ ] Ensure `Asset` relation exists for joins
  - [ ] Run `pnpm db:generate` if schema updated

### Phase 2: Data Fetching Layer

- [ ] **Create Server Action for Fetching Council Sessions**
  - [ ] Create `app/dashboard/council/actions.ts`:
    ```typescript
    'use server';

    import { createClient } from '@/lib/supabase/server';
    import { CouncilSession, CouncilFeedFilters } from '@/types/council';

    const PAGE_SIZE = 20;

    export async function fetchCouncilSessions(
      filters: CouncilFeedFilters = {}
    ): Promise<{
      sessions: CouncilSession[];
      nextCursor: string | null;
      hasMore: boolean;
    }> {
      const supabase = await createClient();
      const limit = filters.limit || PAGE_SIZE;

      let query = supabase
        .from('council_sessions')
        .select(`
          *,
          asset:assets (
            symbol,
            lastPrice:last_price
          )
        `)
        .order('timestamp', { ascending: false })
        .limit(limit + 1);  // Fetch one extra to check if more exist

      // Apply cursor-based pagination
      if (filters.cursor) {
        query = query.lt('timestamp', filters.cursor);
      }

      // Apply filters
      if (filters.assetSymbol) {
        query = query.eq('asset.symbol', filters.assetSymbol);
      }

      if (filters.decision) {
        query = query.eq('final_decision', filters.decision);
      }

      const { data, error } = await query;

      if (error) {
        console.error('Error fetching council sessions:', error);
        throw new Error('Failed to fetch council sessions');
      }

      const hasMore = data.length > limit;
      const sessions = hasMore ? data.slice(0, limit) : data;
      const nextCursor = hasMore ? sessions[sessions.length - 1]?.timestamp : null;

      // Transform snake_case to camelCase
      const transformedSessions: CouncilSession[] = sessions.map((s: any) => ({
        id: s.id,
        assetId: s.asset_id,
        timestamp: new Date(s.timestamp),
        sentimentScore: s.sentiment_score,
        technicalSignal: s.technical_signal,
        technicalStrength: s.technical_strength,
        technicalDetails: s.technical_details,
        visionAnalysis: s.vision_analysis,
        visionConfidence: s.vision_confidence,
        visionValid: s.vision_valid,
        finalDecision: s.final_decision,
        decisionConfidence: s.decision_confidence,
        reasoningLog: s.reasoning_log,
        createdAt: new Date(s.created_at),
        asset: s.asset ? {
          symbol: s.asset.symbol,
          lastPrice: s.asset.lastPrice,
        } : undefined,
      }));

      return {
        sessions: transformedSessions,
        nextCursor,
        hasMore,
      };
    }

    export async function fetchLatestSession(
      assetId?: string
    ): Promise<CouncilSession | null> {
      const supabase = await createClient();

      let query = supabase
        .from('council_sessions')
        .select(`
          *,
          asset:assets (
            symbol,
            lastPrice:last_price
          )
        `)
        .order('timestamp', { ascending: false })
        .limit(1);

      if (assetId) {
        query = query.eq('asset_id', assetId);
      }

      const { data, error } = await query.single();

      if (error || !data) {
        return null;
      }

      // Transform to camelCase (same as above)
      return {
        id: data.id,
        assetId: data.asset_id,
        timestamp: new Date(data.timestamp),
        sentimentScore: data.sentiment_score,
        technicalSignal: data.technical_signal,
        technicalStrength: data.technical_strength,
        technicalDetails: data.technical_details,
        visionAnalysis: data.vision_analysis,
        visionConfidence: data.vision_confidence,
        visionValid: data.vision_valid,
        finalDecision: data.final_decision,
        decisionConfidence: data.decision_confidence,
        reasoningLog: data.reasoning_log,
        createdAt: new Date(data.created_at),
        asset: data.asset ? {
          symbol: data.asset.symbol,
          lastPrice: data.asset.lastPrice,
        } : undefined,
      };
    }
    ```

### Phase 3: Council Card Component

- [ ] **Create Decision Badge Component**
  - [ ] Create `components/council/decision-badge.tsx`:
    ```typescript
    import { Badge } from '@/components/ui/badge';
    import { cn } from '@/lib/utils';
    import { DecisionType } from '@/types/council';

    interface DecisionBadgeProps {
      decision: DecisionType;
      confidence?: number;
      className?: string;
    }

    const decisionStyles: Record<DecisionType, string> = {
      BUY: 'bg-emerald-500/20 text-emerald-500 border-emerald-500/50',
      SELL: 'bg-rose-500/20 text-rose-500 border-rose-500/50',
      HOLD: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/50',
    };

    export function DecisionBadge({
      decision,
      confidence,
      className,
    }: DecisionBadgeProps) {
      return (
        <Badge
          variant="outline"
          className={cn(decisionStyles[decision], className)}
        >
          {decision}
          {confidence !== undefined && (
            <span className="ml-1 opacity-70">({confidence}%)</span>
          )}
        </Badge>
      );
    }
    ```

- [ ] **Create Sentiment Score Indicator**
  - [ ] Create `components/council/sentiment-indicator.tsx`:
    ```typescript
    import { cn } from '@/lib/utils';
    import { Twitter } from 'lucide-react';

    interface SentimentIndicatorProps {
      score: number;  // 0-100 (0 = extreme fear, 100 = extreme greed)
      className?: string;
    }

    export function SentimentIndicator({ score, className }: SentimentIndicatorProps) {
      // Determine sentiment label
      const getLabel = (s: number): string => {
        if (s < 20) return 'Extreme Fear';
        if (s < 40) return 'Fear';
        if (s < 60) return 'Neutral';
        if (s < 80) return 'Greed';
        return 'Extreme Greed';
      };

      // Color based on fear (green for fear = buying opportunity)
      const getColor = (s: number): string => {
        if (s < 20) return 'bg-emerald-500';
        if (s < 40) return 'bg-emerald-400';
        if (s < 60) return 'bg-zinc-400';
        if (s < 80) return 'bg-rose-400';
        return 'bg-rose-500';
      };

      return (
        <div className={cn('space-y-2', className)}>
          <div className="flex items-center gap-2">
            <Twitter className="h-4 w-4 text-zinc-400" />
            <span className="text-sm text-zinc-400">Sentiment</span>
            <span className="ml-auto font-mono text-sm text-zinc-100">
              {score}/100
            </span>
          </div>
          <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className={cn('h-full transition-all', getColor(score))}
              style={{ width: `${score}%` }}
              role="progressbar"
              aria-valuenow={score}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`Sentiment score: ${score} - ${getLabel(score)}`}
            />
          </div>
          <span className="text-xs text-zinc-500">{getLabel(score)}</span>
        </div>
      );
    }
    ```

- [ ] **Create Technical Signal Display**
  - [ ] Create `components/council/technical-display.tsx`:
    ```typescript
    import { cn } from '@/lib/utils';
    import { TrendingUp, TrendingDown, Minus, BarChart3 } from 'lucide-react';
    import { TechnicalDetails } from '@/types/council';

    interface TechnicalDisplayProps {
      signal: string;
      strength: number;
      details: TechnicalDetails | null;
      className?: string;
    }

    export function TechnicalDisplay({
      signal,
      strength,
      details,
      className,
    }: TechnicalDisplayProps) {
      const SignalIcon = signal === 'BULLISH'
        ? TrendingUp
        : signal === 'BEARISH'
        ? TrendingDown
        : Minus;

      const signalColor = signal === 'BULLISH'
        ? 'text-emerald-500'
        : signal === 'BEARISH'
        ? 'text-rose-500'
        : 'text-zinc-400';

      return (
        <div className={cn('space-y-3', className)}>
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-zinc-400" />
            <span className="text-sm text-zinc-400">Technical</span>
            <div className={cn('flex items-center gap-1 ml-auto', signalColor)}>
              <SignalIcon className="h-4 w-4" />
              <span className="font-mono text-sm">{signal}</span>
            </div>
          </div>

          {/* Strength bar */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs">
              <span className="text-zinc-500">Strength</span>
              <span className="font-mono text-zinc-400">{strength}%</span>
            </div>
            <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
              <div
                className={cn(
                  'h-full transition-all',
                  signal === 'BULLISH' ? 'bg-emerald-500' :
                  signal === 'BEARISH' ? 'bg-rose-500' : 'bg-zinc-500'
                )}
                style={{ width: `${strength}%` }}
              />
            </div>
          </div>

          {/* Technical details */}
          {details && (
            <div className="grid grid-cols-2 gap-2 text-xs font-mono">
              {details.rsi !== null && (
                <div className="flex justify-between">
                  <span className="text-zinc-500">RSI:</span>
                  <span className={cn(
                    details.rsi < 30 ? 'text-emerald-500' :
                    details.rsi > 70 ? 'text-rose-500' : 'text-zinc-100'
                  )}>
                    {details.rsi.toFixed(1)}
                  </span>
                </div>
              )}
              {details.sma_50 !== null && (
                <div className="flex justify-between">
                  <span className="text-zinc-500">SMA50:</span>
                  <span className="text-zinc-100">${details.sma_50.toFixed(2)}</span>
                </div>
              )}
              {details.sma_200 !== null && (
                <div className="flex justify-between">
                  <span className="text-zinc-500">SMA200:</span>
                  <span className="text-zinc-100">${details.sma_200.toFixed(2)}</span>
                </div>
              )}
              {details.volume_delta !== null && (
                <div className="flex justify-between">
                  <span className="text-zinc-500">Vol Delta:</span>
                  <span className={cn(
                    details.volume_delta > 0 ? 'text-emerald-500' : 'text-rose-500'
                  )}>
                    {details.volume_delta > 0 ? '+' : ''}{details.volume_delta.toFixed(1)}%
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      );
    }
    ```

- [ ] **Create Vision Analysis Display**
  - [ ] Create `components/council/vision-display.tsx`:
    ```typescript
    import { cn } from '@/lib/utils';
    import { Eye, CheckCircle, XCircle } from 'lucide-react';

    interface VisionDisplayProps {
      analysis: string | null;
      confidence: number;
      isValid: boolean;
      className?: string;
    }

    export function VisionDisplay({
      analysis,
      confidence,
      isValid,
      className,
    }: VisionDisplayProps) {
      return (
        <div className={cn('space-y-2', className)}>
          <div className="flex items-center gap-2">
            <Eye className="h-4 w-4 text-zinc-400" />
            <span className="text-sm text-zinc-400">Chart Vision</span>
            <div className="flex items-center gap-1 ml-auto">
              {isValid ? (
                <CheckCircle className="h-4 w-4 text-emerald-500" />
              ) : (
                <XCircle className="h-4 w-4 text-rose-500" />
              )}
              <span className={cn(
                'text-xs font-mono',
                isValid ? 'text-emerald-500' : 'text-rose-500'
              )}>
                {isValid ? 'Valid' : 'Invalid'}
              </span>
            </div>
          </div>

          <div className="flex justify-between text-xs">
            <span className="text-zinc-500">Confidence</span>
            <span className="font-mono text-zinc-400">{confidence}%</span>
          </div>

          {analysis && (
            <p className="text-xs text-zinc-400 leading-relaxed">
              {analysis}
            </p>
          )}
        </div>
      );
    }
    ```

- [ ] **Create Main Council Card Component**
  - [ ] Create `components/council/council-card.tsx`:
    ```typescript
    'use client';

    import { useState } from 'react';
    import { formatDistanceToNow, format } from 'date-fns';
    import { Card, CardContent, CardHeader } from '@/components/ui/card';
    import {
      Accordion,
      AccordionContent,
      AccordionItem,
      AccordionTrigger,
    } from '@/components/ui/accordion';
    import { Separator } from '@/components/ui/separator';
    import { cn } from '@/lib/utils';
    import { CouncilSession, TechnicalDetails } from '@/types/council';
    import { DecisionBadge } from './decision-badge';
    import { SentimentIndicator } from './sentiment-indicator';
    import { TechnicalDisplay } from './technical-display';
    import { VisionDisplay } from './vision-display';

    interface CouncilCardProps {
      session: CouncilSession;
      isNew?: boolean;  // For animation on realtime updates
      className?: string;
    }

    export function CouncilCard({ session, isNew, className }: CouncilCardProps) {
      const [isExpanded, setIsExpanded] = useState(false);

      // Parse technical details JSON
      const technicalDetails: TechnicalDetails | null = session.technicalDetails
        ? JSON.parse(session.technicalDetails)
        : null;

      // Border color based on decision
      const borderColor = {
        BUY: 'border-l-emerald-500',
        SELL: 'border-l-rose-500',
        HOLD: 'border-l-zinc-500',
      }[session.finalDecision];

      return (
        <Card
          className={cn(
            'bg-zinc-900 border-zinc-800 border-l-4 transition-all duration-300',
            borderColor,
            isNew && 'animate-slide-in-from-top',
            className
          )}
        >
          <CardHeader className="p-4 pb-2">
            {/* Header: Asset + Time + Decision */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="font-semibold text-zinc-100 font-mono">
                  {session.asset?.symbol || session.assetId}
                </span>
                <time
                  dateTime={session.timestamp.toISOString()}
                  className="text-xs text-zinc-500"
                  title={format(session.timestamp, 'PPpp')}
                >
                  {formatDistanceToNow(session.timestamp, { addSuffix: true })}
                </time>
              </div>
              <DecisionBadge
                decision={session.finalDecision}
                confidence={session.decisionConfidence}
              />
            </div>
          </CardHeader>

          <CardContent className="p-4 pt-0">
            {/* Master Node Reasoning Summary */}
            <p className="text-sm text-zinc-300 leading-relaxed mb-4 font-mono">
              {session.reasoningLog.length > 200
                ? `${session.reasoningLog.slice(0, 200)}...`
                : session.reasoningLog}
            </p>

            {/* Expandable Agent Details */}
            <Accordion
              type="single"
              collapsible
              value={isExpanded ? 'details' : ''}
              onValueChange={(v) => setIsExpanded(v === 'details')}
            >
              <AccordionItem value="details" className="border-zinc-800">
                <AccordionTrigger className="text-sm text-zinc-400 hover:text-zinc-100 py-2">
                  Agent Analysis Details
                </AccordionTrigger>
                <AccordionContent className="space-y-4 pt-2">
                  {/* Sentiment Analysis */}
                  <SentimentIndicator score={session.sentimentScore} />

                  <Separator className="bg-zinc-800" />

                  {/* Technical Analysis */}
                  <TechnicalDisplay
                    signal={session.technicalSignal}
                    strength={session.technicalStrength}
                    details={technicalDetails}
                  />

                  <Separator className="bg-zinc-800" />

                  {/* Vision Analysis */}
                  <VisionDisplay
                    analysis={session.visionAnalysis}
                    confidence={session.visionConfidence}
                    isValid={session.visionValid}
                  />

                  {/* Full Reasoning Log (if long) */}
                  {session.reasoningLog.length > 200 && (
                    <>
                      <Separator className="bg-zinc-800" />
                      <div className="space-y-2">
                        <span className="text-sm text-zinc-400">Full Reasoning</span>
                        <pre className="text-xs text-zinc-300 font-mono whitespace-pre-wrap bg-zinc-950 p-3 rounded-md max-h-48 overflow-y-auto">
                          {session.reasoningLog}
                        </pre>
                      </div>
                    </>
                  )}
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </CardContent>
        </Card>
      );
    }
    ```

### Phase 4: Council Feed Component

- [ ] **Create Infinite Scroll Hook**
  - [ ] Create `hooks/use-infinite-scroll.ts`:
    ```typescript
    'use client';

    import { useEffect, useRef, useCallback } from 'react';

    interface UseInfiniteScrollOptions {
      onLoadMore: () => void;
      hasMore: boolean;
      isLoading: boolean;
      threshold?: number;  // Distance from bottom in pixels
    }

    export function useInfiniteScroll({
      onLoadMore,
      hasMore,
      isLoading,
      threshold = 200,
    }: UseInfiniteScrollOptions) {
      const observerRef = useRef<IntersectionObserver | null>(null);
      const loadMoreRef = useRef<HTMLDivElement | null>(null);

      const handleObserver = useCallback(
        (entries: IntersectionObserverEntry[]) => {
          const [target] = entries;
          if (target.isIntersecting && hasMore && !isLoading) {
            onLoadMore();
          }
        },
        [onLoadMore, hasMore, isLoading]
      );

      useEffect(() => {
        const element = loadMoreRef.current;
        if (!element) return;

        observerRef.current = new IntersectionObserver(handleObserver, {
          root: null,
          rootMargin: `${threshold}px`,
          threshold: 0,
        });

        observerRef.current.observe(element);

        return () => {
          if (observerRef.current) {
            observerRef.current.disconnect();
          }
        };
      }, [handleObserver, threshold]);

      return { loadMoreRef };
    }
    ```

- [ ] **Create Council Feed Container**
  - [ ] Create `components/council/council-feed.tsx`:
    ```typescript
    'use client';

    import { useState, useEffect, useCallback } from 'react';
    import { ScrollArea } from '@/components/ui/scroll-area';
    import { Skeleton } from '@/components/ui/skeleton';
    import { Button } from '@/components/ui/button';
    import { RefreshCw, Filter } from 'lucide-react';
    import { cn } from '@/lib/utils';
    import { CouncilSession, CouncilFeedFilters, DecisionType } from '@/types/council';
    import { fetchCouncilSessions } from '@/app/dashboard/council/actions';
    import { CouncilCard } from './council-card';
    import { useInfiniteScroll } from '@/hooks/use-infinite-scroll';

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

      // Trigger reload when filter changes
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
          {/* Header */}
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-zinc-100">Council Chamber</h2>
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
                <CouncilCard key={session.id} session={session} />
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

### Phase 5: Page Integration

- [ ] **Create Council Page**
  - [ ] Create `app/dashboard/council/page.tsx`:
    ```typescript
    import { Metadata } from 'next';
    import { CouncilFeed } from '@/components/council/council-feed';
    import { fetchCouncilSessions } from './actions';

    export const metadata: Metadata = {
      title: 'Council Chamber | ContrarianAI',
      description: 'View AI Council deliberations and trading decisions',
    };

    export default async function CouncilPage() {
      // Server-side initial fetch
      const { sessions } = await fetchCouncilSessions({ limit: 20 });

      return (
        <div className="h-[calc(100vh-8rem)]">
          <CouncilFeed initialSessions={sessions} />
        </div>
      );
    }
    ```

- [ ] **Integrate Feed into Dashboard Overview**
  - [ ] Update `app/dashboard/page.tsx` to include CouncilFeed:
    ```typescript
    import { Metadata } from 'next';
    import { CouncilFeed } from '@/components/council/council-feed';
    import { fetchCouncilSessions } from './council/actions';

    export const metadata: Metadata = {
      title: 'Dashboard | ContrarianAI',
      description: 'ContrarianAI Mission Control Dashboard',
    };

    export default async function DashboardPage() {
      const { sessions } = await fetchCouncilSessions({ limit: 10 });

      return (
        <div className="space-y-6">
          <h1 className="text-2xl font-bold text-zinc-100">Mission Control</h1>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            {/* Council Feed - 40% */}
            <div className="lg:col-span-5 bg-zinc-900 rounded-lg border border-zinc-800 p-4 h-[600px]">
              <CouncilFeed initialSessions={sessions} />
            </div>

            {/* Active Trades - 35% (Story 4.3) */}
            <div className="lg:col-span-4 bg-zinc-900 rounded-lg border border-zinc-800 p-4 min-h-[400px]">
              <h2 className="text-lg font-semibold text-zinc-100 mb-4">Active Positions</h2>
              <p className="text-zinc-400 text-sm">Trade cards will be implemented in Story 4.3</p>
            </div>

            {/* Scanner - 25% (Story 4.3) */}
            <div className="lg:col-span-3 bg-zinc-900 rounded-lg border border-zinc-800 p-4 min-h-[400px]">
              <h2 className="text-lg font-semibold text-zinc-100 mb-4">Market Scanner</h2>
              <p className="text-zinc-400 text-sm">Scanner table will be implemented in Story 4.3</p>
            </div>
          </div>
        </div>
      );
    }
    ```

### Phase 6: Animation & Polish

- [ ] **Add CSS Animation for New Cards**
  - [ ] Add to `app/globals.css`:
    ```css
    @keyframes slide-in-from-top {
      from {
        opacity: 0;
        transform: translateY(-20px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    .animate-slide-in-from-top {
      animation: slide-in-from-top 0.3s ease-out;
    }
    ```

- [ ] **Install date-fns for Time Formatting**
  - [ ] Run `pnpm add date-fns`
  - [ ] Verify import works in CouncilCard

### Phase 7: Testing & Verification

- [ ] **Create Test Data Script**
  - [ ] Create `scripts/seed-council-sessions.ts` for testing:
    ```typescript
    // Script to insert test CouncilSession records via Supabase
    // Run with: npx tsx scripts/seed-council-sessions.ts
    ```

- [ ] **Manual Testing Checklist**
  - [ ] Navigate to `/dashboard/council`
  - [ ] Verify sessions load with proper styling
  - [ ] Verify BUY sessions have green left border
  - [ ] Verify SELL sessions have red left border
  - [ ] Verify HOLD sessions have grey left border
  - [ ] Click accordion to expand agent details
  - [ ] Verify sentiment progress bar displays correctly
  - [ ] Verify technical indicators display with correct colors
  - [ ] Verify infinite scroll loads more sessions
  - [ ] Verify filter buttons work (All/Buy/Sell)
  - [ ] Verify refresh button reloads data
  - [ ] Verify empty state displays when no sessions exist
  - [ ] Test on mobile viewport - verify stacked layout

---

## Dev Notes

### Architecture Context

**Reference:** `docs/core/architecture.md` Section 6.2 (CouncilFeed Component)
**Reference:** `docs/core/uiux.md` Section 6.1 (Council Session Card)

This is the "killer feature" of the UI - the component that visualizes the AI's decision-making process. Users should be able to:
1. Quickly scan recent decisions (BUY/SELL/HOLD at a glance)
2. Deep-dive into any specific decision to understand the reasoning
3. Filter to see only actionable signals (BUY/SELL)

**Database Query Pattern:**
```sql
SELECT cs.*, a.symbol, a.last_price
FROM council_sessions cs
JOIN assets a ON cs.asset_id = a.id
ORDER BY cs.timestamp DESC
LIMIT 20
```

### Technical Specifications

**Card Color Coding (from uiux.md):**
| Decision | Left Border | Badge Style |
|----------|-------------|-------------|
| BUY | `border-l-emerald-500` | `bg-emerald-500/20 text-emerald-500` |
| SELL | `border-l-rose-500` | `bg-rose-500/20 text-rose-500` |
| HOLD | `border-l-zinc-500` | `bg-zinc-500/20 text-zinc-400` |

**Sentiment Score Interpretation:**
- 0-20: Extreme Fear (Green - buying opportunity)
- 20-40: Fear
- 40-60: Neutral
- 60-80: Greed
- 80-100: Extreme Greed (Red - selling opportunity)

**Typography:**
- Asset symbol: `font-mono font-semibold`
- Reasoning text: `font-mono text-sm`
- Technical data: `font-mono text-xs`
- All numerical values: `font-mono`

### Implementation Guidance

**Performance Optimization:**
- Use cursor-based pagination (timestamp as cursor)
- Limit initial load to 20 sessions
- Lazy-load expanded content (accordion)
- Use `React.memo` on CouncilCard if re-renders are frequent

**Server Actions vs API Routes:**
Server Actions are preferred for data fetching because:
- Direct database access without HTTP overhead
- Automatic request deduplication
- Better TypeScript inference
- Easier caching with `revalidatePath`

**Accessibility:**
- Progress bars must have `role="progressbar"` and aria attributes
- Time elements should use `datetime` attribute
- Accordion should be keyboard navigable
- Color should not be the only indicator (use icons too)

### Dependencies & Prerequisites

**Required Completions:**
- Story 4.1: Layout, authentication, Shadcn components
- Story 1.2: Database schema with CouncilSession table
- Story 2.4: CouncilSession records being written by bot

**Required Shadcn Components:**
- Card (installed in 4.1)
- Accordion (installed in 4.1)
- Badge (installed in 4.1)
- ScrollArea (installed in 4.1)
- Skeleton (installed in 4.1)
- Button (installed in 4.1)
- Separator (installed in 4.1)

**Additional Dependencies:**
- `date-fns` for time formatting
- `lucide-react` for icons (installed in 4.1)

### Downstream Dependencies

- **Story 4.4**: Will add realtime subscription to auto-update feed

---

## Testing Strategy

### Unit Tests

- [ ] Test `DecisionBadge` renders correct styles for each decision
- [ ] Test `SentimentIndicator` renders correct color for each range
- [ ] Test `TechnicalDisplay` handles null details gracefully
- [ ] Test `CouncilCard` expands/collapses accordion
- [ ] Test `useInfiniteScroll` triggers callback at threshold

### Integration Tests

- [ ] Test `fetchCouncilSessions` returns correct structure
- [ ] Test pagination cursor works correctly
- [ ] Test filter query parameters are applied

### Manual Testing Scenarios

1. Fresh load - verify 20 sessions load
2. Scroll to bottom - verify more sessions load
3. Click BUY filter - verify only BUY sessions shown
4. Expand a card - verify all agent details display
5. Check on mobile - verify cards are readable
6. Check empty database - verify empty state displays

### Acceptance Criteria Validation

- [ ] AC1: Feed fetches CouncilSession records with Asset join
- [ ] AC2a: Sessions display as vertical card stream
- [ ] AC2b: Header shows Asset + Timestamp + Decision
- [ ] AC2c: Accordion expands to show Sentiment, Technical, Vision
- [ ] AC3: Green/Red/Grey color coding applied correctly
- [ ] AC4: Infinite scroll loads more sessions on scroll

---

## Technical Considerations

### Security

- Server Actions run on server - no client-side SQL
- Row-Level Security (RLS) can be applied in Supabase
- Filter inputs are type-safe (DecisionType enum)

### Performance

- Initial SSR load for SEO and fast first paint
- Intersection Observer for efficient scroll detection
- Limit expanded content to reduce DOM size
- Consider virtualization for very long lists (future)

### Edge Cases

- Empty database: Show helpful empty state
- Network error: Display error message with retry
- Invalid JSON in technicalDetails: Handle parse error gracefully
- Very long reasoningLog: Truncate with "show more"
- Missing asset relation: Fallback to asset_id display

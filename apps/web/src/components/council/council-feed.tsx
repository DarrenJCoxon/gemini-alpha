'use client';

import { useState, useEffect, useCallback } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { RefreshCw, Wifi } from 'lucide-react';
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

export function CouncilFeed({
  initialSessions = [],
  className,
}: CouncilFeedProps) {
  const [sessions, setSessions] = useState<CouncilSession[]>(initialSessions);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [cursor, setCursor] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<DecisionType | null>(null);
  const [newSessionIds, setNewSessionIds] = useState<Set<string>>(new Set());

  // Realtime listener for new sessions
  const handleNewSession = useCallback(
    (session: CouncilSession) => {
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
    },
    [filter]
  );

  // Enable realtime listener
  useCouncilListener({
    onNewSession: handleNewSession,
    showToasts: true,
  });

  // Fetch sessions
  const loadSessions = useCallback(
    async (reset = false) => {
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
    },
    [cursor, filter, isLoading]
  );

  // Fetch initial data if not provided
  useEffect(() => {
    if (initialSessions.length === 0) {
      loadSessions(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Reload when filter changes
  useEffect(() => {
    setSessions([]);
    setCursor(null);
    setHasMore(true);
    loadSessions(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    setCursor(null);
    await loadSessions(true);
    setIsRefreshing(false);
  };

  const handleFilterChange = (newFilter: DecisionType | null) => {
    if (newFilter === filter) return;
    setFilter(newFilter);
  };

  const { loadMoreRef } = useInfiniteScroll({
    onLoadMore: () => loadSessions(false),
    hasMore,
    isLoading,
  });

  return (
    <div className={cn('flex flex-col h-full', className)} data-testid="council-feed">
      {/* Header with Realtime Status */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-zinc-100">Council Chamber</h2>
          <Wifi
            className="h-4 w-4 text-emerald-500 animate-pulse"
            aria-label="Realtime connected"
            data-testid="realtime-indicator"
          />
        </div>
        <div className="flex items-center gap-2">
          {/* Filter buttons */}
          <div className="flex gap-1" role="group" aria-label="Filter by decision">
            <Button
              size="sm"
              variant={filter === null ? 'secondary' : 'ghost'}
              onClick={() => handleFilterChange(null)}
              className="text-xs h-7"
              data-testid="filter-all"
            >
              All
            </Button>
            <Button
              size="sm"
              variant={filter === 'BUY' ? 'secondary' : 'ghost'}
              onClick={() => handleFilterChange('BUY')}
              className="text-xs h-7 text-emerald-500"
              data-testid="filter-buy"
            >
              Buy
            </Button>
            <Button
              size="sm"
              variant={filter === 'SELL' ? 'secondary' : 'ghost'}
              onClick={() => handleFilterChange('SELL')}
              className="text-xs h-7 text-rose-500"
              data-testid="filter-sell"
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
            aria-label="Refresh feed"
            data-testid="refresh-button"
          >
            <RefreshCw
              className={cn('h-4 w-4', isRefreshing && 'animate-spin')}
              aria-hidden="true"
            />
          </Button>
        </div>
      </div>

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
          {hasMore && <div ref={loadMoreRef} className="h-4" aria-hidden="true" />}

          {/* Empty state */}
          {!isLoading && sessions.length === 0 && (
            <div
              className="text-center py-12 text-zinc-500"
              data-testid="empty-state"
            >
              <p>No council sessions found</p>
              <p className="text-sm mt-2">
                Sessions will appear here when the bot makes decisions
              </p>
            </div>
          )}

          {/* End of list */}
          {!hasMore && sessions.length > 0 && (
            <p
              className="text-center text-zinc-500 text-sm py-4"
              data-testid="end-of-list"
            >
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
    <div
      className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 space-y-3"
      data-testid="council-card-skeleton"
    >
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

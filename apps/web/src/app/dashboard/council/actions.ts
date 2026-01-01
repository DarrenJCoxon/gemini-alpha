'use server';

import { createClient } from '@/lib/supabase/server';
import {
  CouncilSession,
  CouncilFeedFilters,
  CouncilFeedResult,
} from '@/types/council';

const PAGE_SIZE = 20;

/**
 * Transforms raw Supabase data to camelCase CouncilSession
 */
function transformSession(raw: Record<string, unknown>): CouncilSession {
  return {
    id: raw.id as string,
    assetId: raw.asset_id as string,
    timestamp: new Date(raw.timestamp as string),
    sentimentScore: raw.sentiment_score as number,
    technicalSignal: raw.technical_signal as string,
    technicalStrength: raw.technical_strength as number,
    technicalDetails: raw.technical_details as string | null,
    visionAnalysis: raw.vision_analysis as string | null,
    visionConfidence: Number(raw.vision_confidence ?? 0),
    visionValid: raw.vision_valid as boolean,
    finalDecision: raw.final_decision as 'BUY' | 'SELL' | 'HOLD',
    decisionConfidence: raw.decision_confidence as number,
    reasoningLog: raw.reasoning_log as string,
    createdAt: new Date(raw.created_at as string),
    asset: raw.asset
      ? {
          symbol: (raw.asset as Record<string, unknown>).symbol as string,
          lastPrice: Number(
            (raw.asset as Record<string, unknown>).last_price ?? 0
          ),
        }
      : undefined,
  };
}

/**
 * Fetches council sessions with cursor-based pagination and optional filters
 */
export async function fetchCouncilSessions(
  filters: CouncilFeedFilters = {}
): Promise<CouncilFeedResult> {
  const supabase = await createClient();
  const limit = filters.limit || PAGE_SIZE;

  let query = supabase
    .from('council_sessions')
    .select(
      `
      *,
      asset:assets (
        symbol,
        last_price
      )
    `
    )
    .order('timestamp', { ascending: false })
    .limit(limit + 1); // Fetch one extra to check if more exist

  // Apply cursor-based pagination
  if (filters.cursor) {
    query = query.lt('timestamp', filters.cursor);
  }

  // Apply decision filter
  if (filters.decision) {
    query = query.eq('final_decision', filters.decision);
  }

  const { data, error } = await query;

  if (error) {
    console.error('Error fetching council sessions:', error);
    throw new Error('Failed to fetch council sessions');
  }

  const hasMore = (data?.length ?? 0) > limit;
  const sessions = hasMore ? (data ?? []).slice(0, limit) : (data ?? []);
  const nextCursor = hasMore
    ? (sessions[sessions.length - 1]?.timestamp as string | null)
    : null;

  const transformedSessions: CouncilSession[] = sessions.map((s) =>
    transformSession(s as Record<string, unknown>)
  );

  return {
    sessions: transformedSessions,
    nextCursor,
    hasMore,
  };
}

/**
 * Fetches the latest council session, optionally for a specific asset
 */
export async function fetchLatestSession(
  assetId?: string
): Promise<CouncilSession | null> {
  const supabase = await createClient();

  let query = supabase
    .from('council_sessions')
    .select(
      `
      *,
      asset:assets (
        symbol,
        last_price
      )
    `
    )
    .order('timestamp', { ascending: false })
    .limit(1);

  if (assetId) {
    query = query.eq('asset_id', assetId);
  }

  const { data, error } = await query.single();

  if (error || !data) {
    return null;
  }

  return transformSession(data as Record<string, unknown>);
}

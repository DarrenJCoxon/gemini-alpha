/**
 * Council Session Types
 * Types for AI council deliberation and decision data
 */

export type DecisionType = 'BUY' | 'SELL' | 'HOLD';

export interface CouncilSession {
  id: string;
  assetId: string;
  timestamp: Date;
  sentimentScore: number; // 0-100 (lower = fear)
  technicalSignal: string; // "BULLISH" | "BEARISH" | "NEUTRAL"
  technicalStrength: number; // 0-100
  technicalDetails: string | null; // JSON string
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
  cursor?: string; // For cursor-based pagination
}

export interface CouncilFeedResult {
  sessions: CouncilSession[];
  nextCursor: string | null;
  hasMore: boolean;
}

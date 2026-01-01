/**
 * Scanner Types
 * Types for market scanning and asset discovery
 */

export interface ScannerAsset {
  id: string;
  symbol: string;
  lastPrice: number;
  priceChange15m: number; // Percentage change
  sentimentScore: number | null; // From latest council session
  technicalSignal: string | null; // "BULLISH" | "BEARISH" | "NEUTRAL"
  technicalStrength: number | null;
  lastSessionTime: Date | null;
}

export type SortField = 'symbol' | 'lastPrice' | 'sentimentScore' | 'technicalSignal';
export type SortDirection = 'asc' | 'desc';

export interface ScannerFilters {
  sortBy?: SortField;
  sortDirection?: SortDirection;
  limit?: number;
}

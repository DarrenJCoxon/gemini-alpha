/**
 * Shared TypeScript Interfaces for Contrarian AI
 *
 * This package contains type definitions shared between
 * the Next.js frontend and other TypeScript packages.
 */

// API Response types
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

// Health check response
export interface HealthCheckResponse {
  status: "healthy" | "unhealthy";
  timestamp: string;
}

// Trading related types (to be expanded in future stories)
export interface TradingPair {
  base: string;
  quote: string;
  symbol: string;
}

// Sentiment analysis types (to be expanded in Story 1.4)
export interface SentimentData {
  symbol: string;
  score: number;
  source: string;
  timestamp: Date;
}

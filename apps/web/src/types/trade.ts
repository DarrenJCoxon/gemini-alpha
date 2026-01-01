/**
 * Trade Types
 * Types for trading positions and P&L tracking
 */

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
  pnl: number | null; // Realized P&L (after close)
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
  unrealizedPnl: number; // Current price - Entry price * size
  unrealizedPnlPercent: number;
  distanceToStopPercent: number;
  distanceToTakeProfitPercent: number | null;
}

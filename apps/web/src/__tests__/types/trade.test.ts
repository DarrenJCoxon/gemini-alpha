/**
 * @jest-environment jsdom
 */

import type {
  TradeStatus,
  TradeDirection,
  Trade,
  TradeWithMetrics,
} from '@/types/trade';

describe('Trade Types', () => {
  describe('TradeStatus', () => {
    it('should accept OPEN as a valid status', () => {
      const status: TradeStatus = 'OPEN';
      expect(status).toBe('OPEN');
    });

    it('should accept CLOSED as a valid status', () => {
      const status: TradeStatus = 'CLOSED';
      expect(status).toBe('CLOSED');
    });

    it('should accept STOPPED_OUT as a valid status', () => {
      const status: TradeStatus = 'STOPPED_OUT';
      expect(status).toBe('STOPPED_OUT');
    });

    it('should accept TAKE_PROFIT as a valid status', () => {
      const status: TradeStatus = 'TAKE_PROFIT';
      expect(status).toBe('TAKE_PROFIT');
    });
  });

  describe('TradeDirection', () => {
    it('should accept LONG as a valid direction', () => {
      const direction: TradeDirection = 'LONG';
      expect(direction).toBe('LONG');
    });

    it('should accept SHORT as a valid direction', () => {
      const direction: TradeDirection = 'SHORT';
      expect(direction).toBe('SHORT');
    });
  });

  describe('Trade', () => {
    it('should create a valid Trade object', () => {
      const trade: Trade = {
        id: 'trade-1',
        assetId: 'asset-1',
        status: 'OPEN',
        direction: 'LONG',
        entryPrice: 45000,
        size: 0.5,
        entryTime: new Date('2024-01-01T00:00:00Z'),
        stopLossPrice: 44000,
        takeProfitPrice: 48000,
        exitPrice: null,
        exitTime: null,
        pnl: null,
        createdAt: new Date('2024-01-01T00:00:00Z'),
        updatedAt: new Date('2024-01-01T00:00:00Z'),
      };

      expect(trade.id).toBe('trade-1');
      expect(trade.status).toBe('OPEN');
      expect(trade.direction).toBe('LONG');
      expect(trade.entryPrice).toBe(45000);
    });

    it('should allow optional asset data', () => {
      const trade: Trade = {
        id: 'trade-1',
        assetId: 'asset-1',
        status: 'OPEN',
        direction: 'LONG',
        entryPrice: 45000,
        size: 0.5,
        entryTime: new Date(),
        stopLossPrice: 44000,
        takeProfitPrice: null,
        exitPrice: null,
        exitTime: null,
        pnl: null,
        createdAt: new Date(),
        updatedAt: new Date(),
        asset: {
          symbol: 'BTC/USD',
          lastPrice: 46000,
        },
      };

      expect(trade.asset?.symbol).toBe('BTC/USD');
      expect(trade.asset?.lastPrice).toBe(46000);
    });

    it('should create a closed trade with exit data', () => {
      const trade: Trade = {
        id: 'trade-1',
        assetId: 'asset-1',
        status: 'CLOSED',
        direction: 'LONG',
        entryPrice: 45000,
        size: 0.5,
        entryTime: new Date('2024-01-01T00:00:00Z'),
        stopLossPrice: 44000,
        takeProfitPrice: 48000,
        exitPrice: 47000,
        exitTime: new Date('2024-01-02T00:00:00Z'),
        pnl: 1000,
        createdAt: new Date('2024-01-01T00:00:00Z'),
        updatedAt: new Date('2024-01-02T00:00:00Z'),
      };

      expect(trade.status).toBe('CLOSED');
      expect(trade.exitPrice).toBe(47000);
      expect(trade.pnl).toBe(1000);
    });
  });

  describe('TradeWithMetrics', () => {
    it('should create a valid TradeWithMetrics object', () => {
      const trade: TradeWithMetrics = {
        id: 'trade-1',
        assetId: 'asset-1',
        status: 'OPEN',
        direction: 'LONG',
        entryPrice: 45000,
        size: 0.5,
        entryTime: new Date(),
        stopLossPrice: 44000,
        takeProfitPrice: 48000,
        exitPrice: null,
        exitTime: null,
        pnl: null,
        createdAt: new Date(),
        updatedAt: new Date(),
        currentPrice: 46000,
        unrealizedPnl: 500,
        unrealizedPnlPercent: 2.22,
        distanceToStopPercent: 4.35,
        distanceToTakeProfitPercent: 4.35,
      };

      expect(trade.currentPrice).toBe(46000);
      expect(trade.unrealizedPnl).toBe(500);
      expect(trade.unrealizedPnlPercent).toBe(2.22);
      expect(trade.distanceToStopPercent).toBe(4.35);
    });

    it('should allow null distanceToTakeProfitPercent when no TP set', () => {
      const trade: TradeWithMetrics = {
        id: 'trade-1',
        assetId: 'asset-1',
        status: 'OPEN',
        direction: 'LONG',
        entryPrice: 45000,
        size: 0.5,
        entryTime: new Date(),
        stopLossPrice: 44000,
        takeProfitPrice: null,
        exitPrice: null,
        exitTime: null,
        pnl: null,
        createdAt: new Date(),
        updatedAt: new Date(),
        currentPrice: 46000,
        unrealizedPnl: 500,
        unrealizedPnlPercent: 2.22,
        distanceToStopPercent: 4.35,
        distanceToTakeProfitPercent: null,
      };

      expect(trade.takeProfitPrice).toBeNull();
      expect(trade.distanceToTakeProfitPercent).toBeNull();
    });

    it('should handle SHORT position metrics', () => {
      const trade: TradeWithMetrics = {
        id: 'trade-1',
        assetId: 'asset-1',
        status: 'OPEN',
        direction: 'SHORT',
        entryPrice: 45000,
        size: 0.5,
        entryTime: new Date(),
        stopLossPrice: 46000,
        takeProfitPrice: 43000,
        exitPrice: null,
        exitTime: null,
        pnl: null,
        createdAt: new Date(),
        updatedAt: new Date(),
        currentPrice: 44000,
        unrealizedPnl: 500, // Profit when price goes down for SHORT
        unrealizedPnlPercent: 2.22,
        distanceToStopPercent: 4.55,
        distanceToTakeProfitPercent: 2.27,
      };

      expect(trade.direction).toBe('SHORT');
      expect(trade.currentPrice).toBe(44000);
      expect(trade.unrealizedPnl).toBe(500);
    });
  });
});

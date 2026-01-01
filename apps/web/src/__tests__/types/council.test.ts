/**
 * @jest-environment jsdom
 */

import type {
  DecisionType,
  CouncilSession,
  TechnicalDetails,
  CouncilFeedFilters,
  CouncilFeedResult,
} from '@/types/council';

describe('Council Types', () => {
  describe('DecisionType', () => {
    it('should accept BUY as a valid decision type', () => {
      const decision: DecisionType = 'BUY';
      expect(decision).toBe('BUY');
    });

    it('should accept SELL as a valid decision type', () => {
      const decision: DecisionType = 'SELL';
      expect(decision).toBe('SELL');
    });

    it('should accept HOLD as a valid decision type', () => {
      const decision: DecisionType = 'HOLD';
      expect(decision).toBe('HOLD');
    });
  });

  describe('CouncilSession', () => {
    it('should create a valid CouncilSession object', () => {
      const session: CouncilSession = {
        id: 'test-id',
        assetId: 'asset-1',
        timestamp: new Date('2024-01-01T00:00:00Z'),
        sentimentScore: 45,
        technicalSignal: 'BULLISH',
        technicalStrength: 75,
        technicalDetails: '{"rsi": 55}',
        visionAnalysis: 'Chart shows upward trend',
        visionConfidence: 85,
        visionValid: true,
        finalDecision: 'BUY',
        decisionConfidence: 80,
        reasoningLog: 'Market conditions favor buying',
        createdAt: new Date('2024-01-01T00:00:00Z'),
      };

      expect(session.id).toBe('test-id');
      expect(session.finalDecision).toBe('BUY');
      expect(session.sentimentScore).toBe(45);
    });

    it('should allow optional asset data', () => {
      const session: CouncilSession = {
        id: 'test-id',
        assetId: 'asset-1',
        timestamp: new Date(),
        sentimentScore: 45,
        technicalSignal: 'BULLISH',
        technicalStrength: 75,
        technicalDetails: null,
        visionAnalysis: null,
        visionConfidence: 0,
        visionValid: false,
        finalDecision: 'HOLD',
        decisionConfidence: 50,
        reasoningLog: 'Holding position',
        createdAt: new Date(),
        asset: {
          symbol: 'BTC/USD',
          lastPrice: 45000,
        },
      };

      expect(session.asset?.symbol).toBe('BTC/USD');
      expect(session.asset?.lastPrice).toBe(45000);
    });
  });

  describe('TechnicalDetails', () => {
    it('should create a valid TechnicalDetails object', () => {
      const details: TechnicalDetails = {
        rsi: 55.5,
        sma_50: 43500.25,
        sma_200: 42000.00,
        volume_delta: 15.3,
        reasoning: 'RSI indicates neutral momentum',
      };

      expect(details.rsi).toBe(55.5);
      expect(details.sma_50).toBe(43500.25);
      expect(details.sma_200).toBe(42000.00);
      expect(details.volume_delta).toBe(15.3);
    });

    it('should allow null values', () => {
      const details: TechnicalDetails = {
        rsi: null,
        sma_50: null,
        sma_200: null,
        volume_delta: null,
        reasoning: null,
      };

      expect(details.rsi).toBeNull();
      expect(details.sma_50).toBeNull();
    });
  });

  describe('CouncilFeedFilters', () => {
    it('should create a valid filter with all options', () => {
      const filters: CouncilFeedFilters = {
        assetSymbol: 'BTC/USD',
        decision: 'BUY',
        limit: 20,
        cursor: '2024-01-01T00:00:00Z',
      };

      expect(filters.assetSymbol).toBe('BTC/USD');
      expect(filters.decision).toBe('BUY');
      expect(filters.limit).toBe(20);
      expect(filters.cursor).toBe('2024-01-01T00:00:00Z');
    });

    it('should allow empty filter object', () => {
      const filters: CouncilFeedFilters = {};

      expect(filters.assetSymbol).toBeUndefined();
      expect(filters.decision).toBeUndefined();
    });
  });

  describe('CouncilFeedResult', () => {
    it('should create a valid result with sessions', () => {
      const result: CouncilFeedResult = {
        sessions: [
          {
            id: 'test-id',
            assetId: 'asset-1',
            timestamp: new Date(),
            sentimentScore: 45,
            technicalSignal: 'BULLISH',
            technicalStrength: 75,
            technicalDetails: null,
            visionAnalysis: null,
            visionConfidence: 0,
            visionValid: false,
            finalDecision: 'BUY',
            decisionConfidence: 80,
            reasoningLog: 'Buy signal',
            createdAt: new Date(),
          },
        ],
        nextCursor: '2024-01-01T00:00:00Z',
        hasMore: true,
      };

      expect(result.sessions).toHaveLength(1);
      expect(result.hasMore).toBe(true);
      expect(result.nextCursor).toBe('2024-01-01T00:00:00Z');
    });

    it('should create a valid result with no more items', () => {
      const result: CouncilFeedResult = {
        sessions: [],
        nextCursor: null,
        hasMore: false,
      };

      expect(result.sessions).toHaveLength(0);
      expect(result.hasMore).toBe(false);
      expect(result.nextCursor).toBeNull();
    });
  });
});

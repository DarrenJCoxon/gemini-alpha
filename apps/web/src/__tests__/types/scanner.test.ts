/**
 * @jest-environment jsdom
 */

import type {
  ScannerAsset,
  SortField,
  SortDirection,
  ScannerFilters,
} from '@/types/scanner';

describe('Scanner Types', () => {
  describe('SortField', () => {
    it('should accept symbol as a valid sort field', () => {
      const field: SortField = 'symbol';
      expect(field).toBe('symbol');
    });

    it('should accept lastPrice as a valid sort field', () => {
      const field: SortField = 'lastPrice';
      expect(field).toBe('lastPrice');
    });

    it('should accept sentimentScore as a valid sort field', () => {
      const field: SortField = 'sentimentScore';
      expect(field).toBe('sentimentScore');
    });

    it('should accept technicalSignal as a valid sort field', () => {
      const field: SortField = 'technicalSignal';
      expect(field).toBe('technicalSignal');
    });
  });

  describe('SortDirection', () => {
    it('should accept asc as a valid direction', () => {
      const direction: SortDirection = 'asc';
      expect(direction).toBe('asc');
    });

    it('should accept desc as a valid direction', () => {
      const direction: SortDirection = 'desc';
      expect(direction).toBe('desc');
    });
  });

  describe('ScannerAsset', () => {
    it('should create a valid ScannerAsset object', () => {
      const asset: ScannerAsset = {
        id: 'asset-1',
        symbol: 'BTC/USD',
        lastPrice: 45000,
        priceChange15m: 2.5,
        sentimentScore: 35,
        technicalSignal: 'BULLISH',
        technicalStrength: 75,
        lastSessionTime: new Date('2024-01-01T00:00:00Z'),
      };

      expect(asset.id).toBe('asset-1');
      expect(asset.symbol).toBe('BTC/USD');
      expect(asset.lastPrice).toBe(45000);
      expect(asset.priceChange15m).toBe(2.5);
      expect(asset.sentimentScore).toBe(35);
      expect(asset.technicalSignal).toBe('BULLISH');
    });

    it('should allow null values for optional fields', () => {
      const asset: ScannerAsset = {
        id: 'asset-1',
        symbol: 'ETH/USD',
        lastPrice: 2500,
        priceChange15m: -1.2,
        sentimentScore: null,
        technicalSignal: null,
        technicalStrength: null,
        lastSessionTime: null,
      };

      expect(asset.sentimentScore).toBeNull();
      expect(asset.technicalSignal).toBeNull();
      expect(asset.technicalStrength).toBeNull();
      expect(asset.lastSessionTime).toBeNull();
    });

    it('should handle negative price change', () => {
      const asset: ScannerAsset = {
        id: 'asset-1',
        symbol: 'BTC/USD',
        lastPrice: 44000,
        priceChange15m: -3.5,
        sentimentScore: 15,
        technicalSignal: 'BEARISH',
        technicalStrength: 65,
        lastSessionTime: new Date(),
      };

      expect(asset.priceChange15m).toBe(-3.5);
      expect(asset.technicalSignal).toBe('BEARISH');
    });

    it('should handle neutral technical signal', () => {
      const asset: ScannerAsset = {
        id: 'asset-1',
        symbol: 'XRP/USD',
        lastPrice: 0.5,
        priceChange15m: 0.1,
        sentimentScore: 50,
        technicalSignal: 'NEUTRAL',
        technicalStrength: 40,
        lastSessionTime: new Date(),
      };

      expect(asset.technicalSignal).toBe('NEUTRAL');
      expect(asset.sentimentScore).toBe(50);
    });
  });

  describe('ScannerFilters', () => {
    it('should create a valid filter with all options', () => {
      const filters: ScannerFilters = {
        sortBy: 'sentimentScore',
        sortDirection: 'asc',
        limit: 30,
      };

      expect(filters.sortBy).toBe('sentimentScore');
      expect(filters.sortDirection).toBe('asc');
      expect(filters.limit).toBe(30);
    });

    it('should allow empty filter object', () => {
      const filters: ScannerFilters = {};

      expect(filters.sortBy).toBeUndefined();
      expect(filters.sortDirection).toBeUndefined();
      expect(filters.limit).toBeUndefined();
    });

    it('should allow partial filters', () => {
      const filters: ScannerFilters = {
        sortBy: 'lastPrice',
      };

      expect(filters.sortBy).toBe('lastPrice');
      expect(filters.sortDirection).toBeUndefined();
    });
  });
});

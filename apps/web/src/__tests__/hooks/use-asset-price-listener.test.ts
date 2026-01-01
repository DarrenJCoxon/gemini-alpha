/**
 * @jest-environment jsdom
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useAssetPriceListener } from '@/hooks/use-asset-price-listener';
import { subscribeToTable } from '@/lib/supabase/realtime';

// Mock dependencies
jest.mock('@/lib/supabase/realtime', () => ({
  subscribeToTable: jest.fn(),
}));

const mockSubscribeToTable = subscribeToTable as jest.Mock;

describe('useAssetPriceListener Hook', () => {
  let mockUnsubscribe: jest.Mock;
  let capturedCallback: ((payload: unknown) => void) | null = null;

  beforeEach(() => {
    jest.clearAllMocks();
    capturedCallback = null;
    mockUnsubscribe = jest.fn();

    mockSubscribeToTable.mockImplementation((table, event, callback) => {
      capturedCallback = callback;
      return { unsubscribe: mockUnsubscribe };
    });
  });

  const createMockPricePayload = (
    assetId: string,
    newPrice: string,
    oldPrice: string
  ) => ({
    new: {
      id: assetId,
      symbol: 'BTC/USD',
      last_price: newPrice,
    },
    old: {
      id: assetId,
      last_price: oldPrice,
    },
  });

  describe('Subscription Setup', () => {
    it('should subscribe to assets table for UPDATE events', () => {
      const onPriceUpdate = jest.fn();
      renderHook(() => useAssetPriceListener({ onPriceUpdate }));

      expect(mockSubscribeToTable).toHaveBeenCalledWith(
        'assets',
        'UPDATE',
        expect.any(Function)
      );
    });

    it('should unsubscribe on unmount', () => {
      const onPriceUpdate = jest.fn();
      const { unmount } = renderHook(() => useAssetPriceListener({ onPriceUpdate }));

      unmount();

      expect(mockUnsubscribe).toHaveBeenCalled();
    });
  });

  describe('Price Updates', () => {
    it('should call onPriceUpdate when price changes', async () => {
      const onPriceUpdate = jest.fn();
      renderHook(() => useAssetPriceListener({ onPriceUpdate }));

      const payload = createMockPricePayload('asset-123', '105.00', '100.00');

      act(() => {
        capturedCallback?.(payload);
      });

      await waitFor(() => {
        expect(onPriceUpdate).toHaveBeenCalledWith({
          assetId: 'asset-123',
          symbol: 'BTC/USD',
          lastPrice: 105,
        });
      });
    });

    it('should not call onPriceUpdate when price is unchanged', () => {
      const onPriceUpdate = jest.fn();
      renderHook(() => useAssetPriceListener({ onPriceUpdate }));

      const payload = createMockPricePayload('asset-123', '100.00', '100.00');

      act(() => {
        capturedCallback?.(payload);
      });

      expect(onPriceUpdate).not.toHaveBeenCalled();
    });

    it('should ignore payload with no new record', () => {
      const onPriceUpdate = jest.fn();
      renderHook(() => useAssetPriceListener({ onPriceUpdate }));

      act(() => {
        capturedCallback?.({ new: null, old: null });
      });

      expect(onPriceUpdate).not.toHaveBeenCalled();
    });
  });

  describe('Asset ID Filtering', () => {
    it('should filter updates by assetIds when provided', async () => {
      const onPriceUpdate = jest.fn();
      renderHook(() =>
        useAssetPriceListener({
          onPriceUpdate,
          assetIds: ['asset-123', 'asset-456'],
        })
      );

      const payload = createMockPricePayload('asset-123', '105.00', '100.00');

      act(() => {
        capturedCallback?.(payload);
      });

      await waitFor(() => {
        expect(onPriceUpdate).toHaveBeenCalled();
      });
    });

    it('should ignore updates for assets not in assetIds list', () => {
      const onPriceUpdate = jest.fn();
      renderHook(() =>
        useAssetPriceListener({
          onPriceUpdate,
          assetIds: ['asset-456'],
        })
      );

      const payload = createMockPricePayload('asset-123', '105.00', '100.00');

      act(() => {
        capturedCallback?.(payload);
      });

      expect(onPriceUpdate).not.toHaveBeenCalled();
    });

    it('should allow all updates when assetIds is undefined', async () => {
      const onPriceUpdate = jest.fn();
      renderHook(() => useAssetPriceListener({ onPriceUpdate }));

      const payload = createMockPricePayload('any-asset', '105.00', '100.00');

      act(() => {
        capturedCallback?.(payload);
      });

      await waitFor(() => {
        expect(onPriceUpdate).toHaveBeenCalled();
      });
    });

    it('should allow all updates when assetIds is empty array', async () => {
      const onPriceUpdate = jest.fn();
      renderHook(() =>
        useAssetPriceListener({
          onPriceUpdate,
          assetIds: [],
        })
      );

      const payload = createMockPricePayload('any-asset', '105.00', '100.00');

      act(() => {
        capturedCallback?.(payload);
      });

      await waitFor(() => {
        expect(onPriceUpdate).toHaveBeenCalled();
      });
    });
  });

  describe('Callback Updates', () => {
    it('should use latest callback when it changes', async () => {
      const onPriceUpdate1 = jest.fn();
      const onPriceUpdate2 = jest.fn();

      const { rerender } = renderHook(
        ({ onPriceUpdate }) => useAssetPriceListener({ onPriceUpdate }),
        { initialProps: { onPriceUpdate: onPriceUpdate1 } }
      );

      rerender({ onPriceUpdate: onPriceUpdate2 });

      const payload = createMockPricePayload('asset-123', '105.00', '100.00');

      act(() => {
        capturedCallback?.(payload);
      });

      await waitFor(() => {
        expect(onPriceUpdate2).toHaveBeenCalled();
        expect(onPriceUpdate1).not.toHaveBeenCalled();
      });
    });
  });

  describe('Resubscription on Asset ID Change', () => {
    it('should resubscribe when assetIds change', () => {
      const onPriceUpdate = jest.fn();

      const { rerender } = renderHook(
        ({ assetIds }) => useAssetPriceListener({ onPriceUpdate, assetIds }),
        { initialProps: { assetIds: ['asset-1'] } }
      );

      expect(mockSubscribeToTable).toHaveBeenCalledTimes(1);

      rerender({ assetIds: ['asset-2'] });

      // Should have unsubscribed and resubscribed
      expect(mockUnsubscribe).toHaveBeenCalled();
      expect(mockSubscribeToTable).toHaveBeenCalledTimes(2);
    });
  });
});

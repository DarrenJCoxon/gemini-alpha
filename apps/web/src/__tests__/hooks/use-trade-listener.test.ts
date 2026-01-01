/**
 * @jest-environment jsdom
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useTradeListener } from '@/hooks/use-trade-listener';
import { subscribeToTable } from '@/lib/supabase/realtime';
import { toast } from 'sonner';

// Mock dependencies
jest.mock('@/lib/supabase/realtime', () => ({
  subscribeToTable: jest.fn(),
}));

jest.mock('sonner', () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
    info: jest.fn(),
    warning: jest.fn(),
  },
}));

const mockSubscribeToTable = subscribeToTable as jest.Mock;

describe('useTradeListener Hook', () => {
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

  const createMockTradePayload = (eventType: string, status = 'OPEN', oldStatus?: string) => ({
    eventType,
    new: {
      id: 'trade-123',
      asset_id: 'asset-456',
      status,
      direction: 'LONG',
      entry_price: '100.00',
      size: '0.5',
      entry_time: new Date().toISOString(),
      stop_loss_price: '95.00',
      take_profit_price: '110.00',
      exit_price: status !== 'OPEN' ? '105.00' : null,
      exit_time: status !== 'OPEN' ? new Date().toISOString() : null,
      pnl: status !== 'OPEN' ? '2.50' : null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
    old: oldStatus ? { id: 'trade-123', status: oldStatus } : undefined,
  });

  describe('Subscription Setup', () => {
    it('should subscribe to trades table with wildcard event', () => {
      renderHook(() => useTradeListener({}));

      expect(mockSubscribeToTable).toHaveBeenCalledWith(
        'trades',
        '*',
        expect.any(Function)
      );
    });

    it('should unsubscribe on unmount', () => {
      const { unmount } = renderHook(() => useTradeListener({}));

      unmount();

      expect(mockUnsubscribe).toHaveBeenCalled();
    });
  });

  describe('INSERT Events', () => {
    it('should call onTradeInsert for new trades', async () => {
      const onTradeInsert = jest.fn();
      renderHook(() => useTradeListener({ onTradeInsert, showToasts: false }));

      const payload = createMockTradePayload('INSERT');

      act(() => {
        capturedCallback?.(payload);
      });

      await waitFor(() => {
        expect(onTradeInsert).toHaveBeenCalledWith(
          expect.objectContaining({
            id: 'trade-123',
            assetId: 'asset-456',
            status: 'OPEN',
            entryPrice: 100,
          })
        );
      });
    });

    it('should show success toast for trade insert when showToasts is true', async () => {
      const onTradeInsert = jest.fn();
      renderHook(() => useTradeListener({ onTradeInsert, showToasts: true }));

      const payload = createMockTradePayload('INSERT');

      act(() => {
        capturedCallback?.(payload);
      });

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalledWith(
          expect.stringContaining('Trade Opened'),
          expect.any(Object)
        );
      });
    });
  });

  describe('UPDATE Events', () => {
    it('should call onTradeUpdate for trade updates', async () => {
      const onTradeUpdate = jest.fn();
      renderHook(() => useTradeListener({ onTradeUpdate, showToasts: false }));

      const payload = createMockTradePayload('UPDATE', 'OPEN', 'OPEN');

      act(() => {
        capturedCallback?.(payload);
      });

      await waitFor(() => {
        expect(onTradeUpdate).toHaveBeenCalled();
      });
    });

    it('should show error toast for STOPPED_OUT status change', async () => {
      const onTradeUpdate = jest.fn();
      renderHook(() => useTradeListener({ onTradeUpdate, showToasts: true }));

      const payload = createMockTradePayload('UPDATE', 'STOPPED_OUT', 'OPEN');

      act(() => {
        capturedCallback?.(payload);
      });

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith(
          expect.stringContaining('Stopped Out'),
          expect.any(Object)
        );
      });
    });

    it('should show success toast for TAKE_PROFIT status change', async () => {
      const onTradeUpdate = jest.fn();
      renderHook(() => useTradeListener({ onTradeUpdate, showToasts: true }));

      const payload = createMockTradePayload('UPDATE', 'TAKE_PROFIT', 'OPEN');

      act(() => {
        capturedCallback?.(payload);
      });

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalledWith(
          expect.stringContaining('Take Profit'),
          expect.any(Object)
        );
      });
    });

    it('should not show toast when status does not change', () => {
      const onTradeUpdate = jest.fn();
      renderHook(() => useTradeListener({ onTradeUpdate, showToasts: true }));

      const payload = createMockTradePayload('UPDATE', 'OPEN', 'OPEN');

      act(() => {
        capturedCallback?.(payload);
      });

      // No status change toasts
      expect(toast.error).not.toHaveBeenCalled();
      expect(toast.success).not.toHaveBeenCalledWith(
        expect.stringContaining('Take Profit'),
        expect.any(Object)
      );
    });
  });

  describe('DELETE Events', () => {
    it('should call onTradeDelete with trade ID', async () => {
      const onTradeDelete = jest.fn();
      renderHook(() => useTradeListener({ onTradeDelete, showToasts: false }));

      const payload = {
        eventType: 'DELETE',
        old: { id: 'trade-123' },
        new: null,
      };

      act(() => {
        capturedCallback?.(payload);
      });

      await waitFor(() => {
        expect(onTradeDelete).toHaveBeenCalledWith('trade-123');
      });
    });
  });

  describe('Callback Updates', () => {
    it('should use latest callbacks when they change', async () => {
      const onTradeInsert1 = jest.fn();
      const onTradeInsert2 = jest.fn();

      const { rerender } = renderHook(
        ({ onTradeInsert }) => useTradeListener({ onTradeInsert, showToasts: false }),
        { initialProps: { onTradeInsert: onTradeInsert1 } }
      );

      rerender({ onTradeInsert: onTradeInsert2 });

      const payload = createMockTradePayload('INSERT');

      act(() => {
        capturedCallback?.(payload);
      });

      await waitFor(() => {
        expect(onTradeInsert2).toHaveBeenCalled();
        expect(onTradeInsert1).not.toHaveBeenCalled();
      });
    });
  });

  describe('Missing Callbacks', () => {
    it('should handle missing onTradeInsert callback gracefully', () => {
      renderHook(() => useTradeListener({ showToasts: false }));

      const payload = createMockTradePayload('INSERT');

      expect(() => {
        act(() => {
          capturedCallback?.(payload);
        });
      }).not.toThrow();
    });

    it('should handle missing onTradeUpdate callback gracefully', () => {
      renderHook(() => useTradeListener({ showToasts: false }));

      const payload = createMockTradePayload('UPDATE');

      expect(() => {
        act(() => {
          capturedCallback?.(payload);
        });
      }).not.toThrow();
    });

    it('should handle missing onTradeDelete callback gracefully', () => {
      renderHook(() => useTradeListener({ showToasts: false }));

      const payload = {
        eventType: 'DELETE',
        old: { id: 'trade-123' },
        new: null,
      };

      expect(() => {
        act(() => {
          capturedCallback?.(payload);
        });
      }).not.toThrow();
    });
  });
});

/**
 * @jest-environment jsdom
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useCouncilListener } from '@/hooks/use-council-listener';
import { subscribeToTable } from '@/lib/supabase/realtime';
import { toast } from 'sonner';
import { CouncilSession } from '@/types/council';

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

describe('useCouncilListener Hook', () => {
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

  const createMockPayload = (decision: string, confidence = 80) => ({
    new: {
      id: 'session-123',
      asset_id: 'asset-456',
      timestamp: new Date().toISOString(),
      sentiment_score: 25,
      technical_signal: 'BULLISH',
      technical_strength: 75,
      technical_details: null,
      vision_analysis: null,
      vision_confidence: 70,
      vision_valid: true,
      final_decision: decision,
      decision_confidence: confidence,
      reasoning_log: 'Test reasoning log for the session',
      created_at: new Date().toISOString(),
    },
  });

  describe('Subscription Setup', () => {
    it('should subscribe to council_sessions table on mount', () => {
      const onNewSession = jest.fn();
      renderHook(() => useCouncilListener({ onNewSession }));

      expect(mockSubscribeToTable).toHaveBeenCalledWith(
        'council_sessions',
        'INSERT',
        expect.any(Function)
      );
    });

    it('should unsubscribe on unmount', () => {
      const onNewSession = jest.fn();
      const { unmount } = renderHook(() => useCouncilListener({ onNewSession }));

      unmount();

      expect(mockUnsubscribe).toHaveBeenCalled();
    });
  });

  describe('Payload Transformation', () => {
    it('should transform database payload to CouncilSession type', async () => {
      const onNewSession = jest.fn();
      renderHook(() => useCouncilListener({ onNewSession }));

      const payload = createMockPayload('BUY');

      act(() => {
        capturedCallback?.(payload);
      });

      await waitFor(() => {
        expect(onNewSession).toHaveBeenCalledWith(
          expect.objectContaining({
            id: 'session-123',
            assetId: 'asset-456',
            finalDecision: 'BUY',
            decisionConfidence: 80,
            sentimentScore: 25,
            technicalSignal: 'BULLISH',
          })
        );
      });
    });

    it('should ignore payload with no new record', () => {
      const onNewSession = jest.fn();
      renderHook(() => useCouncilListener({ onNewSession }));

      act(() => {
        capturedCallback?.({ new: null });
      });

      expect(onNewSession).not.toHaveBeenCalled();
    });
  });

  describe('Toast Notifications', () => {
    it('should show success toast for BUY signal', async () => {
      const onNewSession = jest.fn();
      renderHook(() => useCouncilListener({ onNewSession, showToasts: true }));

      const payload = createMockPayload('BUY');

      act(() => {
        capturedCallback?.(payload);
      });

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalledWith(
          expect.stringContaining('BUY'),
          expect.any(Object)
        );
      });
    });

    it('should show error toast for SELL signal', async () => {
      const onNewSession = jest.fn();
      renderHook(() => useCouncilListener({ onNewSession, showToasts: true }));

      const payload = createMockPayload('SELL');

      act(() => {
        capturedCallback?.(payload);
      });

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith(
          expect.stringContaining('SELL'),
          expect.any(Object)
        );
      });
    });

    it('should show info toast for high-confidence HOLD signal', async () => {
      const onNewSession = jest.fn();
      renderHook(() => useCouncilListener({ onNewSession, showToasts: true }));

      const payload = createMockPayload('HOLD', 85);

      act(() => {
        capturedCallback?.(payload);
      });

      await waitFor(() => {
        expect(toast.info).toHaveBeenCalledWith(
          expect.stringContaining('HOLD'),
          expect.any(Object)
        );
      });
    });

    it('should not show toast for low-confidence HOLD signal', () => {
      const onNewSession = jest.fn();
      renderHook(() => useCouncilListener({ onNewSession, showToasts: true }));

      const payload = createMockPayload('HOLD', 50);

      act(() => {
        capturedCallback?.(payload);
      });

      expect(toast.info).not.toHaveBeenCalled();
    });

    it('should not show toasts when showToasts is false', () => {
      const onNewSession = jest.fn();
      renderHook(() => useCouncilListener({ onNewSession, showToasts: false }));

      const payload = createMockPayload('BUY');

      act(() => {
        capturedCallback?.(payload);
      });

      expect(toast.success).not.toHaveBeenCalled();
      expect(toast.error).not.toHaveBeenCalled();
      expect(toast.info).not.toHaveBeenCalled();
    });
  });

  describe('Callback Updates', () => {
    it('should use latest callback when it changes', async () => {
      const onNewSession1 = jest.fn();
      const onNewSession2 = jest.fn();

      const { rerender } = renderHook(
        ({ onNewSession }) => useCouncilListener({ onNewSession, showToasts: false }),
        { initialProps: { onNewSession: onNewSession1 } }
      );

      // Update the callback
      rerender({ onNewSession: onNewSession2 });

      const payload = createMockPayload('BUY');

      act(() => {
        capturedCallback?.(payload);
      });

      await waitFor(() => {
        expect(onNewSession2).toHaveBeenCalled();
        expect(onNewSession1).not.toHaveBeenCalled();
      });
    });
  });
});

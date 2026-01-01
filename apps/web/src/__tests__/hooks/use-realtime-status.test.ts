/**
 * @jest-environment jsdom
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useRealtimeStatus } from '@/hooks/use-realtime-status';
import { createClient } from '@/lib/supabase/client';

// Mock the client module
jest.mock('@/lib/supabase/client', () => ({
  createClient: jest.fn(),
}));

const mockCreateClient = createClient as jest.Mock;

describe('useRealtimeStatus Hook', () => {
  let mockChannel: {
    subscribe: jest.Mock;
  };
  let mockSupabaseClient: {
    channel: jest.Mock;
    removeChannel: jest.Mock;
  };
  let capturedSubscribeCallback: ((status: string) => void) | null = null;

  beforeEach(() => {
    jest.clearAllMocks();
    capturedSubscribeCallback = null;

    mockChannel = {
      subscribe: jest.fn((callback) => {
        capturedSubscribeCallback = callback;
        return mockChannel;
      }),
    };

    mockSupabaseClient = {
      channel: jest.fn().mockReturnValue(mockChannel),
      removeChannel: jest.fn(),
    };

    mockCreateClient.mockReturnValue(mockSupabaseClient);
  });

  describe('Initial State', () => {
    it('should start with connecting status', () => {
      const { result } = renderHook(() => useRealtimeStatus());

      expect(result.current).toBe('connecting');
    });

    it('should create a connection-status channel', () => {
      renderHook(() => useRealtimeStatus());

      expect(mockSupabaseClient.channel).toHaveBeenCalledWith('connection-status');
    });
  });

  describe('Status Updates', () => {
    it('should update to connected when SUBSCRIBED', async () => {
      const { result } = renderHook(() => useRealtimeStatus());

      act(() => {
        capturedSubscribeCallback?.('SUBSCRIBED');
      });

      await waitFor(() => {
        expect(result.current).toBe('connected');
      });
    });

    it('should update to disconnected when CLOSED', async () => {
      const { result } = renderHook(() => useRealtimeStatus());

      act(() => {
        capturedSubscribeCallback?.('CLOSED');
      });

      await waitFor(() => {
        expect(result.current).toBe('disconnected');
      });
    });

    it('should update to disconnected when TIMED_OUT', async () => {
      const { result } = renderHook(() => useRealtimeStatus());

      act(() => {
        capturedSubscribeCallback?.('TIMED_OUT');
      });

      await waitFor(() => {
        expect(result.current).toBe('disconnected');
      });
    });

    it('should update to error when CHANNEL_ERROR', async () => {
      const { result } = renderHook(() => useRealtimeStatus());

      act(() => {
        capturedSubscribeCallback?.('CHANNEL_ERROR');
      });

      await waitFor(() => {
        expect(result.current).toBe('error');
      });
    });

    it('should stay connecting for unknown status', async () => {
      const { result } = renderHook(() => useRealtimeStatus());

      act(() => {
        capturedSubscribeCallback?.('UNKNOWN_STATUS');
      });

      await waitFor(() => {
        expect(result.current).toBe('connecting');
      });
    });
  });

  describe('Cleanup', () => {
    it('should remove channel on unmount', () => {
      const { unmount } = renderHook(() => useRealtimeStatus());

      unmount();

      expect(mockSupabaseClient.removeChannel).toHaveBeenCalledWith(mockChannel);
    });
  });

  describe('Status Transitions', () => {
    it('should handle transition from connecting to connected', async () => {
      const { result } = renderHook(() => useRealtimeStatus());

      expect(result.current).toBe('connecting');

      act(() => {
        capturedSubscribeCallback?.('SUBSCRIBED');
      });

      await waitFor(() => {
        expect(result.current).toBe('connected');
      });
    });

    it('should handle transition from connected to disconnected', async () => {
      const { result } = renderHook(() => useRealtimeStatus());

      act(() => {
        capturedSubscribeCallback?.('SUBSCRIBED');
      });

      await waitFor(() => {
        expect(result.current).toBe('connected');
      });

      act(() => {
        capturedSubscribeCallback?.('CLOSED');
      });

      await waitFor(() => {
        expect(result.current).toBe('disconnected');
      });
    });

    it('should handle transition from connected to error', async () => {
      const { result } = renderHook(() => useRealtimeStatus());

      act(() => {
        capturedSubscribeCallback?.('SUBSCRIBED');
      });

      await waitFor(() => {
        expect(result.current).toBe('connected');
      });

      act(() => {
        capturedSubscribeCallback?.('CHANNEL_ERROR');
      });

      await waitFor(() => {
        expect(result.current).toBe('error');
      });
    });
  });
});

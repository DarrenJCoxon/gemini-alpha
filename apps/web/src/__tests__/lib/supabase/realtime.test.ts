/**
 * @jest-environment node
 */

import {
  subscribeToTable,
  subscribeToMultipleTables,
  RealtimeEventType,
} from '@/lib/supabase/realtime';

// Mock the client module
jest.mock('@/lib/supabase/client', () => ({
  createClient: jest.fn(),
}));

import { createClient } from '@/lib/supabase/client';

const mockCreateClient = createClient as jest.Mock;

describe('Supabase Realtime Utilities', () => {
  let mockChannel: {
    on: jest.Mock;
    subscribe: jest.Mock;
  };
  let mockSupabaseClient: {
    channel: jest.Mock;
    removeChannel: jest.Mock;
  };

  beforeEach(() => {
    jest.clearAllMocks();

    // Create mock channel
    mockChannel = {
      on: jest.fn().mockReturnThis(),
      subscribe: jest.fn((callback) => {
        callback('SUBSCRIBED');
        return mockChannel;
      }),
    };

    // Create mock client
    mockSupabaseClient = {
      channel: jest.fn().mockReturnValue(mockChannel),
      removeChannel: jest.fn(),
    };

    mockCreateClient.mockReturnValue(mockSupabaseClient);
  });

  describe('subscribeToTable', () => {
    it('should create a channel with the correct name', () => {
      const callback = jest.fn();
      subscribeToTable('council_sessions', 'INSERT', callback);

      expect(mockSupabaseClient.channel).toHaveBeenCalledWith(
        expect.stringMatching(/^council_sessions-INSERT-\d+$/)
      );
    });

    it('should configure postgres_changes with correct parameters', () => {
      const callback = jest.fn();
      subscribeToTable('trades', 'UPDATE', callback);

      expect(mockChannel.on).toHaveBeenCalledWith(
        'postgres_changes',
        expect.objectContaining({
          event: 'UPDATE',
          schema: 'public',
          table: 'trades',
        }),
        callback
      );
    });

    it('should handle wildcard event type', () => {
      const callback = jest.fn();
      subscribeToTable('assets', '*', callback);

      expect(mockChannel.on).toHaveBeenCalledWith(
        'postgres_changes',
        expect.objectContaining({
          event: '*',
          schema: 'public',
          table: 'assets',
        }),
        callback
      );
    });

    it('should include filter when provided', () => {
      const callback = jest.fn();
      subscribeToTable('trades', 'INSERT', callback, 'status=eq.OPEN');

      expect(mockChannel.on).toHaveBeenCalledWith(
        'postgres_changes',
        expect.objectContaining({
          event: 'INSERT',
          schema: 'public',
          table: 'trades',
          filter: 'status=eq.OPEN',
        }),
        callback
      );
    });

    it('should subscribe to the channel', () => {
      const callback = jest.fn();
      subscribeToTable('council_sessions', 'INSERT', callback);

      expect(mockChannel.subscribe).toHaveBeenCalled();
    });

    it('should return a subscription with unsubscribe method', () => {
      const callback = jest.fn();
      const subscription = subscribeToTable('council_sessions', 'INSERT', callback);

      expect(subscription).toHaveProperty('channel');
      expect(subscription).toHaveProperty('unsubscribe');
      expect(typeof subscription.unsubscribe).toBe('function');
    });

    it('should remove channel when unsubscribe is called', () => {
      const callback = jest.fn();
      const subscription = subscribeToTable('council_sessions', 'INSERT', callback);

      subscription.unsubscribe();

      expect(mockSupabaseClient.removeChannel).toHaveBeenCalledWith(mockChannel);
    });

    it('should handle DELETE event type', () => {
      const callback = jest.fn();
      subscribeToTable('trades', 'DELETE', callback);

      expect(mockChannel.on).toHaveBeenCalledWith(
        'postgres_changes',
        expect.objectContaining({
          event: 'DELETE',
          schema: 'public',
          table: 'trades',
        }),
        callback
      );
    });
  });

  describe('subscribeToMultipleTables', () => {
    it('should create subscriptions for each table config', () => {
      const callback1 = jest.fn();
      const callback2 = jest.fn();

      subscribeToMultipleTables([
        { table: 'council_sessions', event: 'INSERT', callback: callback1 },
        { table: 'trades', event: '*', callback: callback2 },
      ]);

      expect(mockSupabaseClient.channel).toHaveBeenCalledTimes(2);
    });

    it('should return a cleanup function', () => {
      const cleanup = subscribeToMultipleTables([
        { table: 'council_sessions', event: 'INSERT', callback: jest.fn() },
      ]);

      expect(typeof cleanup).toBe('function');
    });

    it('should unsubscribe from all channels when cleanup is called', () => {
      const cleanup = subscribeToMultipleTables([
        { table: 'council_sessions', event: 'INSERT', callback: jest.fn() },
        { table: 'trades', event: 'UPDATE', callback: jest.fn() },
      ]);

      cleanup();

      expect(mockSupabaseClient.removeChannel).toHaveBeenCalledTimes(2);
    });

    it('should handle filters in multiple subscriptions', () => {
      subscribeToMultipleTables([
        {
          table: 'trades',
          event: 'UPDATE',
          callback: jest.fn(),
          filter: 'status=eq.OPEN',
        },
      ]);

      expect(mockChannel.on).toHaveBeenCalledWith(
        'postgres_changes',
        expect.objectContaining({
          filter: 'status=eq.OPEN',
        }),
        expect.any(Function)
      );
    });

    it('should handle empty array', () => {
      const cleanup = subscribeToMultipleTables([]);

      expect(mockSupabaseClient.channel).not.toHaveBeenCalled();
      expect(typeof cleanup).toBe('function');
    });
  });
});

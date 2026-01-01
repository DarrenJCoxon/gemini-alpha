import { createClient } from './client';
import { RealtimeChannel, RealtimePostgresChangesPayload } from '@supabase/supabase-js';

export type RealtimeEventType = 'INSERT' | 'UPDATE' | 'DELETE';

export interface RealtimeSubscription {
  channel: RealtimeChannel;
  unsubscribe: () => void;
}

/**
 * Subscribe to realtime changes on a specific table.
 *
 * @param table - The table name to subscribe to
 * @param event - The event type (INSERT, UPDATE, DELETE, or *)
 * @param callback - Function called when changes occur
 * @param filter - Optional filter string (e.g., "status=eq.OPEN")
 * @returns Subscription object with unsubscribe method
 */
export function subscribeToTable<T extends Record<string, unknown>>(
  table: string,
  event: RealtimeEventType | '*',
  callback: (payload: RealtimePostgresChangesPayload<T>) => void,
  filter?: string
): RealtimeSubscription {
  const supabase = createClient();

  const channelName = `${table}-${event}-${Date.now()}`;

  // Build the channel configuration
  const channelConfig: {
    event: 'INSERT' | 'UPDATE' | 'DELETE' | '*';
    schema: string;
    table: string;
    filter?: string;
  } = {
    event: event,
    schema: 'public',
    table,
  };

  // Only add filter if provided
  if (filter) {
    channelConfig.filter = filter;
  }

  const channel = supabase
    .channel(channelName)
    .on(
      'postgres_changes',
      channelConfig,
      callback as (payload: RealtimePostgresChangesPayload<Record<string, unknown>>) => void
    )
    .subscribe((status) => {
      console.log(`[Realtime] ${channelName} subscription status:`, status);
    });

  return {
    channel,
    unsubscribe: () => {
      console.log(`[Realtime] Unsubscribing from ${channelName}`);
      supabase.removeChannel(channel);
    },
  };
}

/**
 * Subscribe to multiple tables at once.
 * Returns a cleanup function that unsubscribes from all channels.
 */
export function subscribeToMultipleTables(
  subscriptions: Array<{
    table: string;
    event: RealtimeEventType | '*';
    callback: (payload: RealtimePostgresChangesPayload<Record<string, unknown>>) => void;
    filter?: string;
  }>
): () => void {
  const subs = subscriptions.map((config) =>
    subscribeToTable(config.table, config.event, config.callback, config.filter)
  );

  return () => {
    subs.forEach((sub) => sub.unsubscribe());
  };
}

'use client';

import { useState, useEffect } from 'react';
import { createClient } from '@/lib/supabase/client';

export type RealtimeStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

/**
 * Hook to track the overall Supabase Realtime connection status.
 */
export function useRealtimeStatus(): RealtimeStatus {
  const [status, setStatus] = useState<RealtimeStatus>('connecting');

  useEffect(() => {
    const supabase = createClient();

    // Create a test channel to monitor connection status
    const channel = supabase
      .channel('connection-status')
      .subscribe((subscriptionStatus) => {
        switch (subscriptionStatus) {
          case 'SUBSCRIBED':
            setStatus('connected');
            break;
          case 'CLOSED':
          case 'TIMED_OUT':
            setStatus('disconnected');
            break;
          case 'CHANNEL_ERROR':
            setStatus('error');
            break;
          default:
            setStatus('connecting');
        }
      });

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  return status;
}

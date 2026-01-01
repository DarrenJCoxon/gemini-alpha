'use client';

import { useEffect, useRef } from 'react';
import { subscribeToTable } from '@/lib/supabase/realtime';

export interface AssetPriceUpdate {
  assetId: string;
  symbol: string;
  lastPrice: number;
}

interface UseAssetPriceListenerOptions {
  onPriceUpdate: (update: AssetPriceUpdate) => void;
  assetIds?: string[]; // Optional filter to specific assets
}

/**
 * Hook to listen for asset price updates via Supabase Realtime.
 * Updates when the `last_price` column changes on the assets table.
 */
export function useAssetPriceListener({
  onPriceUpdate,
  assetIds,
}: UseAssetPriceListenerOptions) {
  const callbackRef = useRef(onPriceUpdate);

  useEffect(() => {
    callbackRef.current = onPriceUpdate;
  }, [onPriceUpdate]);

  // Serialize assetIds for dependency comparison
  const assetIdsKey = assetIds?.join(',') || '';

  useEffect(() => {
    const { unsubscribe } = subscribeToTable(
      'assets',
      'UPDATE',
      (payload) => {
        const newRecord = payload.new as Record<string, unknown> | undefined;
        const oldRecord = payload.old as Record<string, unknown> | undefined;

        if (!newRecord) return;

        // Only trigger if price actually changed
        if (newRecord.last_price === oldRecord?.last_price) return;

        // Filter by asset IDs if provided
        if (assetIds && assetIds.length > 0 && !assetIds.includes(newRecord.id as string)) return;

        callbackRef.current({
          assetId: newRecord.id as string,
          symbol: newRecord.symbol as string,
          lastPrice: parseFloat(newRecord.last_price as string),
        });
      }
    );

    return () => {
      unsubscribe();
    };
  }, [assetIdsKey, assetIds]);
}

'use server';

import { createClient } from '@/lib/supabase/server';
import { ScannerAsset, ScannerFilters } from '@/types/scanner';

/**
 * Fetches assets for the market scanner with sentiment and technical data
 * @param filters Optional sorting and filtering options
 * @returns Array of scanner assets with latest council session data
 */
export async function fetchScannerAssets(
  filters: ScannerFilters = { sortBy: 'sentimentScore', sortDirection: 'asc' }
): Promise<ScannerAsset[]> {
  const supabase = await createClient();

  // Get all active assets
  const { data: assets, error: assetsError } = await supabase
    .from('assets')
    .select('*')
    .eq('is_active', true)
    .limit(filters.limit || 30);

  if (assetsError) {
    console.error('Error fetching assets:', assetsError);
    throw new Error('Failed to fetch scanner assets');
  }

  if (!assets || assets.length === 0) {
    return [];
  }

  // Get asset IDs for related queries
  const assetIds = assets.map((a: Record<string, unknown>) => a.id as string);

  // Get latest council session for each asset
  const { data: sessions, error: sessionsError } = await supabase
    .from('council_sessions')
    .select('*')
    .in('asset_id', assetIds)
    .order('timestamp', { ascending: false });

  if (sessionsError) {
    console.error('Error fetching sessions:', sessionsError);
    // Continue without session data
  }

  // Get latest candles for price change calculation
  const { data: candles, error: candlesError } = await supabase
    .from('candles')
    .select('*')
    .in('asset_id', assetIds)
    .order('timestamp', { ascending: false })
    .limit(assetIds.length * 2); // 2 candles per asset for comparison

  if (candlesError) {
    console.error('Error fetching candles:', candlesError);
    // Continue without candle data
  }

  // Build scanner data
  const scannerData: ScannerAsset[] = assets.map((asset: Record<string, unknown>) => {
    const assetId = asset.id as string;

    // Find latest session for this asset
    const latestSession = sessions?.find(
      (s: Record<string, unknown>) => s.asset_id === assetId
    );

    // Find candles for price change
    const assetCandles = candles?.filter(
      (c: Record<string, unknown>) => c.asset_id === assetId
    ) || [];
    const latestCandle = assetCandles[0] as Record<string, unknown> | undefined;
    const previousCandle = assetCandles[1] as Record<string, unknown> | undefined;

    let priceChange15m = 0;
    if (latestCandle && previousCandle) {
      const latestClose = parseFloat(String(latestCandle.close));
      const previousClose = parseFloat(String(previousCandle.close));
      if (previousClose > 0) {
        priceChange15m = ((latestClose - previousClose) / previousClose) * 100;
      }
    }

    return {
      id: assetId,
      symbol: asset.symbol as string,
      lastPrice: parseFloat(String(asset.last_price)) || 0,
      priceChange15m,
      sentimentScore: latestSession?.sentiment_score
        ? Number(latestSession.sentiment_score)
        : null,
      technicalSignal: (latestSession?.technical_signal as string) ?? null,
      technicalStrength: latestSession?.technical_strength
        ? Number(latestSession.technical_strength)
        : null,
      lastSessionTime: latestSession?.timestamp
        ? new Date(latestSession.timestamp as string)
        : null,
    };
  });

  // Sort data
  return sortScannerData(
    scannerData,
    filters.sortBy || 'sentimentScore',
    filters.sortDirection || 'asc'
  );
}

/**
 * Sorts scanner data by the specified field and direction
 */
function sortScannerData(
  data: ScannerAsset[],
  sortBy: NonNullable<ScannerFilters['sortBy']>,
  direction: NonNullable<ScannerFilters['sortDirection']>
): ScannerAsset[] {
  return [...data].sort((a, b) => {
    let aVal: string | number | null = a[sortBy];
    let bVal: string | number | null = b[sortBy];

    // Handle null values - push to end
    if (aVal === null) return 1;
    if (bVal === null) return -1;

    // String comparison
    if (typeof aVal === 'string' && typeof bVal === 'string') {
      aVal = aVal.toLowerCase();
      bVal = bVal.toLowerCase();
    }

    if (direction === 'asc') {
      return aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
    } else {
      return aVal > bVal ? -1 : aVal < bVal ? 1 : 0;
    }
  });
}

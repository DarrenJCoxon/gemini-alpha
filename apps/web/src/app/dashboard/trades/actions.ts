'use server';

import { createClient } from '@/lib/supabase/server';
import { Trade, TradeWithMetrics } from '@/types/trade';

/**
 * Fetches all open trades with calculated metrics
 * @returns Array of trades with real-time metrics (P&L, distance to stop/TP)
 */
export async function fetchOpenTrades(): Promise<TradeWithMetrics[]> {
  const supabase = await createClient();

  const { data, error } = await supabase
    .from('trades')
    .select(`
      *,
      asset:assets (
        symbol,
        last_price
      )
    `)
    .eq('status', 'OPEN')
    .order('entry_time', { ascending: false });

  if (error) {
    console.error('Error fetching open trades:', error);
    throw new Error('Failed to fetch open trades');
  }

  // Transform and calculate metrics
  return (data || []).map((t: Record<string, unknown>) => {
    const asset = t.asset as { symbol: string; last_price: string | number } | null;
    const entryPrice = parseFloat(String(t.entry_price));
    const currentPrice = asset?.last_price ? parseFloat(String(asset.last_price)) : entryPrice;
    const size = parseFloat(String(t.size));
    const stopLossPrice = parseFloat(String(t.stop_loss_price));
    const takeProfitPrice = t.take_profit_price ? parseFloat(String(t.take_profit_price)) : null;
    const direction = (t.direction as string) || 'LONG';

    // Calculate P&L based on direction
    const priceChange = direction === 'LONG'
      ? currentPrice - entryPrice
      : entryPrice - currentPrice;

    const unrealizedPnl = priceChange * size;
    const unrealizedPnlPercent = (priceChange / entryPrice) * 100;

    // Distance to stop (for LONG: how far above stop, for SHORT: how far below stop)
    const distanceToStopPercent = direction === 'LONG'
      ? ((currentPrice - stopLossPrice) / currentPrice) * 100
      : ((stopLossPrice - currentPrice) / currentPrice) * 100;

    // Distance to take profit
    const distanceToTakeProfitPercent = takeProfitPrice
      ? direction === 'LONG'
        ? ((takeProfitPrice - currentPrice) / currentPrice) * 100
        : ((currentPrice - takeProfitPrice) / currentPrice) * 100
      : null;

    return {
      id: t.id as string,
      assetId: t.asset_id as string,
      status: t.status as TradeWithMetrics['status'],
      direction: direction as TradeWithMetrics['direction'],
      entryPrice,
      size,
      entryTime: new Date(t.entry_time as string),
      stopLossPrice,
      takeProfitPrice,
      exitPrice: t.exit_price ? parseFloat(String(t.exit_price)) : null,
      exitTime: t.exit_time ? new Date(t.exit_time as string) : null,
      pnl: t.pnl ? parseFloat(String(t.pnl)) : null,
      createdAt: new Date(t.created_at as string),
      updatedAt: new Date(t.updated_at as string),
      asset: asset ? {
        symbol: asset.symbol,
        lastPrice: parseFloat(String(asset.last_price)),
      } : undefined,
      currentPrice,
      unrealizedPnl,
      unrealizedPnlPercent,
      distanceToStopPercent,
      distanceToTakeProfitPercent,
    };
  });
}

/**
 * Fetches closed trade history
 * @param limit Maximum number of trades to return
 * @returns Array of closed trades
 */
export async function fetchTradeHistory(limit = 20): Promise<Trade[]> {
  const supabase = await createClient();

  const { data, error } = await supabase
    .from('trades')
    .select(`
      *,
      asset:assets (
        symbol,
        last_price
      )
    `)
    .in('status', ['CLOSED', 'STOPPED_OUT', 'TAKE_PROFIT'])
    .order('exit_time', { ascending: false })
    .limit(limit);

  if (error) {
    console.error('Error fetching trade history:', error);
    throw new Error('Failed to fetch trade history');
  }

  return (data || []).map((t: Record<string, unknown>) => {
    const asset = t.asset as { symbol: string; last_price: string | number } | null;

    return {
      id: t.id as string,
      assetId: t.asset_id as string,
      status: t.status as Trade['status'],
      direction: (t.direction as Trade['direction']) || 'LONG',
      entryPrice: parseFloat(String(t.entry_price)),
      size: parseFloat(String(t.size)),
      entryTime: new Date(t.entry_time as string),
      stopLossPrice: parseFloat(String(t.stop_loss_price)),
      takeProfitPrice: t.take_profit_price ? parseFloat(String(t.take_profit_price)) : null,
      exitPrice: t.exit_price ? parseFloat(String(t.exit_price)) : null,
      exitTime: t.exit_time ? new Date(t.exit_time as string) : null,
      pnl: t.pnl ? parseFloat(String(t.pnl)) : null,
      createdAt: new Date(t.created_at as string),
      updatedAt: new Date(t.updated_at as string),
      asset: asset ? {
        symbol: asset.symbol,
        lastPrice: parseFloat(String(asset.last_price)),
      } : undefined,
    };
  });
}

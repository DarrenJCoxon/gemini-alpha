'use client';

import { useEffect, useRef } from 'react';
import { subscribeToTable } from '@/lib/supabase/realtime';
import { Trade, TradeStatus, TradeDirection } from '@/types/trade';
import { toast } from 'sonner';

interface UseTradeListenerOptions {
  onTradeInsert?: (trade: Trade) => void;
  onTradeUpdate?: (trade: Trade) => void;
  onTradeDelete?: (tradeId: string) => void;
  showToasts?: boolean;
}

/**
 * Hook to listen for trade changes via Supabase Realtime.
 */
export function useTradeListener({
  onTradeInsert,
  onTradeUpdate,
  onTradeDelete,
  showToasts = true,
}: UseTradeListenerOptions) {
  const insertRef = useRef(onTradeInsert);
  const updateRef = useRef(onTradeUpdate);
  const deleteRef = useRef(onTradeDelete);

  // Keep refs updated
  useEffect(() => {
    insertRef.current = onTradeInsert;
    updateRef.current = onTradeUpdate;
    deleteRef.current = onTradeDelete;
  }, [onTradeInsert, onTradeUpdate, onTradeDelete]);

  useEffect(() => {
    // Subscribe to all trade changes
    const { unsubscribe } = subscribeToTable(
      'trades',
      '*',
      (payload) => {
        console.log('[TradeListener] Trade event:', payload.eventType, payload);

        const transformTrade = (record: Record<string, unknown>): Trade => ({
          id: record.id as string,
          assetId: record.asset_id as string,
          status: record.status as TradeStatus,
          direction: (record.direction as TradeDirection) || 'LONG',
          entryPrice: parseFloat(record.entry_price as string),
          size: parseFloat(record.size as string),
          entryTime: new Date(record.entry_time as string),
          stopLossPrice: parseFloat(record.stop_loss_price as string),
          takeProfitPrice: record.take_profit_price ? parseFloat(record.take_profit_price as string) : null,
          exitPrice: record.exit_price ? parseFloat(record.exit_price as string) : null,
          exitTime: record.exit_time ? new Date(record.exit_time as string) : null,
          pnl: record.pnl ? parseFloat(record.pnl as string) : null,
          createdAt: new Date(record.created_at as string),
          updatedAt: new Date(record.updated_at as string),
        });

        switch (payload.eventType) {
          case 'INSERT':
            if (insertRef.current && payload.new) {
              const trade = transformTrade(payload.new as Record<string, unknown>);
              insertRef.current(trade);

              if (showToasts) {
                toast.success(`Trade Opened: ${trade.assetId}`, {
                  description: `Entry: $${trade.entryPrice.toFixed(2)} | Size: ${trade.size.toFixed(4)}`,
                  duration: 6000,
                });
              }
            }
            break;

          case 'UPDATE':
            if (updateRef.current && payload.new) {
              const trade = transformTrade(payload.new as Record<string, unknown>);
              const oldStatus = (payload.old as Record<string, unknown> | undefined)?.status as string | undefined;
              const newStatus = trade.status;

              updateRef.current(trade);

              // Show toast for status changes
              if (showToasts && oldStatus !== newStatus) {
                showTradeStatusToast(trade, oldStatus, newStatus);
              }
            }
            break;

          case 'DELETE':
            if (deleteRef.current && payload.old) {
              deleteRef.current((payload.old as Record<string, unknown>).id as string);
            }
            break;
        }
      }
    );

    return () => {
      unsubscribe();
    };
  }, [showToasts]);
}

function showTradeStatusToast(trade: Trade, oldStatus: string | undefined, newStatus: TradeStatus) {
  switch (newStatus) {
    case 'STOPPED_OUT':
      toast.error(`Trade Stopped Out: ${trade.assetId}`, {
        description: `P&L: $${trade.pnl?.toFixed(2) || '0.00'}`,
        duration: 8000,
      });
      break;

    case 'TAKE_PROFIT':
      toast.success(`Take Profit Hit: ${trade.assetId}`, {
        description: `P&L: +$${trade.pnl?.toFixed(2) || '0.00'}`,
        duration: 8000,
      });
      break;

    case 'CLOSED':
      const isProfit = (trade.pnl || 0) >= 0;
      if (isProfit) {
        toast.success(`Trade Closed: ${trade.assetId}`, {
          description: `P&L: +$${trade.pnl?.toFixed(2) || '0.00'}`,
          duration: 6000,
        });
      } else {
        toast.warning(`Trade Closed: ${trade.assetId}`, {
          description: `P&L: $${trade.pnl?.toFixed(2) || '0.00'}`,
          duration: 6000,
        });
      }
      break;
  }
}

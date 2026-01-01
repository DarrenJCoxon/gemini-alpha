'use client';

import { Badge } from '@/components/ui/badge';
import { Wifi, WifiOff, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useRealtimeStatus, RealtimeStatus } from '@/hooks/use-realtime-status';

/**
 * Displays the current Supabase Realtime connection status.
 * Shows different states: connecting, connected, disconnected, error
 */
export function RealtimeStatusIndicator() {
  const status = useRealtimeStatus();

  const config: Record<
    RealtimeStatus,
    { icon: React.ReactNode; text: string; className: string }
  > = {
    connecting: {
      icon: <Loader2 className="h-3 w-3 animate-spin" />,
      text: 'Connecting',
      className: 'border-amber-500/50 text-amber-500',
    },
    connected: {
      icon: <Wifi className="h-3 w-3" />,
      text: 'Live',
      className: 'border-emerald-500/50 text-emerald-500',
    },
    disconnected: {
      icon: <WifiOff className="h-3 w-3" />,
      text: 'Offline',
      className: 'border-rose-500/50 text-rose-500',
    },
    error: {
      icon: <WifiOff className="h-3 w-3" />,
      text: 'Error',
      className: 'border-rose-500/50 text-rose-500',
    },
  };

  const { icon, text, className } = config[status];

  return (
    <Badge
      variant="outline"
      className={cn('gap-1.5 text-xs', className)}
      aria-label={`Realtime connection: ${text}`}
      data-testid="realtime-status-indicator"
      data-status={status}
    >
      {icon}
      {text}
    </Badge>
  );
}

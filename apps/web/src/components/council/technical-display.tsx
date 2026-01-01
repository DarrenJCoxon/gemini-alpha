import { cn } from '@/lib/utils';
import { TrendingUp, TrendingDown, Minus, BarChart3 } from 'lucide-react';
import { TechnicalDetails } from '@/types/council';

interface TechnicalDisplayProps {
  signal: string;
  strength: number;
  details: TechnicalDetails | null;
  className?: string;
}

/**
 * Gets the appropriate icon component for the signal
 */
export function getSignalIcon(signal: string) {
  if (signal === 'BULLISH') return TrendingUp;
  if (signal === 'BEARISH') return TrendingDown;
  return Minus;
}

/**
 * Gets the color class for the signal
 */
export function getSignalColor(signal: string): string {
  if (signal === 'BULLISH') return 'text-emerald-500';
  if (signal === 'BEARISH') return 'text-rose-500';
  return 'text-zinc-400';
}

/**
 * Gets the strength bar color class for the signal
 */
export function getStrengthBarColor(signal: string): string {
  if (signal === 'BULLISH') return 'bg-emerald-500';
  if (signal === 'BEARISH') return 'bg-rose-500';
  return 'bg-zinc-500';
}

/**
 * Gets the RSI color class based on value
 * RSI < 30 = oversold (green), RSI > 70 = overbought (red)
 */
export function getRsiColor(rsi: number): string {
  if (rsi < 30) return 'text-emerald-500';
  if (rsi > 70) return 'text-rose-500';
  return 'text-zinc-100';
}

export function TechnicalDisplay({
  signal,
  strength,
  details,
  className,
}: TechnicalDisplayProps) {
  const SignalIcon = getSignalIcon(signal);
  const signalColor = getSignalColor(signal);
  const strengthBarColor = getStrengthBarColor(signal);

  return (
    <div className={cn('space-y-3', className)} data-testid="technical-display">
      <div className="flex items-center gap-2">
        <BarChart3 className="h-4 w-4 text-zinc-400" aria-hidden="true" />
        <span className="text-sm text-zinc-400">Technical</span>
        <div className={cn('flex items-center gap-1 ml-auto', signalColor)}>
          <SignalIcon className="h-4 w-4" aria-hidden="true" />
          <span className="font-mono text-sm" data-testid="technical-signal">
            {signal}
          </span>
        </div>
      </div>

      {/* Strength bar */}
      <div className="space-y-1">
        <div className="flex justify-between text-xs">
          <span className="text-zinc-500">Strength</span>
          <span className="font-mono text-zinc-400" data-testid="technical-strength">
            {strength}%
          </span>
        </div>
        <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
          <div
            className={cn('h-full transition-all', strengthBarColor)}
            style={{ width: `${Math.min(Math.max(strength, 0), 100)}%` }}
            role="progressbar"
            aria-valuenow={strength}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`Technical strength: ${strength}%`}
            data-testid="strength-progress"
          />
        </div>
      </div>

      {/* Technical details */}
      {details && (
        <div className="grid grid-cols-2 gap-2 text-xs font-mono" data-testid="technical-details">
          {details.rsi !== null && (
            <div className="flex justify-between">
              <span className="text-zinc-500">RSI:</span>
              <span className={getRsiColor(details.rsi)} data-testid="rsi-value">
                {details.rsi.toFixed(1)}
              </span>
            </div>
          )}
          {details.sma_50 !== null && (
            <div className="flex justify-between">
              <span className="text-zinc-500">SMA50:</span>
              <span className="text-zinc-100" data-testid="sma50-value">
                ${details.sma_50.toFixed(2)}
              </span>
            </div>
          )}
          {details.sma_200 !== null && (
            <div className="flex justify-between">
              <span className="text-zinc-500">SMA200:</span>
              <span className="text-zinc-100" data-testid="sma200-value">
                ${details.sma_200.toFixed(2)}
              </span>
            </div>
          )}
          {details.volume_delta !== null && (
            <div className="flex justify-between">
              <span className="text-zinc-500">Vol Delta:</span>
              <span
                className={cn(
                  details.volume_delta > 0 ? 'text-emerald-500' : 'text-rose-500'
                )}
                data-testid="volume-delta-value"
              >
                {details.volume_delta > 0 ? '+' : ''}
                {details.volume_delta.toFixed(1)}%
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

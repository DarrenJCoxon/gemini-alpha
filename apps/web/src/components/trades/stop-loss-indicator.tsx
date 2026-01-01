import { cn } from '@/lib/utils';

interface StopLossIndicatorProps {
  entryPrice: number;
  currentPrice: number;
  stopLossPrice: number;
  takeProfitPrice?: number | null;
  direction?: 'LONG' | 'SHORT';
  className?: string;
}

/**
 * Visual indicator showing current price position relative to stop loss and take profit.
 * For LONG positions: stop loss is below entry, take profit above.
 * For SHORT positions: stop loss is above entry, take profit below.
 */
export function StopLossIndicator({
  entryPrice,
  currentPrice,
  stopLossPrice,
  takeProfitPrice,
  direction = 'LONG',
  className,
}: StopLossIndicatorProps) {
  // Calculate the range for the progress bar
  // Range: stopLoss (0%) to takeProfit (100%), entry in middle
  let range: number;
  let effectiveMax: number;

  if (direction === 'LONG') {
    // For LONG: stop is below entry, TP is above
    range = takeProfitPrice
      ? takeProfitPrice - stopLossPrice
      : (entryPrice - stopLossPrice) * 2; // Double distance to stop if no TP
    effectiveMax = takeProfitPrice || entryPrice + (entryPrice - stopLossPrice);
  } else {
    // For SHORT: stop is above entry, TP is below
    // Invert the visualization
    range = takeProfitPrice
      ? stopLossPrice - takeProfitPrice
      : (stopLossPrice - entryPrice) * 2;
    effectiveMax = stopLossPrice;
  }

  // Calculate positions as percentages
  let entryPercent: number;
  let currentPercent: number;

  if (direction === 'LONG') {
    entryPercent = ((entryPrice - stopLossPrice) / range) * 100;
    currentPercent = ((currentPrice - stopLossPrice) / range) * 100;
  } else {
    // For SHORT, invert the scale
    const min = takeProfitPrice || entryPrice - (stopLossPrice - entryPrice);
    entryPercent = ((stopLossPrice - entryPrice) / range) * 100;
    currentPercent = ((stopLossPrice - currentPrice) / range) * 100;
  }

  // Clamp current price indicator between 0-100
  const clampedCurrent = Math.max(0, Math.min(100, currentPercent));

  // Determine if in profit or loss based on direction
  const isProfit = direction === 'LONG'
    ? currentPrice >= entryPrice
    : currentPrice <= entryPrice;

  // Labels for stop and TP based on direction
  const stopLabel = direction === 'LONG' ? 'Stop' : 'Stop';
  const tpLabel = direction === 'LONG' ? 'TP' : 'TP';

  return (
    <div className={cn('space-y-1', className)}>
      <div className="flex justify-between text-xs font-mono text-zinc-500">
        <span>{stopLabel}: ${stopLossPrice.toFixed(2)}</span>
        {takeProfitPrice && <span>{tpLabel}: ${takeProfitPrice.toFixed(2)}</span>}
      </div>

      <div
        className="relative h-3 bg-zinc-800 rounded-full overflow-hidden"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={clampedCurrent}
        aria-label={`Price position: ${clampedCurrent.toFixed(0)}% from stop loss`}
      >
        {/* Entry marker */}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-zinc-400 z-10"
          style={{ left: `${entryPercent}%` }}
          title={`Entry: $${entryPrice.toFixed(2)}`}
        />

        {/* Current position fill */}
        <div
          className={cn(
            'absolute top-0 bottom-0 left-0 transition-all duration-300',
            isProfit ? 'bg-emerald-500/50' : 'bg-rose-500/50'
          )}
          style={{ width: `${clampedCurrent}%` }}
        />

        {/* Current price marker */}
        <div
          className={cn(
            'absolute top-0 bottom-0 w-1 rounded-full z-20 transition-all duration-300',
            isProfit ? 'bg-emerald-500' : 'bg-rose-500'
          )}
          style={{ left: `${clampedCurrent}%`, transform: 'translateX(-50%)' }}
          title={`Current: $${currentPrice.toFixed(2)}`}
        />
      </div>

      <div className="flex justify-between text-xs">
        <span className="text-rose-500">Risk Zone</span>
        <span className="text-emerald-500">Profit Zone</span>
      </div>
    </div>
  );
}

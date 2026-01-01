import { cn } from '@/lib/utils';
import { Twitter } from 'lucide-react';

interface SentimentIndicatorProps {
  score: number; // 0-100 (0 = extreme fear, 100 = extreme greed)
  className?: string;
}

/**
 * Determines sentiment label based on score
 */
export function getSentimentLabel(score: number): string {
  if (score < 20) return 'Extreme Fear';
  if (score < 40) return 'Fear';
  if (score < 60) return 'Neutral';
  if (score < 80) return 'Greed';
  return 'Extreme Greed';
}

/**
 * Gets color class based on sentiment score
 * Lower scores (fear) are green (buying opportunity)
 * Higher scores (greed) are red (selling opportunity)
 */
export function getSentimentColor(score: number): string {
  if (score < 20) return 'bg-emerald-500';
  if (score < 40) return 'bg-emerald-400';
  if (score < 60) return 'bg-zinc-400';
  if (score < 80) return 'bg-rose-400';
  return 'bg-rose-500';
}

export function SentimentIndicator({
  score,
  className,
}: SentimentIndicatorProps) {
  const label = getSentimentLabel(score);
  const colorClass = getSentimentColor(score);

  return (
    <div className={cn('space-y-2', className)} data-testid="sentiment-indicator">
      <div className="flex items-center gap-2">
        <Twitter className="h-4 w-4 text-zinc-400" aria-hidden="true" />
        <span className="text-sm text-zinc-400">Sentiment</span>
        <span className="ml-auto font-mono text-sm text-zinc-100">
          {score}/100
        </span>
      </div>
      <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className={cn('h-full transition-all', colorClass)}
          style={{ width: `${Math.min(Math.max(score, 0), 100)}%` }}
          role="progressbar"
          aria-valuenow={score}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Sentiment score: ${score} - ${label}`}
          data-testid="sentiment-progress"
        />
      </div>
      <span className="text-xs text-zinc-500" data-testid="sentiment-label">
        {label}
      </span>
    </div>
  );
}

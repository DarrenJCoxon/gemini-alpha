import { cn } from '@/lib/utils';
import { Eye, CheckCircle, XCircle } from 'lucide-react';

interface VisionDisplayProps {
  analysis: string | null;
  confidence: number;
  isValid: boolean;
  className?: string;
}

export function VisionDisplay({
  analysis,
  confidence,
  isValid,
  className,
}: VisionDisplayProps) {
  return (
    <div className={cn('space-y-2', className)} data-testid="vision-display">
      <div className="flex items-center gap-2">
        <Eye className="h-4 w-4 text-zinc-400" aria-hidden="true" />
        <span className="text-sm text-zinc-400">Chart Vision</span>
        <div className="flex items-center gap-1 ml-auto">
          {isValid ? (
            <CheckCircle
              className="h-4 w-4 text-emerald-500"
              aria-hidden="true"
              data-testid="valid-icon"
            />
          ) : (
            <XCircle
              className="h-4 w-4 text-rose-500"
              aria-hidden="true"
              data-testid="invalid-icon"
            />
          )}
          <span
            className={cn(
              'text-xs font-mono',
              isValid ? 'text-emerald-500' : 'text-rose-500'
            )}
            data-testid="validity-label"
          >
            {isValid ? 'Valid' : 'Invalid'}
          </span>
        </div>
      </div>

      <div className="flex justify-between text-xs">
        <span className="text-zinc-500">Confidence</span>
        <span className="font-mono text-zinc-400" data-testid="vision-confidence">
          {confidence}%
        </span>
      </div>

      {analysis && (
        <p
          className="text-xs text-zinc-400 leading-relaxed"
          data-testid="vision-analysis"
        >
          {analysis}
        </p>
      )}
    </div>
  );
}

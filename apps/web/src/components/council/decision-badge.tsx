import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { DecisionType } from '@/types/council';

interface DecisionBadgeProps {
  decision: DecisionType;
  confidence?: number;
  className?: string;
}

const decisionStyles: Record<DecisionType, string> = {
  BUY: 'bg-emerald-500/20 text-emerald-500 border-emerald-500/50',
  SELL: 'bg-rose-500/20 text-rose-500 border-rose-500/50',
  HOLD: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/50',
};

export function DecisionBadge({
  decision,
  confidence,
  className,
}: DecisionBadgeProps) {
  return (
    <Badge
      variant="outline"
      className={cn(decisionStyles[decision], className)}
      data-testid="decision-badge"
    >
      {decision}
      {confidence !== undefined && (
        <span className="ml-1 opacity-70">({confidence}%)</span>
      )}
    </Badge>
  );
}

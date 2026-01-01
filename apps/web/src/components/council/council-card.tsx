'use client';

import { useState } from 'react';
import { formatDistanceToNow, format } from 'date-fns';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import { CouncilSession, TechnicalDetails } from '@/types/council';
import { DecisionBadge } from './decision-badge';
import { SentimentIndicator } from './sentiment-indicator';
import { TechnicalDisplay } from './technical-display';
import { VisionDisplay } from './vision-display';

interface CouncilCardProps {
  session: CouncilSession;
  isNew?: boolean; // For animation on realtime updates
  className?: string;
}

const borderColors = {
  BUY: 'border-l-emerald-500',
  SELL: 'border-l-rose-500',
  HOLD: 'border-l-zinc-500',
} as const;

/**
 * Safely parses technical details JSON string
 */
function parseTechnicalDetails(
  detailsString: string | null
): TechnicalDetails | null {
  if (!detailsString) return null;

  try {
    return JSON.parse(detailsString) as TechnicalDetails;
  } catch (error) {
    console.error('Failed to parse technical details:', error);
    return null;
  }
}

export function CouncilCard({ session, isNew, className }: CouncilCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Parse technical details JSON
  const technicalDetails = parseTechnicalDetails(session.technicalDetails);

  // Border color based on decision
  const borderColor = borderColors[session.finalDecision];

  // Truncate long reasoning for summary
  const reasoningSummary =
    session.reasoningLog.length > 200
      ? `${session.reasoningLog.slice(0, 200)}...`
      : session.reasoningLog;

  return (
    <Card
      className={cn(
        'bg-zinc-900 border-zinc-800 border-l-4 transition-all duration-300',
        borderColor,
        isNew && 'animate-slide-in-from-top',
        className
      )}
      data-testid="council-card"
    >
      <CardHeader className="p-4 pb-2">
        {/* Header: Asset + Time + Decision */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span
              className="font-semibold text-zinc-100 font-mono"
              data-testid="asset-symbol"
            >
              {session.asset?.symbol || session.assetId}
            </span>
            <time
              dateTime={session.timestamp.toISOString()}
              className="text-xs text-zinc-500"
              title={format(session.timestamp, 'PPpp')}
              data-testid="session-time"
            >
              {formatDistanceToNow(session.timestamp, { addSuffix: true })}
            </time>
          </div>
          <DecisionBadge
            decision={session.finalDecision}
            confidence={session.decisionConfidence}
          />
        </div>
      </CardHeader>

      <CardContent className="p-4 pt-0">
        {/* Master Node Reasoning Summary */}
        <p
          className="text-sm text-zinc-300 leading-relaxed mb-4 font-mono"
          data-testid="reasoning-summary"
        >
          {reasoningSummary}
        </p>

        {/* Expandable Agent Details */}
        <Accordion
          type="single"
          collapsible
          value={isExpanded ? 'details' : ''}
          onValueChange={(v) => setIsExpanded(v === 'details')}
        >
          <AccordionItem value="details" className="border-zinc-800">
            <AccordionTrigger
              className="text-sm text-zinc-400 hover:text-zinc-100 py-2"
              data-testid="accordion-trigger"
            >
              Agent Analysis Details
            </AccordionTrigger>
            <AccordionContent className="space-y-4 pt-2">
              {/* Sentiment Analysis */}
              <SentimentIndicator score={session.sentimentScore} />

              <Separator className="bg-zinc-800" />

              {/* Technical Analysis */}
              <TechnicalDisplay
                signal={session.technicalSignal}
                strength={session.technicalStrength}
                details={technicalDetails}
              />

              <Separator className="bg-zinc-800" />

              {/* Vision Analysis */}
              <VisionDisplay
                analysis={session.visionAnalysis}
                confidence={session.visionConfidence}
                isValid={session.visionValid}
              />

              {/* Full Reasoning Log (if long) */}
              {session.reasoningLog.length > 200 && (
                <>
                  <Separator className="bg-zinc-800" />
                  <div className="space-y-2">
                    <span className="text-sm text-zinc-400">Full Reasoning</span>
                    <pre
                      className="text-xs text-zinc-300 font-mono whitespace-pre-wrap bg-zinc-950 p-3 rounded-md max-h-48 overflow-y-auto"
                      data-testid="full-reasoning"
                    >
                      {session.reasoningLog}
                    </pre>
                  </div>
                </>
              )}
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </CardContent>
    </Card>
  );
}

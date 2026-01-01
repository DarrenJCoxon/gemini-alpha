'use client';

import { useEffect, useRef } from 'react';
import { subscribeToTable } from '@/lib/supabase/realtime';
import { CouncilSession, DecisionType } from '@/types/council';
import { toast } from 'sonner';

interface UseCouncilListenerOptions {
  onNewSession: (session: CouncilSession) => void;
  showToasts?: boolean;
}

/**
 * Hook to listen for new council session inserts via Supabase Realtime.
 */
export function useCouncilListener({
  onNewSession,
  showToasts = true,
}: UseCouncilListenerOptions) {
  const callbackRef = useRef(onNewSession);

  // Keep callback ref updated
  useEffect(() => {
    callbackRef.current = onNewSession;
  }, [onNewSession]);

  useEffect(() => {
    const { unsubscribe } = subscribeToTable(
      'council_sessions',
      'INSERT',
      (payload) => {
        console.log('[CouncilListener] New session received:', payload);

        const newRecord = payload.new as Record<string, unknown> | undefined;
        if (!newRecord) return;

        // Transform to CouncilSession type
        const session: CouncilSession = {
          id: newRecord.id as string,
          assetId: newRecord.asset_id as string,
          timestamp: new Date(newRecord.timestamp as string),
          sentimentScore: newRecord.sentiment_score as number,
          technicalSignal: newRecord.technical_signal as string,
          technicalStrength: newRecord.technical_strength as number,
          technicalDetails: newRecord.technical_details as string | null,
          visionAnalysis: newRecord.vision_analysis as string | null,
          visionConfidence: newRecord.vision_confidence as number,
          visionValid: newRecord.vision_valid as boolean,
          finalDecision: newRecord.final_decision as DecisionType,
          decisionConfidence: newRecord.decision_confidence as number,
          reasoningLog: newRecord.reasoning_log as string,
          createdAt: new Date(newRecord.created_at as string),
          // Asset will be fetched separately or passed
          asset: undefined,
        };

        // Trigger callback
        callbackRef.current(session);

        // Show toast notification
        if (showToasts) {
          showSessionToast(session);
        }
      }
    );

    return () => {
      unsubscribe();
    };
  }, [showToasts]);
}

function showSessionToast(session: CouncilSession) {
  const decision = session.finalDecision;
  const assetSymbol = session.asset?.symbol || session.assetId;

  switch (decision) {
    case 'BUY':
      toast.success(`New BUY Signal: ${assetSymbol}`, {
        description: `Fear Score: ${session.sentimentScore} | Confidence: ${session.decisionConfidence}%`,
        duration: 8000,
      });
      break;

    case 'SELL':
      toast.error(`SELL Signal: ${assetSymbol}`, {
        description: `Confidence: ${session.decisionConfidence}%`,
        duration: 8000,
      });
      break;

    case 'HOLD':
      // Only show HOLD toasts for significant decisions
      if (session.decisionConfidence > 70) {
        toast.info(`Council Decision: HOLD ${assetSymbol}`, {
          description: session.reasoningLog.slice(0, 100) + '...',
          duration: 5000,
        });
      }
      break;
  }
}

/**
 * @jest-environment jsdom
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { CouncilCard } from '@/components/council/council-card';
import { CouncilSession } from '@/types/council';

// Mock date-fns to control time formatting
jest.mock('date-fns', () => ({
  formatDistanceToNow: jest.fn(() => '2 hours ago'),
  format: jest.fn(() => 'Jan 1, 2024, 12:00 PM'),
}));

describe('CouncilCard Component', () => {
  const createMockSession = (
    overrides: Partial<CouncilSession> = {}
  ): CouncilSession => ({
    id: 'test-session-1',
    assetId: 'asset-1',
    timestamp: new Date('2024-01-01T12:00:00Z'),
    sentimentScore: 45,
    technicalSignal: 'BULLISH',
    technicalStrength: 75,
    technicalDetails: JSON.stringify({
      rsi: 55,
      sma_50: 45000,
      sma_200: 42000,
      volume_delta: 10,
      reasoning: 'Test reasoning',
    }),
    visionAnalysis: 'Chart shows upward trend',
    visionConfidence: 85,
    visionValid: true,
    finalDecision: 'BUY',
    decisionConfidence: 80,
    reasoningLog: 'Market conditions favor buying based on technical and sentiment analysis.',
    createdAt: new Date('2024-01-01T12:00:00Z'),
    asset: {
      symbol: 'BTC/USD',
      lastPrice: 45000,
    },
    ...overrides,
  });

  describe('Header Rendering', () => {
    it('should display asset symbol', () => {
      const session = createMockSession();
      render(<CouncilCard session={session} />);

      expect(screen.getByTestId('asset-symbol')).toHaveTextContent('BTC/USD');
    });

    it('should fallback to assetId when symbol not available', () => {
      const session = createMockSession({ asset: undefined });
      render(<CouncilCard session={session} />);

      expect(screen.getByTestId('asset-symbol')).toHaveTextContent('asset-1');
    });

    it('should display timestamp', () => {
      const session = createMockSession();
      render(<CouncilCard session={session} />);

      expect(screen.getByTestId('session-time')).toHaveTextContent('2 hours ago');
    });

    it('should render decision badge', () => {
      const session = createMockSession();
      render(<CouncilCard session={session} />);

      expect(screen.getByTestId('decision-badge')).toHaveTextContent('BUY');
    });
  });

  describe('Border Styling', () => {
    it('should have emerald border for BUY decision', () => {
      const session = createMockSession({ finalDecision: 'BUY' });
      render(<CouncilCard session={session} />);

      const card = screen.getByTestId('council-card');
      expect(card).toHaveClass('border-l-emerald-500');
    });

    it('should have rose border for SELL decision', () => {
      const session = createMockSession({ finalDecision: 'SELL' });
      render(<CouncilCard session={session} />);

      const card = screen.getByTestId('council-card');
      expect(card).toHaveClass('border-l-rose-500');
    });

    it('should have zinc border for HOLD decision', () => {
      const session = createMockSession({ finalDecision: 'HOLD' });
      render(<CouncilCard session={session} />);

      const card = screen.getByTestId('council-card');
      expect(card).toHaveClass('border-l-zinc-500');
    });
  });

  describe('Reasoning Display', () => {
    it('should display reasoning summary', () => {
      const session = createMockSession();
      render(<CouncilCard session={session} />);

      expect(screen.getByTestId('reasoning-summary')).toHaveTextContent(
        'Market conditions favor buying'
      );
    });

    it('should truncate long reasoning in summary', () => {
      const longReasoning = 'A'.repeat(300);
      const session = createMockSession({ reasoningLog: longReasoning });
      render(<CouncilCard session={session} />);

      const summary = screen.getByTestId('reasoning-summary');
      expect(summary.textContent?.length).toBeLessThan(210);
      expect(summary).toHaveTextContent('...');
    });
  });

  describe('Accordion Functionality', () => {
    it('should have accordion trigger', () => {
      const session = createMockSession();
      render(<CouncilCard session={session} />);

      expect(screen.getByTestId('accordion-trigger')).toBeInTheDocument();
    });

    it('should expand accordion when clicked', () => {
      const session = createMockSession();
      render(<CouncilCard session={session} />);

      const trigger = screen.getByTestId('accordion-trigger');
      fireEvent.click(trigger);

      // After expansion, sentiment indicator should be visible
      expect(screen.getByTestId('sentiment-indicator')).toBeInTheDocument();
    });

    it('should show technical display when expanded', () => {
      const session = createMockSession();
      render(<CouncilCard session={session} />);

      fireEvent.click(screen.getByTestId('accordion-trigger'));

      expect(screen.getByTestId('technical-display')).toBeInTheDocument();
    });

    it('should show vision display when expanded', () => {
      const session = createMockSession();
      render(<CouncilCard session={session} />);

      fireEvent.click(screen.getByTestId('accordion-trigger'));

      expect(screen.getByTestId('vision-display')).toBeInTheDocument();
    });
  });

  describe('Full Reasoning Log', () => {
    it('should show full reasoning section for long logs when expanded', () => {
      const longReasoning = 'A'.repeat(300);
      const session = createMockSession({ reasoningLog: longReasoning });
      render(<CouncilCard session={session} />);

      fireEvent.click(screen.getByTestId('accordion-trigger'));

      expect(screen.getByTestId('full-reasoning')).toBeInTheDocument();
      expect(screen.getByTestId('full-reasoning')).toHaveTextContent(longReasoning);
    });

    it('should not show full reasoning section for short logs', () => {
      const shortReasoning = 'Short reasoning';
      const session = createMockSession({ reasoningLog: shortReasoning });
      render(<CouncilCard session={session} />);

      fireEvent.click(screen.getByTestId('accordion-trigger'));

      expect(screen.queryByTestId('full-reasoning')).not.toBeInTheDocument();
    });
  });

  describe('Technical Details Parsing', () => {
    it('should handle valid JSON technical details', () => {
      const session = createMockSession();
      render(<CouncilCard session={session} />);

      fireEvent.click(screen.getByTestId('accordion-trigger'));

      expect(screen.getByTestId('rsi-value')).toHaveTextContent('55.0');
    });

    it('should handle null technical details', () => {
      const session = createMockSession({ technicalDetails: null });
      render(<CouncilCard session={session} />);

      fireEvent.click(screen.getByTestId('accordion-trigger'));

      expect(screen.queryByTestId('technical-details')).not.toBeInTheDocument();
    });

    it('should handle invalid JSON gracefully', () => {
      // Suppress console.error for this test
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

      const session = createMockSession({ technicalDetails: 'invalid json' });

      // Should not throw error
      expect(() => render(<CouncilCard session={session} />)).not.toThrow();

      consoleSpy.mockRestore();
    });
  });

  describe('Animation', () => {
    it('should apply animation class when isNew is true', () => {
      const session = createMockSession();
      render(<CouncilCard session={session} isNew={true} />);

      const card = screen.getByTestId('council-card');
      expect(card).toHaveClass('animate-slide-in-from-top');
    });

    it('should not apply animation class when isNew is false', () => {
      const session = createMockSession();
      render(<CouncilCard session={session} isNew={false} />);

      const card = screen.getByTestId('council-card');
      expect(card).not.toHaveClass('animate-slide-in-from-top');
    });
  });

  describe('Custom Styling', () => {
    it('should accept additional className', () => {
      const session = createMockSession();
      render(<CouncilCard session={session} className="custom-class" />);

      const card = screen.getByTestId('council-card');
      expect(card).toHaveClass('custom-class');
    });
  });
});

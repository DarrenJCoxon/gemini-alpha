/**
 * @jest-environment jsdom
 */

import { render, screen } from '@testing-library/react';
import { DecisionBadge } from '@/components/council/decision-badge';

describe('DecisionBadge Component', () => {
  describe('Decision Type Rendering', () => {
    it('should render BUY decision with correct text', () => {
      render(<DecisionBadge decision="BUY" />);

      const badge = screen.getByTestId('decision-badge');
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveTextContent('BUY');
    });

    it('should render SELL decision with correct text', () => {
      render(<DecisionBadge decision="SELL" />);

      const badge = screen.getByTestId('decision-badge');
      expect(badge).toHaveTextContent('SELL');
    });

    it('should render HOLD decision with correct text', () => {
      render(<DecisionBadge decision="HOLD" />);

      const badge = screen.getByTestId('decision-badge');
      expect(badge).toHaveTextContent('HOLD');
    });
  });

  describe('Styling', () => {
    it('should apply emerald styling for BUY decision', () => {
      render(<DecisionBadge decision="BUY" />);

      const badge = screen.getByTestId('decision-badge');
      expect(badge).toHaveClass('bg-emerald-500/20');
      expect(badge).toHaveClass('text-emerald-500');
      expect(badge).toHaveClass('border-emerald-500/50');
    });

    it('should apply rose styling for SELL decision', () => {
      render(<DecisionBadge decision="SELL" />);

      const badge = screen.getByTestId('decision-badge');
      expect(badge).toHaveClass('bg-rose-500/20');
      expect(badge).toHaveClass('text-rose-500');
      expect(badge).toHaveClass('border-rose-500/50');
    });

    it('should apply zinc styling for HOLD decision', () => {
      render(<DecisionBadge decision="HOLD" />);

      const badge = screen.getByTestId('decision-badge');
      expect(badge).toHaveClass('bg-zinc-500/20');
      expect(badge).toHaveClass('text-zinc-400');
      expect(badge).toHaveClass('border-zinc-500/50');
    });
  });

  describe('Confidence Display', () => {
    it('should display confidence percentage when provided', () => {
      render(<DecisionBadge decision="BUY" confidence={85} />);

      const badge = screen.getByTestId('decision-badge');
      expect(badge).toHaveTextContent('(85%)');
    });

    it('should display 0% confidence correctly', () => {
      render(<DecisionBadge decision="HOLD" confidence={0} />);

      const badge = screen.getByTestId('decision-badge');
      expect(badge).toHaveTextContent('(0%)');
    });

    it('should not display confidence when not provided', () => {
      render(<DecisionBadge decision="SELL" />);

      const badge = screen.getByTestId('decision-badge');
      expect(badge).not.toHaveTextContent('%');
    });
  });

  describe('Custom Styling', () => {
    it('should accept additional className', () => {
      render(<DecisionBadge decision="BUY" className="custom-class" />);

      const badge = screen.getByTestId('decision-badge');
      expect(badge).toHaveClass('custom-class');
    });

    it('should merge custom className with default styles', () => {
      render(<DecisionBadge decision="BUY" className="test-class" />);

      const badge = screen.getByTestId('decision-badge');
      expect(badge).toHaveClass('test-class');
      expect(badge).toHaveClass('bg-emerald-500/20');
    });
  });
});

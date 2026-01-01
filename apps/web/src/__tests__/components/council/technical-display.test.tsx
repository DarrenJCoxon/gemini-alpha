/**
 * @jest-environment jsdom
 */

import { render, screen } from '@testing-library/react';
import {
  TechnicalDisplay,
  getSignalIcon,
  getSignalColor,
  getStrengthBarColor,
  getRsiColor,
} from '@/components/council/technical-display';
import { TechnicalDetails } from '@/types/council';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

describe('TechnicalDisplay Component', () => {
  const mockDetails: TechnicalDetails = {
    rsi: 55.5,
    sma_50: 43500.25,
    sma_200: 42000.00,
    volume_delta: 15.3,
    reasoning: 'RSI indicates neutral momentum',
  };

  describe('getSignalIcon', () => {
    it('should return TrendingUp for BULLISH signal', () => {
      expect(getSignalIcon('BULLISH')).toBe(TrendingUp);
    });

    it('should return TrendingDown for BEARISH signal', () => {
      expect(getSignalIcon('BEARISH')).toBe(TrendingDown);
    });

    it('should return Minus for NEUTRAL signal', () => {
      expect(getSignalIcon('NEUTRAL')).toBe(Minus);
    });

    it('should return Minus for unknown signal', () => {
      expect(getSignalIcon('UNKNOWN')).toBe(Minus);
    });
  });

  describe('getSignalColor', () => {
    it('should return emerald color for BULLISH signal', () => {
      expect(getSignalColor('BULLISH')).toBe('text-emerald-500');
    });

    it('should return rose color for BEARISH signal', () => {
      expect(getSignalColor('BEARISH')).toBe('text-rose-500');
    });

    it('should return zinc color for NEUTRAL signal', () => {
      expect(getSignalColor('NEUTRAL')).toBe('text-zinc-400');
    });
  });

  describe('getStrengthBarColor', () => {
    it('should return emerald background for BULLISH signal', () => {
      expect(getStrengthBarColor('BULLISH')).toBe('bg-emerald-500');
    });

    it('should return rose background for BEARISH signal', () => {
      expect(getStrengthBarColor('BEARISH')).toBe('bg-rose-500');
    });

    it('should return zinc background for NEUTRAL signal', () => {
      expect(getStrengthBarColor('NEUTRAL')).toBe('bg-zinc-500');
    });
  });

  describe('getRsiColor', () => {
    it('should return emerald for oversold RSI (< 30)', () => {
      expect(getRsiColor(25)).toBe('text-emerald-500');
      expect(getRsiColor(0)).toBe('text-emerald-500');
    });

    it('should return rose for overbought RSI (> 70)', () => {
      expect(getRsiColor(75)).toBe('text-rose-500');
      expect(getRsiColor(100)).toBe('text-rose-500');
    });

    it('should return neutral color for normal RSI (30-70)', () => {
      expect(getRsiColor(50)).toBe('text-zinc-100');
      expect(getRsiColor(30)).toBe('text-zinc-100');
      expect(getRsiColor(70)).toBe('text-zinc-100');
    });
  });

  describe('Rendering', () => {
    it('should render signal type', () => {
      render(
        <TechnicalDisplay signal="BULLISH" strength={75} details={null} />
      );

      expect(screen.getByTestId('technical-signal')).toHaveTextContent('BULLISH');
    });

    it('should render strength percentage', () => {
      render(
        <TechnicalDisplay signal="BULLISH" strength={75} details={null} />
      );

      expect(screen.getByTestId('technical-strength')).toHaveTextContent('75%');
    });

    it('should render strength progress bar with correct width', () => {
      render(
        <TechnicalDisplay signal="BEARISH" strength={60} details={null} />
      );

      const progressBar = screen.getByTestId('strength-progress');
      expect(progressBar).toHaveStyle({ width: '60%' });
    });
  });

  describe('Technical Details', () => {
    it('should render RSI when provided', () => {
      render(
        <TechnicalDisplay signal="NEUTRAL" strength={50} details={mockDetails} />
      );

      expect(screen.getByTestId('rsi-value')).toHaveTextContent('55.5');
    });

    it('should render SMA 50 when provided', () => {
      render(
        <TechnicalDisplay signal="NEUTRAL" strength={50} details={mockDetails} />
      );

      expect(screen.getByTestId('sma50-value')).toHaveTextContent('$43500.25');
    });

    it('should render SMA 200 when provided', () => {
      render(
        <TechnicalDisplay signal="NEUTRAL" strength={50} details={mockDetails} />
      );

      expect(screen.getByTestId('sma200-value')).toHaveTextContent('$42000.00');
    });

    it('should render volume delta with sign', () => {
      render(
        <TechnicalDisplay signal="NEUTRAL" strength={50} details={mockDetails} />
      );

      expect(screen.getByTestId('volume-delta-value')).toHaveTextContent('+15.3%');
    });

    it('should render negative volume delta correctly', () => {
      const negativeDetails: TechnicalDetails = {
        ...mockDetails,
        volume_delta: -10.5,
      };

      render(
        <TechnicalDisplay signal="NEUTRAL" strength={50} details={negativeDetails} />
      );

      expect(screen.getByTestId('volume-delta-value')).toHaveTextContent('-10.5%');
    });

    it('should not render details section when null', () => {
      render(
        <TechnicalDisplay signal="NEUTRAL" strength={50} details={null} />
      );

      expect(screen.queryByTestId('technical-details')).not.toBeInTheDocument();
    });

    it('should handle partially null details', () => {
      const partialDetails: TechnicalDetails = {
        rsi: 45,
        sma_50: null,
        sma_200: null,
        volume_delta: null,
        reasoning: null,
      };

      render(
        <TechnicalDisplay signal="NEUTRAL" strength={50} details={partialDetails} />
      );

      expect(screen.getByTestId('rsi-value')).toBeInTheDocument();
      expect(screen.queryByTestId('sma50-value')).not.toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have progressbar role for strength indicator', () => {
      render(
        <TechnicalDisplay signal="BULLISH" strength={75} details={null} />
      );

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toBeInTheDocument();
    });

    it('should have correct aria attributes on progressbar', () => {
      render(
        <TechnicalDisplay signal="BULLISH" strength={75} details={null} />
      );

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow', '75');
      expect(progressBar).toHaveAttribute('aria-valuemin', '0');
      expect(progressBar).toHaveAttribute('aria-valuemax', '100');
    });
  });

  describe('Custom Styling', () => {
    it('should accept additional className', () => {
      render(
        <TechnicalDisplay
          signal="BULLISH"
          strength={75}
          details={null}
          className="custom-class"
        />
      );

      const container = screen.getByTestId('technical-display');
      expect(container).toHaveClass('custom-class');
    });
  });
});

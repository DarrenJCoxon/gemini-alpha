/**
 * @jest-environment jsdom
 */

import { render, screen } from '@testing-library/react';
import {
  SentimentIndicator,
  getSentimentLabel,
  getSentimentColor,
} from '@/components/council/sentiment-indicator';

describe('SentimentIndicator Component', () => {
  describe('getSentimentLabel', () => {
    it('should return "Extreme Fear" for scores 0-19', () => {
      expect(getSentimentLabel(0)).toBe('Extreme Fear');
      expect(getSentimentLabel(10)).toBe('Extreme Fear');
      expect(getSentimentLabel(19)).toBe('Extreme Fear');
    });

    it('should return "Fear" for scores 20-39', () => {
      expect(getSentimentLabel(20)).toBe('Fear');
      expect(getSentimentLabel(30)).toBe('Fear');
      expect(getSentimentLabel(39)).toBe('Fear');
    });

    it('should return "Neutral" for scores 40-59', () => {
      expect(getSentimentLabel(40)).toBe('Neutral');
      expect(getSentimentLabel(50)).toBe('Neutral');
      expect(getSentimentLabel(59)).toBe('Neutral');
    });

    it('should return "Greed" for scores 60-79', () => {
      expect(getSentimentLabel(60)).toBe('Greed');
      expect(getSentimentLabel(70)).toBe('Greed');
      expect(getSentimentLabel(79)).toBe('Greed');
    });

    it('should return "Extreme Greed" for scores 80-100', () => {
      expect(getSentimentLabel(80)).toBe('Extreme Greed');
      expect(getSentimentLabel(90)).toBe('Extreme Greed');
      expect(getSentimentLabel(100)).toBe('Extreme Greed');
    });
  });

  describe('getSentimentColor', () => {
    it('should return emerald-500 for extreme fear (buying opportunity)', () => {
      expect(getSentimentColor(0)).toBe('bg-emerald-500');
      expect(getSentimentColor(19)).toBe('bg-emerald-500');
    });

    it('should return emerald-400 for fear', () => {
      expect(getSentimentColor(20)).toBe('bg-emerald-400');
      expect(getSentimentColor(39)).toBe('bg-emerald-400');
    });

    it('should return zinc-400 for neutral', () => {
      expect(getSentimentColor(40)).toBe('bg-zinc-400');
      expect(getSentimentColor(59)).toBe('bg-zinc-400');
    });

    it('should return rose-400 for greed', () => {
      expect(getSentimentColor(60)).toBe('bg-rose-400');
      expect(getSentimentColor(79)).toBe('bg-rose-400');
    });

    it('should return rose-500 for extreme greed (selling opportunity)', () => {
      expect(getSentimentColor(80)).toBe('bg-rose-500');
      expect(getSentimentColor(100)).toBe('bg-rose-500');
    });
  });

  describe('Rendering', () => {
    it('should render sentiment score', () => {
      render(<SentimentIndicator score={45} />);

      expect(screen.getByText('45/100')).toBeInTheDocument();
    });

    it('should render sentiment label', () => {
      render(<SentimentIndicator score={45} />);

      expect(screen.getByTestId('sentiment-label')).toHaveTextContent('Neutral');
    });

    it('should render progress bar with correct width', () => {
      render(<SentimentIndicator score={75} />);

      const progressBar = screen.getByTestId('sentiment-progress');
      expect(progressBar).toHaveStyle({ width: '75%' });
    });

    it('should clamp score to 0-100 range for display', () => {
      render(<SentimentIndicator score={150} />);

      const progressBar = screen.getByTestId('sentiment-progress');
      expect(progressBar).toHaveStyle({ width: '100%' });
    });

    it('should clamp negative scores to 0%', () => {
      render(<SentimentIndicator score={-10} />);

      const progressBar = screen.getByTestId('sentiment-progress');
      expect(progressBar).toHaveStyle({ width: '0%' });
    });
  });

  describe('Accessibility', () => {
    it('should have progressbar role', () => {
      render(<SentimentIndicator score={50} />);

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toBeInTheDocument();
    });

    it('should have correct aria attributes', () => {
      render(<SentimentIndicator score={50} />);

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow', '50');
      expect(progressBar).toHaveAttribute('aria-valuemin', '0');
      expect(progressBar).toHaveAttribute('aria-valuemax', '100');
    });

    it('should have descriptive aria-label', () => {
      render(<SentimentIndicator score={50} />);

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute(
        'aria-label',
        'Sentiment score: 50 - Neutral'
      );
    });
  });

  describe('Custom Styling', () => {
    it('should accept additional className', () => {
      render(<SentimentIndicator score={50} className="custom-class" />);

      const container = screen.getByTestId('sentiment-indicator');
      expect(container).toHaveClass('custom-class');
    });
  });
});

/**
 * @jest-environment jsdom
 */

import { render, screen } from '@testing-library/react';
import { VisionDisplay } from '@/components/council/vision-display';

describe('VisionDisplay Component', () => {
  describe('Validity Indicator', () => {
    it('should display Valid label when isValid is true', () => {
      render(
        <VisionDisplay
          analysis="Chart shows upward trend"
          confidence={85}
          isValid={true}
        />
      );

      expect(screen.getByTestId('validity-label')).toHaveTextContent('Valid');
    });

    it('should display Invalid label when isValid is false', () => {
      render(
        <VisionDisplay
          analysis="No clear pattern"
          confidence={30}
          isValid={false}
        />
      );

      expect(screen.getByTestId('validity-label')).toHaveTextContent('Invalid');
    });

    it('should display check icon when valid', () => {
      render(
        <VisionDisplay
          analysis="Chart shows pattern"
          confidence={85}
          isValid={true}
        />
      );

      expect(screen.getByTestId('valid-icon')).toBeInTheDocument();
    });

    it('should display X icon when invalid', () => {
      render(
        <VisionDisplay
          analysis="No pattern"
          confidence={30}
          isValid={false}
        />
      );

      expect(screen.getByTestId('invalid-icon')).toBeInTheDocument();
    });
  });

  describe('Confidence Display', () => {
    it('should display confidence percentage', () => {
      render(
        <VisionDisplay
          analysis="Analysis text"
          confidence={75}
          isValid={true}
        />
      );

      expect(screen.getByTestId('vision-confidence')).toHaveTextContent('75%');
    });

    it('should display 0% confidence', () => {
      render(
        <VisionDisplay
          analysis={null}
          confidence={0}
          isValid={false}
        />
      );

      expect(screen.getByTestId('vision-confidence')).toHaveTextContent('0%');
    });

    it('should display 100% confidence', () => {
      render(
        <VisionDisplay
          analysis="Strong pattern"
          confidence={100}
          isValid={true}
        />
      );

      expect(screen.getByTestId('vision-confidence')).toHaveTextContent('100%');
    });
  });

  describe('Analysis Text', () => {
    it('should display analysis when provided', () => {
      const analysisText = 'Chart shows strong bullish pattern with support at $45,000';

      render(
        <VisionDisplay
          analysis={analysisText}
          confidence={85}
          isValid={true}
        />
      );

      expect(screen.getByTestId('vision-analysis')).toHaveTextContent(analysisText);
    });

    it('should not render analysis section when null', () => {
      render(
        <VisionDisplay
          analysis={null}
          confidence={50}
          isValid={false}
        />
      );

      expect(screen.queryByTestId('vision-analysis')).not.toBeInTheDocument();
    });

    it('should not render analysis section when empty string', () => {
      render(
        <VisionDisplay
          analysis=""
          confidence={50}
          isValid={false}
        />
      );

      // Empty string is falsy, so analysis should not render
      expect(screen.queryByTestId('vision-analysis')).not.toBeInTheDocument();
    });
  });

  describe('Styling', () => {
    it('should have emerald color for valid validity label', () => {
      render(
        <VisionDisplay
          analysis="Valid analysis"
          confidence={85}
          isValid={true}
        />
      );

      const label = screen.getByTestId('validity-label');
      expect(label).toHaveClass('text-emerald-500');
    });

    it('should have rose color for invalid validity label', () => {
      render(
        <VisionDisplay
          analysis="Invalid analysis"
          confidence={30}
          isValid={false}
        />
      );

      const label = screen.getByTestId('validity-label');
      expect(label).toHaveClass('text-rose-500');
    });
  });

  describe('Custom Styling', () => {
    it('should accept additional className', () => {
      render(
        <VisionDisplay
          analysis="Analysis"
          confidence={75}
          isValid={true}
          className="custom-class"
        />
      );

      const container = screen.getByTestId('vision-display');
      expect(container).toHaveClass('custom-class');
    });

    it('should merge custom className with default styles', () => {
      render(
        <VisionDisplay
          analysis="Analysis"
          confidence={75}
          isValid={true}
          className="test-class"
        />
      );

      const container = screen.getByTestId('vision-display');
      expect(container).toHaveClass('test-class');
      expect(container).toHaveClass('space-y-2');
    });
  });
});

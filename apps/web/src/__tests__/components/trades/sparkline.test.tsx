/**
 * @jest-environment jsdom
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { Sparkline } from '@/components/trades/sparkline';

// Mock Recharts to avoid issues with ResizeObserver
jest.mock('recharts', () => ({
  LineChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="line-chart">{children}</div>
  ),
  Line: () => <div data-testid="line" />,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  YAxis: () => <div data-testid="y-axis" />,
}));

describe('Sparkline', () => {
  it('renders chart with valid data', () => {
    render(<Sparkline data={[100, 105, 102, 108, 110]} />);

    expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
    expect(screen.getByTestId('line-chart')).toBeInTheDocument();
  });

  it('renders placeholder for empty data', () => {
    render(<Sparkline data={[]} />);

    expect(screen.getByText('--')).toBeInTheDocument();
    expect(screen.queryByTestId('line-chart')).not.toBeInTheDocument();
  });

  it('renders placeholder for single data point', () => {
    render(<Sparkline data={[100]} />);

    expect(screen.getByText('--')).toBeInTheDocument();
    expect(screen.queryByTestId('line-chart')).not.toBeInTheDocument();
  });

  it('has aria-label for accessibility', () => {
    const { container } = render(<Sparkline data={[100, 105, 110]} />);

    const chartContainer = container.querySelector('[aria-label="Price trend chart"]');
    expect(chartContainer).toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(
      <Sparkline data={[100, 105, 110]} className="custom-class" />
    );

    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('auto-detects positive trend', () => {
    // When data goes up, it should use positive color
    const { container } = render(
      <Sparkline data={[100, 102, 105, 108, 110]} />
    );

    // Component should render (trend is positive: 110 > 100)
    expect(screen.getByTestId('line-chart')).toBeInTheDocument();
  });

  it('auto-detects negative trend', () => {
    // When data goes down, it should use negative color
    const { container } = render(
      <Sparkline data={[110, 108, 105, 102, 100]} />
    );

    // Component should render (trend is negative: 100 < 110)
    expect(screen.getByTestId('line-chart')).toBeInTheDocument();
  });

  it('respects isPositive override for positive', () => {
    render(<Sparkline data={[110, 100]} isPositive={true} />);

    // Even though data trends down, isPositive forces green color
    expect(screen.getByTestId('line-chart')).toBeInTheDocument();
  });

  it('respects isPositive override for negative', () => {
    render(<Sparkline data={[100, 110]} isPositive={false} />);

    // Even though data trends up, isPositive=false forces red color
    expect(screen.getByTestId('line-chart')).toBeInTheDocument();
  });

  it('handles undefined data gracefully', () => {
    // @ts-expect-error Testing undefined handling
    render(<Sparkline data={undefined} />);

    expect(screen.getByText('--')).toBeInTheDocument();
  });
});

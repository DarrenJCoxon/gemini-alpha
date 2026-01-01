/**
 * @jest-environment jsdom
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { StopLossIndicator } from '@/components/trades/stop-loss-indicator';

describe('StopLossIndicator', () => {
  const defaultProps = {
    entryPrice: 45000,
    currentPrice: 46000,
    stopLossPrice: 44000,
    takeProfitPrice: 48000,
    direction: 'LONG' as const,
  };

  it('renders stop loss price', () => {
    render(<StopLossIndicator {...defaultProps} />);

    expect(screen.getByText('Stop: $44000.00')).toBeInTheDocument();
  });

  it('renders take profit price when provided', () => {
    render(<StopLossIndicator {...defaultProps} />);

    expect(screen.getByText('TP: $48000.00')).toBeInTheDocument();
  });

  it('does not render take profit when null', () => {
    render(
      <StopLossIndicator
        {...defaultProps}
        takeProfitPrice={null}
      />
    );

    expect(screen.queryByText(/TP:/)).not.toBeInTheDocument();
  });

  it('renders risk and profit zone labels', () => {
    render(<StopLossIndicator {...defaultProps} />);

    expect(screen.getByText('Risk Zone')).toBeInTheDocument();
    expect(screen.getByText('Profit Zone')).toBeInTheDocument();
  });

  it('has progressbar role for accessibility', () => {
    render(<StopLossIndicator {...defaultProps} />);

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('calculates correct position when in profit (LONG)', () => {
    const { container } = render(
      <StopLossIndicator
        entryPrice={45000}
        currentPrice={46000}
        stopLossPrice={44000}
        takeProfitPrice={48000}
        direction="LONG"
      />
    );

    // Current price is above entry, should show profit colors
    const fillBar = container.querySelector('.bg-emerald-500\\/50');
    expect(fillBar).toBeInTheDocument();
  });

  it('calculates correct position when in loss (LONG)', () => {
    const { container } = render(
      <StopLossIndicator
        entryPrice={45000}
        currentPrice={44500}
        stopLossPrice={44000}
        takeProfitPrice={48000}
        direction="LONG"
      />
    );

    // Current price is below entry, should show loss colors
    const fillBar = container.querySelector('.bg-rose-500\\/50');
    expect(fillBar).toBeInTheDocument();
  });

  it('handles SHORT position in profit', () => {
    const { container } = render(
      <StopLossIndicator
        entryPrice={45000}
        currentPrice={44000}
        stopLossPrice={46000}
        takeProfitPrice={43000}
        direction="SHORT"
      />
    );

    // For SHORT, profit is when current < entry
    const fillBar = container.querySelector('.bg-emerald-500\\/50');
    expect(fillBar).toBeInTheDocument();
  });

  it('handles SHORT position in loss', () => {
    const { container } = render(
      <StopLossIndicator
        entryPrice={45000}
        currentPrice={45500}
        stopLossPrice={46000}
        takeProfitPrice={43000}
        direction="SHORT"
      />
    );

    // For SHORT, loss is when current > entry
    const fillBar = container.querySelector('.bg-rose-500\\/50');
    expect(fillBar).toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(
      <StopLossIndicator {...defaultProps} className="custom-class" />
    );

    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('handles missing takeProfitPrice for LONG', () => {
    // Should use double distance to stop as default range
    render(
      <StopLossIndicator
        entryPrice={45000}
        currentPrice={46000}
        stopLossPrice={44000}
        takeProfitPrice={null}
        direction="LONG"
      />
    );

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('clamps current position at 0% when below stop', () => {
    render(
      <StopLossIndicator
        entryPrice={45000}
        currentPrice={43000} // Below stop loss
        stopLossPrice={44000}
        takeProfitPrice={48000}
        direction="LONG"
      />
    );

    const progressbar = screen.getByRole('progressbar');
    expect(progressbar.getAttribute('aria-valuenow')).toBe('0');
  });

  it('clamps current position at 100% when above take profit', () => {
    render(
      <StopLossIndicator
        entryPrice={45000}
        currentPrice={50000} // Above take profit
        stopLossPrice={44000}
        takeProfitPrice={48000}
        direction="LONG"
      />
    );

    const progressbar = screen.getByRole('progressbar');
    expect(progressbar.getAttribute('aria-valuenow')).toBe('100');
  });
});

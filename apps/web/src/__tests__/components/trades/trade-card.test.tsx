/**
 * @jest-environment jsdom
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { TradeCard } from '@/components/trades/trade-card';
import { TradeWithMetrics } from '@/types/trade';

// Mock recharts
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

// Mock date-fns
jest.mock('date-fns', () => ({
  formatDistanceToNow: jest.fn(() => '2 hours ago'),
}));

describe('TradeCard', () => {
  const createMockTrade = (overrides: Partial<TradeWithMetrics> = {}): TradeWithMetrics => ({
    id: 'trade-1',
    assetId: 'asset-1',
    status: 'OPEN',
    direction: 'LONG',
    entryPrice: 45000,
    size: 0.5,
    entryTime: new Date('2024-01-01T00:00:00Z'),
    stopLossPrice: 44000,
    takeProfitPrice: 48000,
    exitPrice: null,
    exitTime: null,
    pnl: null,
    createdAt: new Date('2024-01-01T00:00:00Z'),
    updatedAt: new Date('2024-01-01T00:00:00Z'),
    currentPrice: 46000,
    unrealizedPnl: 500,
    unrealizedPnlPercent: 2.22,
    distanceToStopPercent: 4.35,
    distanceToTakeProfitPercent: 4.35,
    asset: {
      symbol: 'BTC/USD',
      lastPrice: 46000,
    },
    ...overrides,
  });

  it('renders trade symbol', () => {
    render(<TradeCard trade={createMockTrade()} />);

    expect(screen.getByText('BTC/USD')).toBeInTheDocument();
  });

  it('renders LONG direction badge', () => {
    render(<TradeCard trade={createMockTrade({ direction: 'LONG' })} />);

    expect(screen.getByText('LONG')).toBeInTheDocument();
  });

  it('renders SHORT direction badge', () => {
    render(<TradeCard trade={createMockTrade({ direction: 'SHORT' })} />);

    expect(screen.getByText('SHORT')).toBeInTheDocument();
  });

  it('displays positive P&L with profit styling', () => {
    render(
      <TradeCard
        trade={createMockTrade({
          unrealizedPnl: 500,
          unrealizedPnlPercent: 2.22,
        })}
      />
    );

    // Text may be split across elements, use regex
    expect(screen.getByText(/\+2\.22/)).toBeInTheDocument();
    expect(screen.getByText(/\+\$500\.00/)).toBeInTheDocument();
  });

  it('displays negative P&L with loss styling', () => {
    render(
      <TradeCard
        trade={createMockTrade({
          unrealizedPnl: -500,
          unrealizedPnlPercent: -2.22,
        })}
      />
    );

    // Text may be split across elements, use regex
    expect(screen.getByText(/-2\.22/)).toBeInTheDocument();
    expect(screen.getByText(/-500\.00/)).toBeInTheDocument();
  });

  it('displays entry price', () => {
    render(<TradeCard trade={createMockTrade({ entryPrice: 45000 })} />);

    expect(screen.getByText('$45000.00')).toBeInTheDocument();
  });

  it('displays current price', () => {
    render(<TradeCard trade={createMockTrade({ currentPrice: 46000 })} />);

    expect(screen.getByText('$46000.00')).toBeInTheDocument();
  });

  it('displays size', () => {
    render(<TradeCard trade={createMockTrade({ size: 0.5 })} />);

    expect(screen.getByText('0.5000')).toBeInTheDocument();
  });

  it('renders TrendingUp icon for profit', () => {
    render(
      <TradeCard
        trade={createMockTrade({ unrealizedPnlPercent: 2.22 })}
      />
    );

    expect(screen.getByLabelText('Profit')).toBeInTheDocument();
  });

  it('renders TrendingDown icon for loss', () => {
    render(
      <TradeCard
        trade={createMockTrade({ unrealizedPnlPercent: -2.22 })}
      />
    );

    expect(screen.getByLabelText('Loss')).toBeInTheDocument();
  });

  it('displays distance to stop', () => {
    const { container } = render(
      <TradeCard trade={createMockTrade({ distanceToStopPercent: 4.35 })} />
    );

    // Check that the component contains the distance text (4.3% is the rounded value)
    expect(container.textContent).toMatch(/4\.\d+% to stop/);
  });

  it('highlights danger when close to stop', () => {
    const { container } = render(
      <TradeCard trade={createMockTrade({ distanceToStopPercent: 1.5 })} />
    );

    // Should have rose-500 class for danger
    expect(container.querySelector('.text-rose-500')).toBeInTheDocument();
  });

  it('displays time since opened', () => {
    render(<TradeCard trade={createMockTrade()} />);

    expect(screen.getByText(/Opened 2 hours ago/)).toBeInTheDocument();
  });

  it('renders sparkline when priceHistory provided', () => {
    render(
      <TradeCard
        trade={createMockTrade()}
        priceHistory={[45000, 45500, 46000]}
      />
    );

    expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
  });

  it('does not render sparkline when no priceHistory', () => {
    render(<TradeCard trade={createMockTrade()} />);

    expect(screen.queryByTestId('responsive-container')).not.toBeInTheDocument();
  });

  it('falls back to assetId when no asset symbol', () => {
    render(
      <TradeCard
        trade={createMockTrade({
          asset: undefined,
          assetId: 'fallback-asset-id',
        })}
      />
    );

    expect(screen.getByText('fallback-asset-id')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(
      <TradeCard trade={createMockTrade()} className="custom-class" />
    );

    const card = container.querySelector('.custom-class');
    expect(card).toBeInTheDocument();
  });
});

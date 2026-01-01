/**
 * @jest-environment jsdom
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ActiveTrades } from '@/components/trades/active-trades';
import { TradeWithMetrics } from '@/types/trade';

// Mock the fetchOpenTrades action
jest.mock('@/app/dashboard/trades/actions', () => ({
  fetchOpenTrades: jest.fn(),
}));

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

// Mock the trade and asset price listener hooks
jest.mock('@/hooks/use-trade-listener', () => ({
  useTradeListener: jest.fn(),
}));

jest.mock('@/hooks/use-asset-price-listener', () => ({
  useAssetPriceListener: jest.fn(),
}));

import { fetchOpenTrades } from '@/app/dashboard/trades/actions';

const mockFetchOpenTrades = fetchOpenTrades as jest.MockedFunction<typeof fetchOpenTrades>;

describe('ActiveTrades', () => {
  const createMockTrade = (id: string, overrides: Partial<TradeWithMetrics> = {}): TradeWithMetrics => ({
    id,
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

  beforeEach(() => {
    jest.clearAllMocks();
    mockFetchOpenTrades.mockResolvedValue([]);
  });

  it('renders header with title', () => {
    render(<ActiveTrades initialTrades={[]} />);

    expect(screen.getByText('Active Positions')).toBeInTheDocument();
  });

  it('displays trade count', () => {
    const trades = [createMockTrade('1'), createMockTrade('2')];
    render(<ActiveTrades initialTrades={trades} />);

    expect(screen.getByText('2 open trades')).toBeInTheDocument();
  });

  it('displays singular trade count', () => {
    const trades = [createMockTrade('1')];
    render(<ActiveTrades initialTrades={trades} />);

    expect(screen.getByText('1 open trade')).toBeInTheDocument();
  });

  it('renders trade cards for initial trades', () => {
    const trades = [
      createMockTrade('1', { asset: { symbol: 'BTC/USD', lastPrice: 46000 } }),
      createMockTrade('2', { asset: { symbol: 'ETH/USD', lastPrice: 2500 } }),
    ];
    render(<ActiveTrades initialTrades={trades} />);

    expect(screen.getByText('BTC/USD')).toBeInTheDocument();
    expect(screen.getByText('ETH/USD')).toBeInTheDocument();
  });

  it('displays total unrealized P&L (profit)', () => {
    const trades = [
      createMockTrade('1', { unrealizedPnl: 500, unrealizedPnlPercent: 2 }),
      createMockTrade('2', { unrealizedPnl: 300, unrealizedPnlPercent: 3 }),
    ];
    const { container } = render(<ActiveTrades initialTrades={trades} />);

    // Text may be split across elements, check container text
    expect(container.textContent).toMatch(/\+.*\$800\.00/);
  });

  it('displays total unrealized P&L (loss)', () => {
    const trades = [
      createMockTrade('1', { unrealizedPnl: -500, unrealizedPnlPercent: -2 }),
      createMockTrade('2', { unrealizedPnl: -300, unrealizedPnlPercent: -3 }),
    ];
    const { container } = render(<ActiveTrades initialTrades={trades} />);

    // Text may be split across elements, check container text
    // The format is $-800.00 not -$800.00
    expect(container.textContent).toMatch(/\$-800\.00/);
  });

  it('displays average ROI', () => {
    const trades = [
      createMockTrade('1', { unrealizedPnlPercent: 2 }),
      createMockTrade('2', { unrealizedPnlPercent: 4 }),
    ];
    const { container } = render(<ActiveTrades initialTrades={trades} />);

    // Average of 2% and 4% = 3%, text may be split
    expect(container.textContent).toMatch(/\+.*3\.00.*%/);
  });

  it('shows at-risk warning when trades near stop loss', () => {
    const trades = [
      createMockTrade('1', { distanceToStopPercent: 1.5 }), // At risk
      createMockTrade('2', { distanceToStopPercent: 10 }), // Safe
    ];
    render(<ActiveTrades initialTrades={trades} />);

    expect(screen.getByText('1 trade within 2% of stop loss')).toBeInTheDocument();
  });

  it('shows plural at-risk warning for multiple trades', () => {
    const trades = [
      createMockTrade('1', { distanceToStopPercent: 1 }),
      createMockTrade('2', { distanceToStopPercent: 1.5 }),
    ];
    render(<ActiveTrades initialTrades={trades} />);

    expect(screen.getByText('2 trades within 2% of stop loss')).toBeInTheDocument();
  });

  it('does not show at-risk warning when no trades near stop', () => {
    const trades = [
      createMockTrade('1', { distanceToStopPercent: 10 }),
      createMockTrade('2', { distanceToStopPercent: 15 }),
    ];
    render(<ActiveTrades initialTrades={trades} />);

    expect(screen.queryByText(/within 2% of stop loss/)).not.toBeInTheDocument();
  });

  it('displays empty state when no trades', async () => {
    // Mock returns empty array to show empty state after fetch
    mockFetchOpenTrades.mockResolvedValue([]);
    render(<ActiveTrades initialTrades={[]} />);

    // Wait for fetch to complete and empty state to show
    await waitFor(() => {
      expect(screen.getByText('No active positions')).toBeInTheDocument();
    });
    expect(screen.getByText('Trades will appear here when the bot opens positions')).toBeInTheDocument();
  });

  it('has refresh button with accessibility label', () => {
    render(<ActiveTrades initialTrades={[]} />);

    expect(screen.getByLabelText('Refresh trades')).toBeInTheDocument();
  });

  it('calls fetchOpenTrades on refresh click', async () => {
    mockFetchOpenTrades.mockResolvedValue([createMockTrade('1')]);
    render(<ActiveTrades initialTrades={[]} />);

    const refreshButton = screen.getByLabelText('Refresh trades');
    fireEvent.click(refreshButton);

    await waitFor(() => {
      expect(mockFetchOpenTrades).toHaveBeenCalled();
    });
  });

  it('shows loading state while fetching', async () => {
    let resolvePromise: (value: TradeWithMetrics[]) => void;
    mockFetchOpenTrades.mockImplementation(() => new Promise((resolve) => {
      resolvePromise = resolve;
    }));

    render(<ActiveTrades initialTrades={[]} />);
    const refreshButton = screen.getByLabelText('Refresh trades');
    fireEvent.click(refreshButton);

    // Button should be disabled while loading
    expect(refreshButton).toBeDisabled();

    // Resolve the promise
    resolvePromise!([]);
    await waitFor(() => {
      expect(refreshButton).not.toBeDisabled();
    });
  });

  it('shows error message on fetch failure', async () => {
    mockFetchOpenTrades.mockRejectedValue(new Error('Network error'));
    render(<ActiveTrades initialTrades={[]} />);

    const refreshButton = screen.getByLabelText('Refresh trades');
    fireEvent.click(refreshButton);

    await waitFor(() => {
      expect(screen.getByText('Failed to load trades')).toBeInTheDocument();
    });
  });

  it('has role="alert" on error message', async () => {
    mockFetchOpenTrades.mockRejectedValue(new Error('Network error'));
    render(<ActiveTrades initialTrades={[]} />);

    fireEvent.click(screen.getByLabelText('Refresh trades'));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('applies custom className', () => {
    const { container } = render(
      <ActiveTrades initialTrades={[]} className="custom-class" />
    );

    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('fetches trades on mount when no initial trades', async () => {
    mockFetchOpenTrades.mockResolvedValue([createMockTrade('1')]);
    render(<ActiveTrades />);

    await waitFor(() => {
      expect(mockFetchOpenTrades).toHaveBeenCalled();
    });
  });

  it('does not fetch on mount when initial trades provided', () => {
    render(<ActiveTrades initialTrades={[createMockTrade('1')]} />);

    expect(mockFetchOpenTrades).not.toHaveBeenCalled();
  });
});

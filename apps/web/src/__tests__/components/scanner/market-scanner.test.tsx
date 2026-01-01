/**
 * @jest-environment jsdom
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MarketScanner } from '@/components/scanner/market-scanner';
import { ScannerAsset } from '@/types/scanner';

// Mock the fetchScannerAssets action
jest.mock('@/app/dashboard/scanner/actions', () => ({
  fetchScannerAssets: jest.fn(),
}));

import { fetchScannerAssets } from '@/app/dashboard/scanner/actions';

const mockFetchScannerAssets = fetchScannerAssets as jest.MockedFunction<typeof fetchScannerAssets>;

describe('MarketScanner', () => {
  const createMockAsset = (id: string, overrides: Partial<ScannerAsset> = {}): ScannerAsset => ({
    id,
    symbol: 'BTC/USD',
    lastPrice: 45000,
    priceChange15m: 2.5,
    sentimentScore: 35,
    technicalSignal: 'BULLISH',
    technicalStrength: 75,
    lastSessionTime: new Date('2024-01-01T00:00:00Z'),
    ...overrides,
  });

  beforeEach(() => {
    jest.clearAllMocks();
    mockFetchScannerAssets.mockResolvedValue([]);
  });

  it('renders header with title', () => {
    render(<MarketScanner initialAssets={[]} />);

    expect(screen.getByText('Market Scanner')).toBeInTheDocument();
  });

  it('displays high-fear asset count', () => {
    const assets = [
      createMockAsset('1', { sentimentScore: 15 }), // High fear
      createMockAsset('2', { sentimentScore: 35 }), // Medium
      createMockAsset('3', { sentimentScore: 10 }), // High fear
    ];
    render(<MarketScanner initialAssets={assets} />);

    expect(screen.getByText('2 high-fear assets')).toBeInTheDocument();
  });

  it('displays singular high-fear count', () => {
    const assets = [
      createMockAsset('1', { sentimentScore: 15 }), // High fear
      createMockAsset('2', { sentimentScore: 50 }), // Medium
    ];
    render(<MarketScanner initialAssets={assets} />);

    expect(screen.getByText('1 high-fear asset')).toBeInTheDocument();
  });

  it('displays zero high-fear assets when none qualify', () => {
    const assets = [
      createMockAsset('1', { sentimentScore: 50 }),
      createMockAsset('2', { sentimentScore: 80 }),
    ];
    render(<MarketScanner initialAssets={assets} />);

    expect(screen.getByText('0 high-fear assets')).toBeInTheDocument();
  });

  it('excludes null sentiment from high-fear count', () => {
    const assets = [
      createMockAsset('1', { sentimentScore: null }),
      createMockAsset('2', { sentimentScore: 15 }),
    ];
    render(<MarketScanner initialAssets={assets} />);

    expect(screen.getByText('1 high-fear asset')).toBeInTheDocument();
  });

  it('renders scanner table with assets', () => {
    const assets = [
      createMockAsset('1', { symbol: 'BTC/USD' }),
      createMockAsset('2', { symbol: 'ETH/USD' }),
    ];
    render(<MarketScanner initialAssets={assets} />);

    expect(screen.getByText('BTC/USD')).toBeInTheDocument();
    expect(screen.getByText('ETH/USD')).toBeInTheDocument();
  });

  it('has refresh button with accessibility label', () => {
    render(<MarketScanner initialAssets={[]} />);

    expect(screen.getByLabelText('Refresh scanner')).toBeInTheDocument();
  });

  it('calls fetchScannerAssets on refresh click', async () => {
    mockFetchScannerAssets.mockResolvedValue([createMockAsset('1')]);
    render(<MarketScanner initialAssets={[]} />);

    const refreshButton = screen.getByLabelText('Refresh scanner');
    fireEvent.click(refreshButton);

    await waitFor(() => {
      expect(mockFetchScannerAssets).toHaveBeenCalled();
    });
  });

  it('shows loading state while fetching', async () => {
    let resolvePromise: (value: ScannerAsset[]) => void;
    mockFetchScannerAssets.mockImplementation(() => new Promise((resolve) => {
      resolvePromise = resolve;
    }));

    render(<MarketScanner initialAssets={[]} />);
    const refreshButton = screen.getByLabelText('Refresh scanner');
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
    mockFetchScannerAssets.mockRejectedValue(new Error('Network error'));
    render(<MarketScanner initialAssets={[]} />);

    const refreshButton = screen.getByLabelText('Refresh scanner');
    fireEvent.click(refreshButton);

    await waitFor(() => {
      expect(screen.getByText('Failed to load scanner data')).toBeInTheDocument();
    });
  });

  it('has role="alert" on error message', async () => {
    mockFetchScannerAssets.mockRejectedValue(new Error('Network error'));
    render(<MarketScanner initialAssets={[]} />);

    fireEvent.click(screen.getByLabelText('Refresh scanner'));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('calls onAssetSelect when asset row clicked', () => {
    const onAssetSelect = jest.fn();
    const assets = [createMockAsset('1', { symbol: 'BTC/USD' })];
    render(<MarketScanner initialAssets={assets} onAssetSelect={onAssetSelect} />);

    const row = screen.getByText('BTC/USD').closest('tr');
    fireEvent.click(row!);

    expect(onAssetSelect).toHaveBeenCalledWith(assets[0]);
  });

  it('applies custom className', () => {
    const { container } = render(
      <MarketScanner initialAssets={[]} className="custom-class" />
    );

    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('fetches assets on mount when no initial assets', async () => {
    mockFetchScannerAssets.mockResolvedValue([createMockAsset('1')]);
    render(<MarketScanner />);

    await waitFor(() => {
      expect(mockFetchScannerAssets).toHaveBeenCalled();
    });
  });

  it('does not fetch on mount when initial assets provided', () => {
    render(<MarketScanner initialAssets={[createMockAsset('1')]} />);

    expect(mockFetchScannerAssets).not.toHaveBeenCalled();
  });

  it('updates assets after successful fetch', async () => {
    const newAssets = [
      createMockAsset('1', { symbol: 'NEW/USD' }),
    ];
    mockFetchScannerAssets.mockResolvedValue(newAssets);

    render(<MarketScanner initialAssets={[createMockAsset('old', { symbol: 'OLD/USD' })]} />);

    // Initially shows old asset
    expect(screen.getByText('OLD/USD')).toBeInTheDocument();

    // Click refresh
    fireEvent.click(screen.getByLabelText('Refresh scanner'));

    await waitFor(() => {
      expect(screen.getByText('NEW/USD')).toBeInTheDocument();
    });
  });
});

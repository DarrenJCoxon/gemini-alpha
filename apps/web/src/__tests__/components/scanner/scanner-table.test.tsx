/**
 * @jest-environment jsdom
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ScannerTable } from '@/components/scanner/scanner-table';
import { ScannerAsset } from '@/types/scanner';

describe('ScannerTable', () => {
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

  it('renders table headers', () => {
    render(<ScannerTable assets={[]} />);

    expect(screen.getByText('Symbol')).toBeInTheDocument();
    expect(screen.getByText('Price')).toBeInTheDocument();
    expect(screen.getByText('Fear')).toBeInTheDocument();
    expect(screen.getByText('Signal')).toBeInTheDocument();
  });

  it('renders asset rows', () => {
    const assets = [
      createMockAsset('1', { symbol: 'BTC/USD' }),
      createMockAsset('2', { symbol: 'ETH/USD' }),
    ];
    render(<ScannerTable assets={assets} />);

    expect(screen.getByText('BTC/USD')).toBeInTheDocument();
    expect(screen.getByText('ETH/USD')).toBeInTheDocument();
  });

  it('displays last price', () => {
    const assets = [createMockAsset('1', { lastPrice: 45000.50 })];
    render(<ScannerTable assets={assets} />);

    expect(screen.getByText('$45000.50')).toBeInTheDocument();
  });

  it('displays positive price change with color', () => {
    const assets = [createMockAsset('1', { priceChange15m: 2.5 })];
    const { container } = render(<ScannerTable assets={assets} />);

    expect(screen.getByText('+2.50%')).toBeInTheDocument();
    expect(container.querySelector('.text-emerald-500')).toBeInTheDocument();
  });

  it('displays negative price change with color', () => {
    const assets = [createMockAsset('1', { priceChange15m: -3.2 })];
    const { container } = render(<ScannerTable assets={assets} />);

    expect(screen.getByText('-3.20%')).toBeInTheDocument();
    expect(container.querySelector('.text-rose-500')).toBeInTheDocument();
  });

  it('displays sentiment score with fear coloring (low = green)', () => {
    const assets = [createMockAsset('1', { sentimentScore: 15 })];
    const { container } = render(<ScannerTable assets={assets} />);

    expect(screen.getByText('15')).toBeInTheDocument();
    expect(container.querySelector('.text-emerald-500')).toBeInTheDocument();
  });

  it('displays sentiment score with greed coloring (high = red)', () => {
    const assets = [createMockAsset('1', { sentimentScore: 85 })];
    const { container } = render(<ScannerTable assets={assets} />);

    expect(screen.getByText('85')).toBeInTheDocument();
    expect(container.querySelector('.text-rose-500')).toBeInTheDocument();
  });

  it('displays placeholder for null sentiment score', () => {
    const assets = [createMockAsset('1', { sentimentScore: null })];
    render(<ScannerTable assets={assets} />);

    expect(screen.getAllByText('--').length).toBeGreaterThan(0);
  });

  it('displays BULLISH signal with icon', () => {
    const assets = [createMockAsset('1', { technicalSignal: 'BULLISH' })];
    render(<ScannerTable assets={assets} />);

    expect(screen.getByText('BULLISH')).toBeInTheDocument();
  });

  it('displays BEARISH signal with icon', () => {
    const assets = [createMockAsset('1', { technicalSignal: 'BEARISH' })];
    render(<ScannerTable assets={assets} />);

    expect(screen.getByText('BEARISH')).toBeInTheDocument();
  });

  it('displays NEUTRAL signal', () => {
    const assets = [createMockAsset('1', { technicalSignal: 'NEUTRAL' })];
    render(<ScannerTable assets={assets} />);

    expect(screen.getByText('NEUTRAL')).toBeInTheDocument();
  });

  it('displays placeholder for null technical signal', () => {
    const assets = [createMockAsset('1', { technicalSignal: null })];
    render(<ScannerTable assets={assets} />);

    expect(screen.getAllByText('--').length).toBeGreaterThan(0);
  });

  it('displays empty state when no assets', () => {
    render(<ScannerTable assets={[]} />);

    expect(screen.getByText('No assets found')).toBeInTheDocument();
  });

  it('calls onRowClick when row is clicked', () => {
    const onRowClick = jest.fn();
    const assets = [createMockAsset('1', { symbol: 'BTC/USD' })];
    render(<ScannerTable assets={assets} onRowClick={onRowClick} />);

    const row = screen.getByText('BTC/USD').closest('tr');
    fireEvent.click(row!);

    expect(onRowClick).toHaveBeenCalledWith(assets[0]);
  });

  it('makes rows focusable when onRowClick provided', () => {
    const onRowClick = jest.fn();
    const assets = [createMockAsset('1')];
    render(<ScannerTable assets={assets} onRowClick={onRowClick} />);

    const row = screen.getByText('BTC/USD').closest('tr');
    expect(row).toHaveAttribute('tabindex', '0');
  });

  it('triggers onRowClick on Enter key', () => {
    const onRowClick = jest.fn();
    const assets = [createMockAsset('1')];
    render(<ScannerTable assets={assets} onRowClick={onRowClick} />);

    const row = screen.getByText('BTC/USD').closest('tr');
    fireEvent.keyDown(row!, { key: 'Enter' });

    expect(onRowClick).toHaveBeenCalled();
  });

  it('triggers onRowClick on Space key', () => {
    const onRowClick = jest.fn();
    const assets = [createMockAsset('1')];
    render(<ScannerTable assets={assets} onRowClick={onRowClick} />);

    const row = screen.getByText('BTC/USD').closest('tr');
    fireEvent.keyDown(row!, { key: ' ' });

    expect(onRowClick).toHaveBeenCalled();
  });

  describe('Sorting', () => {
    it('sorts by symbol when header clicked', () => {
      const assets = [
        createMockAsset('1', { symbol: 'ETH/USD' }),
        createMockAsset('2', { symbol: 'BTC/USD' }),
      ];
      render(<ScannerTable assets={assets} />);

      const symbolHeader = screen.getByRole('button', { name: /Sort by Symbol/i });
      fireEvent.click(symbolHeader);

      const rows = screen.getAllByRole('row');
      // First row is header, so check rows[1] and rows[2]
      expect(rows[1]).toHaveTextContent('BTC/USD');
      expect(rows[2]).toHaveTextContent('ETH/USD');
    });

    it('reverses sort direction on second click', () => {
      const assets = [
        createMockAsset('1', { symbol: 'BTC/USD' }),
        createMockAsset('2', { symbol: 'ETH/USD' }),
      ];
      render(<ScannerTable assets={assets} />);

      const symbolHeader = screen.getByRole('button', { name: /Sort by Symbol/i });

      // First click - ascending
      fireEvent.click(symbolHeader);
      // Second click - descending
      fireEvent.click(symbolHeader);

      const rows = screen.getAllByRole('row');
      expect(rows[1]).toHaveTextContent('ETH/USD');
      expect(rows[2]).toHaveTextContent('BTC/USD');
    });

    it('sorts by fear score by default (ascending)', () => {
      const assets = [
        createMockAsset('1', { symbol: 'HIGH', sentimentScore: 80 }),
        createMockAsset('2', { symbol: 'LOW', sentimentScore: 15 }),
      ];
      render(<ScannerTable assets={assets} />);

      const rows = screen.getAllByRole('row');
      // Low fear first (ascending)
      expect(rows[1]).toHaveTextContent('LOW');
      expect(rows[2]).toHaveTextContent('HIGH');
    });

    it('pushes null sentiment scores to end', () => {
      const assets = [
        createMockAsset('1', { symbol: 'NULL', sentimentScore: null }),
        createMockAsset('2', { symbol: 'LOW', sentimentScore: 15 }),
      ];
      render(<ScannerTable assets={assets} />);

      const rows = screen.getAllByRole('row');
      expect(rows[1]).toHaveTextContent('LOW');
      expect(rows[2]).toHaveTextContent('NULL');
    });
  });

  it('applies custom className', () => {
    const { container } = render(
      <ScannerTable assets={[]} className="custom-class" />
    );

    expect(container.firstChild).toHaveClass('custom-class');
  });
});

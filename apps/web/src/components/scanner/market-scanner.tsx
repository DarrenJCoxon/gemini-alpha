'use client';

import { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ScannerAsset } from '@/types/scanner';
import { fetchScannerAssets } from '@/app/dashboard/scanner/actions';
import { ScannerTable } from './scanner-table';

interface MarketScannerProps {
  initialAssets?: ScannerAsset[];
  onAssetSelect?: (asset: ScannerAsset) => void;
  className?: string;
}

/**
 * Container component for the market scanner.
 * Fetches and displays assets with sorting capabilities.
 */
export function MarketScanner({
  initialAssets = [],
  onAssetSelect,
  className,
}: MarketScannerProps) {
  const [assets, setAssets] = useState<ScannerAsset[]>(initialAssets);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAssets = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await fetchScannerAssets();
      setAssets(data);
    } catch (err) {
      setError('Failed to load scanner data');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (initialAssets.length === 0) {
      loadAssets();
    }
  }, [initialAssets.length, loadAssets]);

  // Count opportunities (low fear score)
  const opportunities = assets.filter(
    (a) => a.sentimentScore !== null && a.sentimentScore < 20
  );

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-zinc-100">Market Scanner</h2>
          <p className="text-sm text-zinc-400">
            {opportunities.length} high-fear asset{opportunities.length !== 1 ? 's' : ''}
          </p>
        </div>
        <Button
          size="sm"
          variant="ghost"
          onClick={loadAssets}
          disabled={isLoading}
          className="h-8"
          aria-label="Refresh scanner"
        >
          <RefreshCw className={cn('h-4 w-4', isLoading && 'animate-spin')} />
        </Button>
      </div>

      {/* Error state */}
      {error && (
        <div
          className="bg-rose-500/10 border border-rose-500/50 text-rose-500 p-3 rounded-md mb-4 text-sm"
          role="alert"
        >
          {error}
        </div>
      )}

      {/* Scanner Table */}
      <div className="flex-1 overflow-auto">
        <ScannerTable
          assets={assets}
          onRowClick={onAssetSelect}
        />
      </div>
    </div>
  );
}

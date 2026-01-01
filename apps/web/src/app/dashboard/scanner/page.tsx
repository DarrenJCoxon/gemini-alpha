import { Metadata } from 'next';
import { MarketScanner } from '@/components/scanner/market-scanner';
import { fetchScannerAssets } from './actions';

export const metadata: Metadata = {
  title: 'Market Scanner | ContrarianAI',
  description: 'Scan market for trading opportunities',
};

export default async function ScannerPage() {
  let assets: Awaited<ReturnType<typeof fetchScannerAssets>> = [];

  try {
    assets = await fetchScannerAssets();
  } catch (error) {
    console.error('Failed to fetch scanner assets:', error);
    // Assets will be empty, component will handle this gracefully
  }

  return (
    <div className="h-[calc(100vh-8rem)]">
      <MarketScanner initialAssets={assets} />
    </div>
  );
}

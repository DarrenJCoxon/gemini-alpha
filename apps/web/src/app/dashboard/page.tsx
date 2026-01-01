import { Metadata } from 'next';
import { CouncilFeed } from '@/components/council/council-feed';
import { ActiveTrades } from '@/components/trades/active-trades';
import { MarketScanner } from '@/components/scanner/market-scanner';
import { fetchCouncilSessions } from './council/actions';
import { fetchOpenTrades } from './trades/actions';
import { fetchScannerAssets } from './scanner/actions';

export const metadata: Metadata = {
  title: 'Dashboard | ContrarianAI',
  description: 'ContrarianAI Mission Control Dashboard',
};

export default async function DashboardPage() {
  // Parallel data fetching with error handling
  const [councilResult, tradesResult, scannerResult] = await Promise.allSettled([
    fetchCouncilSessions({ limit: 10 }),
    fetchOpenTrades(),
    fetchScannerAssets({ limit: 30 }),
  ]);

  // Extract data with fallbacks
  const sessions = councilResult.status === 'fulfilled'
    ? councilResult.value.sessions
    : [];

  const trades = tradesResult.status === 'fulfilled'
    ? tradesResult.value
    : [];

  const scannerAssets = scannerResult.status === 'fulfilled'
    ? scannerResult.value
    : [];

  // Log errors for debugging
  if (councilResult.status === 'rejected') {
    console.error('Failed to fetch council sessions:', councilResult.reason);
  }
  if (tradesResult.status === 'rejected') {
    console.error('Failed to fetch trades:', tradesResult.reason);
  }
  if (scannerResult.status === 'rejected') {
    console.error('Failed to fetch scanner assets:', scannerResult.reason);
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-zinc-100">Mission Control</h1>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Council Feed - 40% */}
        <div className="lg:col-span-5 bg-zinc-900 rounded-lg border border-zinc-800 p-4 h-[600px]">
          <CouncilFeed initialSessions={sessions} />
        </div>

        {/* Active Trades - 35% */}
        <div className="lg:col-span-4 bg-zinc-900 rounded-lg border border-zinc-800 p-4 h-[600px]">
          <ActiveTrades initialTrades={trades} />
        </div>

        {/* Scanner - 25% */}
        <div className="lg:col-span-3 bg-zinc-900 rounded-lg border border-zinc-800 p-4 h-[600px]">
          <MarketScanner initialAssets={scannerAssets} />
        </div>
      </div>
    </div>
  );
}

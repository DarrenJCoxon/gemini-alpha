import { Metadata } from 'next';
import { CouncilFeed } from '@/components/council/council-feed';
import { fetchCouncilSessions } from './council/actions';

export const metadata: Metadata = {
  title: 'Dashboard | ContrarianAI',
  description: 'ContrarianAI Mission Control Dashboard',
};

export default async function DashboardPage() {
  // Server-side initial fetch for council sessions
  let sessions: Awaited<ReturnType<typeof fetchCouncilSessions>>['sessions'] = [];

  try {
    const result = await fetchCouncilSessions({ limit: 10 });
    sessions = result.sessions;
  } catch (error) {
    console.error('Failed to fetch council sessions:', error);
    // Sessions will be empty, component will handle this gracefully
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-zinc-100">Mission Control</h1>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Council Feed - 40% */}
        <div className="lg:col-span-5 bg-zinc-900 rounded-lg border border-zinc-800 p-4 h-[600px]">
          <CouncilFeed initialSessions={sessions} />
        </div>

        {/* Active Trades - 35% (Story 4.3) */}
        <div className="lg:col-span-4 bg-zinc-900 rounded-lg border border-zinc-800 p-4 min-h-[400px]">
          <h2 className="text-lg font-semibold text-zinc-100 mb-4">
            Active Positions
          </h2>
          <p className="text-zinc-400 text-sm">
            Trade cards will be implemented in Story 4.3
          </p>
        </div>

        {/* Scanner - 25% (Story 4.3) */}
        <div className="lg:col-span-3 bg-zinc-900 rounded-lg border border-zinc-800 p-4 min-h-[400px]">
          <h2 className="text-lg font-semibold text-zinc-100 mb-4">
            Market Scanner
          </h2>
          <p className="text-zinc-400 text-sm">
            Scanner table will be implemented in Story 4.3
          </p>
        </div>
      </div>
    </div>
  );
}

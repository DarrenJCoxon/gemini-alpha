import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Dashboard | ContrarianAI',
  description: 'ContrarianAI Mission Control Dashboard',
};

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-zinc-100">Mission Control</h1>

      {/* 3-Column Bento Grid - Placeholder for Story 4.2-4.4 */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Council Feed - 40% */}
        <div className="lg:col-span-5 bg-zinc-900 rounded-lg border border-zinc-800 p-4 min-h-[400px]">
          <h2 className="text-lg font-semibold text-zinc-100 mb-4">
            Council Chamber
          </h2>
          <p className="text-zinc-400 text-sm">
            Council feed will be implemented in Story 4.2
          </p>
        </div>

        {/* Active Trades - 35% */}
        <div className="lg:col-span-4 bg-zinc-900 rounded-lg border border-zinc-800 p-4 min-h-[400px]">
          <h2 className="text-lg font-semibold text-zinc-100 mb-4">
            Active Positions
          </h2>
          <p className="text-zinc-400 text-sm">
            Trade cards will be implemented in Story 4.3
          </p>
        </div>

        {/* Scanner - 25% */}
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

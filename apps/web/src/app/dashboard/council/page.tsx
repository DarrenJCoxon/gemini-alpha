import { Metadata } from 'next';
import { CouncilFeed } from '@/components/council/council-feed';
import { fetchCouncilSessions } from './actions';

export const metadata: Metadata = {
  title: 'Council Chamber | ContrarianAI',
  description: 'View AI Council deliberations and trading decisions',
};

export default async function CouncilPage() {
  // Server-side initial fetch
  let sessions: Awaited<ReturnType<typeof fetchCouncilSessions>>['sessions'] = [];

  try {
    const result = await fetchCouncilSessions({ limit: 20 });
    sessions = result.sessions;
  } catch (error) {
    console.error('Failed to fetch initial council sessions:', error);
    // Sessions will be empty, component will handle this gracefully
  }

  return (
    <div className="h-[calc(100vh-8rem)]">
      <CouncilFeed initialSessions={sessions} />
    </div>
  );
}

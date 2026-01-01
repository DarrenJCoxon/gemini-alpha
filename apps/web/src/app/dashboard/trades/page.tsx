import { Metadata } from 'next';
import { ActiveTrades } from '@/components/trades/active-trades';
import { fetchOpenTrades } from './actions';

export const metadata: Metadata = {
  title: 'Active Trades | ContrarianAI',
  description: 'Monitor your open trading positions',
};

export default async function TradesPage() {
  let trades: Awaited<ReturnType<typeof fetchOpenTrades>> = [];

  try {
    trades = await fetchOpenTrades();
  } catch (error) {
    console.error('Failed to fetch open trades:', error);
    // Trades will be empty, component will handle this gracefully
  }

  return (
    <div className="h-[calc(100vh-8rem)]">
      <ActiveTrades initialTrades={trades} />
    </div>
  );
}

import { User } from '@supabase/supabase-js';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { LogoutButton } from '@/components/auth/logout-button';

interface TopBarProps {
  user: User;
}

export function TopBar({ user }: TopBarProps) {
  return (
    <header className="sticky top-0 z-50 h-14 bg-zinc-900 border-b border-zinc-800 px-4 flex items-center justify-between">
      {/* Left: Logo & Status */}
      <div className="flex items-center gap-4">
        <span className="font-bold text-lg text-zinc-100">ContrarianAI</span>
        <Badge
          variant="outline"
          className="border-emerald-500/50 text-emerald-500"
          aria-label="System Online"
        >
          <span className="w-2 h-2 rounded-full bg-emerald-500 mr-2 animate-pulse" />
          Online
        </Badge>
      </div>

      {/* Center: Equity Ticker (placeholder) */}
      <div className="hidden md:flex items-center gap-6 font-mono text-sm">
        <div>
          <span className="text-zinc-400">Equity:</span>
          <span className="text-zinc-100 ml-2">$10,000.00</span>
        </div>
        <div>
          <span className="text-zinc-400">24h P&L:</span>
          <span className="text-emerald-500 ml-2">+$125.50 (+1.26%)</span>
        </div>
      </div>

      {/* Right: User Menu */}
      <div className="flex items-center gap-3">
        <Avatar className="h-8 w-8">
          <AvatarFallback className="bg-zinc-800 text-zinc-400 text-xs">
            {user.email?.charAt(0).toUpperCase() || 'U'}
          </AvatarFallback>
        </Avatar>
        <LogoutButton />
      </div>
    </header>
  );
}

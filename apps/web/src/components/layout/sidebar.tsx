'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  LayoutDashboard,
  MessageSquare,
  TrendingUp,
  BarChart3,
  Settings,
  History,
} from 'lucide-react';

const navItems = [
  { href: '/dashboard', label: 'Overview', icon: LayoutDashboard },
  { href: '/dashboard/council', label: 'Council Feed', icon: MessageSquare },
  { href: '/dashboard/trades', label: 'Active Trades', icon: TrendingUp },
  { href: '/dashboard/scanner', label: 'Market Scanner', icon: BarChart3 },
  { href: '/dashboard/history', label: 'History', icon: History },
  { href: '/dashboard/settings', label: 'Settings', icon: Settings },
];

interface SidebarProps {
  className?: string;
}

export function Sidebar({ className }: SidebarProps) {
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        'w-60 border-r border-zinc-800 bg-zinc-900 flex flex-col',
        className
      )}
    >
      <ScrollArea className="flex-1 py-4">
        <nav className="space-y-1 px-3">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-zinc-800 text-emerald-500'
                    : 'text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-100'
                )}
                aria-current={isActive ? 'page' : undefined}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </ScrollArea>
    </aside>
  );
}

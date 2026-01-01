'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  MessageSquare,
  TrendingUp,
  BarChart3,
  Settings,
} from 'lucide-react';

const mobileNavItems = [
  { href: '/dashboard', label: 'Home', icon: LayoutDashboard },
  { href: '/dashboard/council', label: 'Council', icon: MessageSquare },
  { href: '/dashboard/trades', label: 'Trades', icon: TrendingUp },
  { href: '/dashboard/scanner', label: 'Scanner', icon: BarChart3 },
  { href: '/dashboard/settings', label: 'Settings', icon: Settings },
];

interface MobileNavProps {
  className?: string;
}

export function MobileNav({ className }: MobileNavProps) {
  const pathname = usePathname();

  return (
    <nav
      className={cn(
        'fixed bottom-0 left-0 right-0 z-50 h-16 bg-zinc-900 border-t border-zinc-800',
        className
      )}
    >
      <div className="flex h-full items-center justify-around">
        {mobileNavItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex flex-col items-center gap-1 px-3 py-2 text-xs',
                isActive ? 'text-emerald-500' : 'text-zinc-400'
              )}
              aria-current={isActive ? 'page' : undefined}
            >
              <Icon className="h-5 w-5" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

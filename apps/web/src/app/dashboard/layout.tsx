import { Sidebar } from '@/components/layout/sidebar';
import { MobileNav } from '@/components/layout/mobile-nav';
import { TopBar } from '@/components/layout/top-bar';
import { createClient } from '@/lib/supabase/server';
import { redirect } from 'next/navigation';

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect('/login');
  }

  return (
    <div className="min-h-screen bg-zinc-950">
      {/* Top Bar - Global Status */}
      <TopBar user={user} />

      {/* Main Layout */}
      <div className="flex">
        {/* Desktop Sidebar */}
        <Sidebar className="hidden lg:flex" />

        {/* Main Content Area */}
        <main className="flex-1 p-4 lg:p-6 pb-20 lg:pb-6">{children}</main>
      </div>

      {/* Mobile Bottom Navigation */}
      <MobileNav className="lg:hidden" />
    </div>
  );
}

# Story 4.1: UI Foundation & Authentication

**Status:** Draft
**Epic:** 4 - Mission Control Dashboard (Next.js)
**Priority:** High

---

## Story

**As a** User,
**I want** to log in to a secure Next.js dashboard with a professional dark mode interface,
**so that** I can access the trading controls securely.

---

## Acceptance Criteria

1. Next.js 15 App (created in Story 1.1) is configured with `Shadcn UI` and `Tailwind CSS`.
2. Theme set to "Zinc" Dark Mode (Zinc-950 background) as per UI Spec.
3. Supabase Authentication integrated:
    - Login Page created.
    - Protected Route (Middleware) ensures only authenticated users see the dashboard.
4. Basic Layout created: Sidebar/Nav (Desktop) and Bottom Tabs (Mobile).

---

## Tasks / Subtasks

### Phase 1: Shadcn UI Setup & Theme Configuration

- [ ] **Initialize Shadcn UI**
  - [ ] Navigate to `apps/web/` directory
  - [ ] Run `npx shadcn@latest init` with these options:
    - Style: Default
    - Base color: Zinc
    - CSS variables: Yes
    - Tailwind config location: `tailwind.config.ts`
    - Components location: `@/components`
    - Utils location: `@/lib/utils`
  - [ ] Verify `components.json` created with correct configuration
  - [ ] Verify `lib/utils.ts` contains `cn()` helper function

- [ ] **Configure Institutional Dark Theme**
  - [ ] Update `app/globals.css` with CSS variables:
    ```css
    @layer base {
      :root {
        --background: 240 10% 3.9%;      /* zinc-950: #09090b */
        --foreground: 0 0% 95.7%;        /* zinc-100: #f4f4f5 */
        --card: 240 10% 6.9%;            /* zinc-900: #18181b */
        --card-foreground: 0 0% 95.7%;
        --popover: 240 10% 6.9%;
        --popover-foreground: 0 0% 95.7%;
        --primary: 160 84% 39%;          /* emerald-500: #10b981 */
        --primary-foreground: 0 0% 100%;
        --secondary: 240 5% 15%;         /* zinc-800: #27272a */
        --secondary-foreground: 0 0% 95.7%;
        --muted: 240 5% 15%;
        --muted-foreground: 240 5% 64.9%; /* zinc-400: #a1a1aa */
        --accent: 160 84% 39%;
        --accent-foreground: 0 0% 100%;
        --destructive: 349 89% 60%;      /* rose-500: #f43f5e */
        --destructive-foreground: 0 0% 100%;
        --warning: 38 92% 50%;           /* amber-500: #f59e0b */
        --border: 240 5% 17%;            /* zinc-800: #27272a */
        --input: 240 5% 17%;
        --ring: 160 84% 39%;
        --radius: 0.5rem;
      }
    }
    ```
  - [ ] Add custom utility classes for semantic colors:
    ```css
    @layer utilities {
      .text-profit { @apply text-emerald-500; }
      .text-loss { @apply text-rose-500; }
      .text-warning { @apply text-amber-500; }
      .bg-surface { @apply bg-zinc-900; }
      .border-subtle { @apply border-zinc-800; }
    }
    ```

- [ ] **Configure Typography (Inter + JetBrains Mono)**
  - [ ] Update `app/layout.tsx`:
    ```tsx
    import { Inter, JetBrains_Mono } from 'next/font/google';

    const inter = Inter({
      subsets: ['latin'],
      variable: '--font-inter',
    });

    const jetbrainsMono = JetBrains_Mono({
      subsets: ['latin'],
      variable: '--font-mono',
    });

    // Apply to html: className={`${inter.variable} ${jetbrainsMono.variable}`}
    ```
  - [ ] Update `tailwind.config.ts` fontFamily:
    ```ts
    fontFamily: {
      sans: ['var(--font-inter)', ...defaultTheme.fontFamily.sans],
      mono: ['var(--font-mono)', ...defaultTheme.fontFamily.mono],
    },
    ```

- [ ] **Install Essential Shadcn Components**
  - [ ] Run `npx shadcn@latest add button`
  - [ ] Run `npx shadcn@latest add card`
  - [ ] Run `npx shadcn@latest add input`
  - [ ] Run `npx shadcn@latest add label`
  - [ ] Run `npx shadcn@latest add badge`
  - [ ] Run `npx shadcn@latest add avatar`
  - [ ] Run `npx shadcn@latest add scroll-area`
  - [ ] Run `npx shadcn@latest add accordion`
  - [ ] Run `npx shadcn@latest add table`
  - [ ] Run `npx shadcn@latest add skeleton`
  - [ ] Run `npx shadcn@latest add sonner` (toast notifications)
  - [ ] Run `npx shadcn@latest add separator`
  - [ ] Run `npx shadcn@latest add sheet` (mobile menu)
  - [ ] Verify all components installed in `components/ui/`

### Phase 2: Supabase Authentication Integration

- [ ] **Install Supabase Auth Dependencies**
  - [ ] Run `pnpm add @supabase/supabase-js @supabase/ssr`
  - [ ] Verify packages added to `apps/web/package.json`

- [ ] **Create Supabase Client Utilities**
  - [ ] Create `lib/supabase/client.ts` (browser client):
    ```typescript
    import { createBrowserClient } from '@supabase/ssr';

    export function createClient() {
      return createBrowserClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL!,
        process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
      );
    }
    ```
  - [ ] Create `lib/supabase/server.ts` (server client):
    ```typescript
    import { createServerClient, type CookieOptions } from '@supabase/ssr';
    import { cookies } from 'next/headers';

    export async function createClient() {
      const cookieStore = await cookies();

      return createServerClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL!,
        process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
        {
          cookies: {
            getAll() {
              return cookieStore.getAll();
            },
            setAll(cookiesToSet) {
              try {
                cookiesToSet.forEach(({ name, value, options }) =>
                  cookieStore.set(name, value, options)
                );
              } catch {
                // Handle server component context
              }
            },
          },
        }
      );
    }
    ```
  - [ ] Create `lib/supabase/middleware.ts` (middleware helper):
    ```typescript
    import { createServerClient, type CookieOptions } from '@supabase/ssr';
    import { NextResponse, type NextRequest } from 'next/server';

    export async function updateSession(request: NextRequest) {
      let supabaseResponse = NextResponse.next({ request });

      const supabase = createServerClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL!,
        process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
        {
          cookies: {
            getAll() {
              return request.cookies.getAll();
            },
            setAll(cookiesToSet) {
              cookiesToSet.forEach(({ name, value, options }) => request.cookies.set(name, value));
              supabaseResponse = NextResponse.next({ request });
              cookiesToSet.forEach(({ name, value, options }) =>
                supabaseResponse.cookies.set(name, value, options)
              );
            },
          },
        }
      );

      const { data: { user } } = await supabase.auth.getUser();

      return { user, supabaseResponse };
    }
    ```

- [ ] **Create Authentication Middleware**
  - [ ] Create `middleware.ts` in `apps/web/`:
    ```typescript
    import { type NextRequest, NextResponse } from 'next/server';
    import { updateSession } from '@/lib/supabase/middleware';

    export async function middleware(request: NextRequest) {
      const { user, supabaseResponse } = await updateSession(request);

      // Protected routes - redirect to login if not authenticated
      if (request.nextUrl.pathname.startsWith('/dashboard')) {
        if (!user) {
          const url = request.nextUrl.clone();
          url.pathname = '/login';
          return NextResponse.redirect(url);
        }
      }

      // Redirect authenticated users away from login
      if (request.nextUrl.pathname === '/login') {
        if (user) {
          const url = request.nextUrl.clone();
          url.pathname = '/dashboard';
          return NextResponse.redirect(url);
        }
      }

      return supabaseResponse;
    }

    export const config = {
      matcher: [
        '/dashboard/:path*',
        '/login',
      ],
    };
    ```

- [ ] **Create Login Page**
  - [ ] Create `app/login/page.tsx`:
    ```typescript
    import { LoginForm } from '@/components/auth/login-form';
    import { Metadata } from 'next';

    export const metadata: Metadata = {
      title: 'Login | ContrarianAI',
      description: 'Access your ContrarianAI Mission Control',
    };

    export default function LoginPage() {
      return (
        <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
          <div className="w-full max-w-md">
            <div className="text-center mb-8">
              <h1 className="text-2xl font-bold text-zinc-100">ContrarianAI</h1>
              <p className="text-zinc-400 mt-2">Mission Control Access</p>
            </div>
            <LoginForm />
          </div>
        </div>
      );
    }
    ```
  - [ ] Create `components/auth/login-form.tsx`:
    ```typescript
    'use client';

    import { useState } from 'react';
    import { useRouter } from 'next/navigation';
    import { createClient } from '@/lib/supabase/client';
    import { Button } from '@/components/ui/button';
    import { Input } from '@/components/ui/input';
    import { Label } from '@/components/ui/label';
    import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

    export function LoginForm() {
      const [email, setEmail] = useState('');
      const [password, setPassword] = useState('');
      const [loading, setLoading] = useState(false);
      const [error, setError] = useState<string | null>(null);
      const router = useRouter();
      const supabase = createClient();

      const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);

        const { error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });

        if (error) {
          setError(error.message);
          setLoading(false);
          return;
        }

        router.push('/dashboard');
        router.refresh();
      };

      return (
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-zinc-100">Sign In</CardTitle>
            <CardDescription className="text-zinc-400">
              Enter your credentials to access the dashboard
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleLogin} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email" className="text-zinc-100">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="operator@contrarian.ai"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="bg-zinc-950 border-zinc-800 text-zinc-100"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password" className="text-zinc-100">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="bg-zinc-950 border-zinc-800 text-zinc-100"
                />
              </div>
              {error && (
                <p className="text-rose-500 text-sm" role="alert">{error}</p>
              )}
              <Button
                type="submit"
                disabled={loading}
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                {loading ? 'Signing in...' : 'Sign In'}
              </Button>
            </form>
          </CardContent>
        </Card>
      );
    }
    ```

- [ ] **Create Auth Callback Route**
  - [ ] Create `app/auth/callback/route.ts`:
    ```typescript
    import { createClient } from '@/lib/supabase/server';
    import { NextResponse } from 'next/server';

    export async function GET(request: Request) {
      const { searchParams, origin } = new URL(request.url);
      const code = searchParams.get('code');
      const next = searchParams.get('next') ?? '/dashboard';

      if (code) {
        const supabase = await createClient();
        const { error } = await supabase.auth.exchangeCodeForSession(code);
        if (!error) {
          return NextResponse.redirect(`${origin}${next}`);
        }
      }

      return NextResponse.redirect(`${origin}/login?error=auth_failed`);
    }
    ```

### Phase 3: Dashboard Layout Implementation

- [ ] **Create Dashboard Layout Structure**
  - [ ] Create `app/dashboard/layout.tsx`:
    ```typescript
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
      const { data: { user } } = await supabase.auth.getUser();

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
            <main className="flex-1 p-4 lg:p-6 pb-20 lg:pb-6">
              {children}
            </main>
          </div>

          {/* Mobile Bottom Navigation */}
          <MobileNav className="lg:hidden" />
        </div>
      );
    }
    ```

- [ ] **Create Top Bar Component**
  - [ ] Create `components/layout/top-bar.tsx`:
    ```typescript
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
    ```

- [ ] **Create Logout Button Component**
  - [ ] Create `components/auth/logout-button.tsx`:
    ```typescript
    'use client';

    import { useRouter } from 'next/navigation';
    import { createClient } from '@/lib/supabase/client';
    import { Button } from '@/components/ui/button';
    import { LogOut } from 'lucide-react';

    export function LogoutButton() {
      const router = useRouter();
      const supabase = createClient();

      const handleLogout = async () => {
        await supabase.auth.signOut();
        router.push('/login');
        router.refresh();
      };

      return (
        <Button
          variant="ghost"
          size="sm"
          onClick={handleLogout}
          className="text-zinc-400 hover:text-zinc-100"
          aria-label="Sign out"
        >
          <LogOut className="h-4 w-4" />
        </Button>
      );
    }
    ```

- [ ] **Create Desktop Sidebar Component**
  - [ ] Create `components/layout/sidebar.tsx`:
    ```typescript
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
    ```

- [ ] **Create Mobile Bottom Navigation**
  - [ ] Create `components/layout/mobile-nav.tsx`:
    ```typescript
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
    ```

- [ ] **Create Dashboard Home Page**
  - [ ] Create `app/dashboard/page.tsx`:
    ```typescript
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
              <h2 className="text-lg font-semibold text-zinc-100 mb-4">Council Chamber</h2>
              <p className="text-zinc-400 text-sm">Council feed will be implemented in Story 4.2</p>
            </div>

            {/* Active Trades - 35% */}
            <div className="lg:col-span-4 bg-zinc-900 rounded-lg border border-zinc-800 p-4 min-h-[400px]">
              <h2 className="text-lg font-semibold text-zinc-100 mb-4">Active Positions</h2>
              <p className="text-zinc-400 text-sm">Trade cards will be implemented in Story 4.3</p>
            </div>

            {/* Scanner - 25% */}
            <div className="lg:col-span-3 bg-zinc-900 rounded-lg border border-zinc-800 p-4 min-h-[400px]">
              <h2 className="text-lg font-semibold text-zinc-100 mb-4">Market Scanner</h2>
              <p className="text-zinc-400 text-sm">Scanner table will be implemented in Story 4.3</p>
            </div>
          </div>
        </div>
      );
    }
    ```

### Phase 4: Environment & Configuration

- [ ] **Configure Environment Variables**
  - [ ] Create/update `apps/web/.env.local.example`:
    ```env
    # Supabase
    NEXT_PUBLIC_SUPABASE_URL=your-supabase-url
    NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-anon-key

    # Database (Prisma)
    DATABASE_URL=postgresql://...
    DIRECT_URL=postgresql://...
    ```
  - [ ] Verify `.gitignore` includes `.env.local`
  - [ ] Add environment variables to Vercel project settings

- [ ] **Install Required Dependencies**
  - [ ] Run `pnpm add lucide-react` (for icons)
  - [ ] Verify `tailwindcss-animate` is installed (from Shadcn)
  - [ ] Verify all peer dependencies resolved

### Phase 5: Testing & Verification

- [ ] **Manual Testing Checklist**
  - [ ] Visit `/login` - verify dark theme displays correctly
  - [ ] Attempt login with invalid credentials - verify error message shows
  - [ ] Login with valid credentials - verify redirect to `/dashboard`
  - [ ] Visit `/dashboard` without auth - verify redirect to `/login`
  - [ ] Verify sidebar navigation works on desktop
  - [ ] Verify bottom tabs work on mobile (Chrome DevTools mobile view)
  - [ ] Verify logout button works correctly
  - [ ] Check WCAG AA contrast compliance using browser dev tools
  - [ ] Verify system status badge has proper `aria-label`

- [ ] **Responsive Design Verification**
  - [ ] Test on viewport widths: 375px, 768px, 1024px, 1440px
  - [ ] Verify sidebar hidden on mobile (< 1024px)
  - [ ] Verify bottom nav hidden on desktop (>= 1024px)
  - [ ] Verify Bento Grid columns stack on mobile

---

## Dev Notes

### Architecture Context

**Reference:** `docs/core/architecture.md` Section 6.2 (Frontend Components)

This story establishes the foundational UI architecture for the ContrarianAI dashboard. All subsequent Epic 4 stories build upon this foundation.

**File Structure Created:**
```
apps/web/
├── app/
│   ├── globals.css          # Theme CSS variables
│   ├── layout.tsx            # Root layout with fonts
│   ├── login/
│   │   └── page.tsx          # Login page
│   ├── auth/
│   │   └── callback/
│   │       └── route.ts      # OAuth callback
│   └── dashboard/
│       ├── layout.tsx        # Protected dashboard layout
│       └── page.tsx          # Dashboard home
├── components/
│   ├── ui/                   # Shadcn components
│   ├── auth/
│   │   ├── login-form.tsx
│   │   └── logout-button.tsx
│   └── layout/
│       ├── sidebar.tsx
│       ├── mobile-nav.tsx
│       └── top-bar.tsx
├── lib/
│   ├── utils.ts              # cn() helper
│   └── supabase/
│       ├── client.ts         # Browser client
│       ├── server.ts         # Server client
│       └── middleware.ts     # Middleware helper
└── middleware.ts             # Route protection
```

### Technical Specifications

**Color System (from uiux.md):**
| Purpose | Tailwind Class | Hex |
|---------|---------------|-----|
| Background | `bg-zinc-950` | #09090b |
| Surface/Cards | `bg-zinc-900` | #18181b |
| Borders | `border-zinc-800` | #27272a |
| Primary/Buy | `text-emerald-500` | #10b981 |
| Destructive/Sell | `text-rose-500` | #f43f5e |
| Warning | `text-amber-500` | #f59e0b |
| Text Primary | `text-zinc-100` | #f4f4f5 |
| Text Muted | `text-zinc-400` | #a1a1aa |

**Typography:**
- UI Font: Inter (variable: `--font-inter`)
- Data Font: JetBrains Mono (variable: `--font-mono`)
- Use `font-mono` class for all prices, scores, timestamps, and tabular data

**Layout Breakpoints:**
- Mobile: < 1024px (bottom tabs, stacked layout)
- Desktop: >= 1024px (sidebar, 3-column Bento Grid)

### Implementation Guidance

**Security Considerations:**
- This dashboard controls real money - authentication must be bulletproof
- All `/dashboard/*` routes protected by middleware
- Session tokens stored in HTTP-only cookies (handled by Supabase SSR)
- Never expose API keys or secrets to client-side code

**Supabase SSR Pattern (Next.js 15):**
The `@supabase/ssr` package is the official way to use Supabase with Next.js App Router. Key points:
- Use `createClient` from `lib/supabase/server.ts` in Server Components
- Use `createClient` from `lib/supabase/client.ts` in Client Components
- Middleware refreshes session tokens automatically

**Shadcn Component Customization:**
When installing Shadcn components, they are copied to `components/ui/`. You can customize them for the dark theme, but prefer using CSS variables over hardcoded colors for consistency.

### Accessibility Requirements

**WCAG AA Compliance:**
- All text must have 4.5:1 contrast ratio against background
- Interactive elements must have visible focus states
- Status indicators (Online/Offline) must have `aria-label`
- Navigation links must indicate current page with `aria-current="page"`
- Form inputs must have associated `<Label>` elements
- Error messages must use `role="alert"`

**Keyboard Navigation:**
- All interactive elements must be focusable
- Tab order must be logical (left-to-right, top-to-bottom)
- Mobile nav should be keyboard accessible

### Dependencies & Prerequisites

**Required Completions:**
- Story 1.1: Next.js 15 app exists in `apps/web/`
- Story 1.2: Database schema includes User table (via Supabase Auth)
- Supabase project configured with Auth enabled

**Environment Requirements:**
- `NEXT_PUBLIC_SUPABASE_URL` - Supabase project URL
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` - Supabase anonymous key
- Supabase Email/Password auth provider enabled

### Downstream Dependencies

- **Story 4.2**: Builds upon layout, adds CouncilFeed component
- **Story 4.3**: Builds upon layout, adds TradeCard and Scanner components
- **Story 4.4**: Adds realtime subscriptions and toast notifications

---

## Testing Strategy

### Component Tests (Future)

- [ ] Test `LoginForm` renders correctly
- [ ] Test `LoginForm` shows error on failed login
- [ ] Test `LoginForm` redirects on successful login
- [ ] Test `Sidebar` highlights active route
- [ ] Test `MobileNav` highlights active route

### Integration Tests

- [ ] Test middleware redirects unauthenticated users
- [ ] Test middleware allows authenticated users
- [ ] Test logout clears session

### Manual Testing Scenarios

1. Fresh browser - visit `/dashboard` - should redirect to `/login`
2. Login with email/password - should redirect to `/dashboard`
3. Refresh `/dashboard` - should stay authenticated
4. Click logout - should redirect to `/login`
5. Try to navigate back - should not access `/dashboard`

### Acceptance Criteria Validation

- [ ] AC1: Shadcn UI initialized, Tailwind configured with Zinc dark theme
- [ ] AC2: Background is Zinc-950 (#09090b), surfaces are Zinc-900
- [ ] AC3a: Login page functional with Supabase
- [ ] AC3b: Middleware protects dashboard routes
- [ ] AC4: Sidebar visible on desktop, bottom tabs on mobile

---

## Technical Considerations

### Security

- **Session Management**: Supabase SSR handles secure cookie-based sessions
- **CSRF Protection**: Built into Supabase auth flow
- **XSS Prevention**: React escapes by default; avoid `dangerouslySetInnerHTML`
- **Route Protection**: Middleware runs on edge, checking auth before page load

### Performance

- **Font Loading**: Use `next/font` for optimized font loading
- **Component Size**: Shadcn components are tree-shakeable
- **CSS**: Tailwind purges unused styles in production

### Edge Cases

- **Expired Session**: Middleware detects and redirects to login
- **Network Error on Login**: Display user-friendly error message
- **Missing Environment Variables**: App should fail fast with clear error
- **Cookie Disabled**: Supabase requires cookies for auth

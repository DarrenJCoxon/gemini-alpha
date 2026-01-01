import { type NextRequest, NextResponse } from 'next/server';
import { updateSession } from '@/lib/supabase/middleware';

/**
 * Next.js Middleware for authentication and route protection.
 *
 * This middleware:
 * 1. Refreshes the user's auth session
 * 2. Protects /dashboard/* routes (redirects to /login if not authenticated)
 * 3. Redirects authenticated users away from /login to /dashboard
 */
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

  // Redirect authenticated users away from login page
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
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder
     */
    '/dashboard/:path*',
    '/login',
  ],
};

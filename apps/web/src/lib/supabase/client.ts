import { createBrowserClient } from '@supabase/ssr';

/**
 * Creates a Supabase client for browser/client-side usage.
 * This client is used in Client Components (marked with 'use client').
 */
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}

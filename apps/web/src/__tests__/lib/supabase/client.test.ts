/**
 * @jest-environment node
 */

import { createClient } from '@/lib/supabase/client';

// Mock @supabase/ssr
jest.mock('@supabase/ssr', () => ({
  createBrowserClient: jest.fn(() => ({
    auth: {
      signInWithPassword: jest.fn(),
      signOut: jest.fn(),
    },
  })),
}));

import { createBrowserClient } from '@supabase/ssr';
const mockCreateBrowserClient = createBrowserClient as jest.Mock;

describe('Supabase Browser Client', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    jest.clearAllMocks();
    process.env = {
      ...originalEnv,
      NEXT_PUBLIC_SUPABASE_URL: 'https://test.supabase.co',
      NEXT_PUBLIC_SUPABASE_ANON_KEY: 'test-anon-key',
    };
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  it('should create a browser client with correct config', () => {
    createClient();

    expect(mockCreateBrowserClient).toHaveBeenCalledWith(
      'https://test.supabase.co',
      'test-anon-key'
    );
  });

  it('should return the client instance', () => {
    const client = createClient();

    expect(client).toBeDefined();
    expect(client.auth).toBeDefined();
    expect(client.auth.signInWithPassword).toBeDefined();
    expect(client.auth.signOut).toBeDefined();
  });
});

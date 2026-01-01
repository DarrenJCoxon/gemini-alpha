/**
 * @jest-environment node
 */

import { updateSession } from '@/lib/supabase/middleware';
import { NextRequest } from 'next/server';

// Mock @supabase/ssr
const mockGetUser = jest.fn();
jest.mock('@supabase/ssr', () => ({
  createServerClient: jest.fn(() => ({
    auth: {
      getUser: mockGetUser,
    },
  })),
}));

describe('Supabase Middleware Helper', () => {
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

  it('should return user when authenticated', async () => {
    const mockUser = { id: '123', email: 'test@example.com' };
    mockGetUser.mockResolvedValueOnce({ data: { user: mockUser } });

    const request = new NextRequest('http://localhost:3000/dashboard');
    const result = await updateSession(request);

    expect(result.user).toEqual(mockUser);
    expect(result.supabaseResponse).toBeDefined();
  });

  it('should return null user when not authenticated', async () => {
    mockGetUser.mockResolvedValueOnce({ data: { user: null } });

    const request = new NextRequest('http://localhost:3000/dashboard');
    const result = await updateSession(request);

    expect(result.user).toBeNull();
    expect(result.supabaseResponse).toBeDefined();
  });

  it('should return a valid NextResponse', async () => {
    mockGetUser.mockResolvedValueOnce({ data: { user: null } });

    const request = new NextRequest('http://localhost:3000/dashboard');
    const result = await updateSession(request);

    expect(result.supabaseResponse).toBeDefined();
    expect(result.supabaseResponse.headers).toBeDefined();
  });
});

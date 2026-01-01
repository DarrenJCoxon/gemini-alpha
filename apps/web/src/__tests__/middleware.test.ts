/**
 * @jest-environment node
 */

import { middleware } from '@/middleware';
import { NextRequest } from 'next/server';

// Mock the updateSession function
const mockUpdateSession = jest.fn();
jest.mock('@/lib/supabase/middleware', () => ({
  updateSession: () => mockUpdateSession(),
}));

describe('Authentication Middleware', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Protected routes (/dashboard/*)', () => {
    it('should redirect to login when user is not authenticated', async () => {
      mockUpdateSession.mockResolvedValueOnce({
        user: null,
        supabaseResponse: {
          headers: new Headers(),
        },
      });

      const request = new NextRequest('http://localhost:3000/dashboard');
      const response = await middleware(request);

      expect(response.status).toBe(307); // Redirect status
      expect(response.headers.get('location')).toContain('/login');
    });

    it('should allow access when user is authenticated', async () => {
      const mockResponse = {
        headers: new Headers(),
        status: 200,
      };
      mockUpdateSession.mockResolvedValueOnce({
        user: { id: '123', email: 'test@example.com' },
        supabaseResponse: mockResponse,
      });

      const request = new NextRequest('http://localhost:3000/dashboard');
      const response = await middleware(request);

      // Should return the supabaseResponse, not a redirect
      expect(response).toBe(mockResponse);
    });

    it('should protect nested dashboard routes', async () => {
      mockUpdateSession.mockResolvedValueOnce({
        user: null,
        supabaseResponse: {
          headers: new Headers(),
        },
      });

      const request = new NextRequest(
        'http://localhost:3000/dashboard/settings'
      );
      const response = await middleware(request);

      expect(response.status).toBe(307);
      expect(response.headers.get('location')).toContain('/login');
    });
  });

  describe('Login route', () => {
    it('should redirect to dashboard when user is already authenticated', async () => {
      mockUpdateSession.mockResolvedValueOnce({
        user: { id: '123', email: 'test@example.com' },
        supabaseResponse: {
          headers: new Headers(),
        },
      });

      const request = new NextRequest('http://localhost:3000/login');
      const response = await middleware(request);

      expect(response.status).toBe(307);
      expect(response.headers.get('location')).toContain('/dashboard');
    });

    it('should allow access to login when user is not authenticated', async () => {
      const mockResponse = {
        headers: new Headers(),
        status: 200,
      };
      mockUpdateSession.mockResolvedValueOnce({
        user: null,
        supabaseResponse: mockResponse,
      });

      const request = new NextRequest('http://localhost:3000/login');
      const response = await middleware(request);

      expect(response).toBe(mockResponse);
    });
  });
});

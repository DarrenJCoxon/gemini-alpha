/**
 * @jest-environment jsdom
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { LogoutButton } from '@/components/auth/logout-button';

// Mock next/navigation
const mockPush = jest.fn();
const mockRefresh = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    refresh: mockRefresh,
  }),
}));

// Mock Supabase client
const mockSignOut = jest.fn();
jest.mock('@/lib/supabase/client', () => ({
  createClient: () => ({
    auth: {
      signOut: mockSignOut,
    },
  }),
}));

describe('LogoutButton', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should render logout button with icon', () => {
    render(<LogoutButton />);

    const button = screen.getByRole('button', { name: /sign out/i });
    expect(button).toBeInTheDocument();
  });

  it('should have correct accessibility label', () => {
    render(<LogoutButton />);

    const button = screen.getByRole('button', { name: /sign out/i });
    expect(button).toHaveAttribute('aria-label', 'Sign out');
  });

  it('should call signOut and redirect to login on click', async () => {
    mockSignOut.mockResolvedValueOnce({});

    render(<LogoutButton />);

    const button = screen.getByRole('button', { name: /sign out/i });
    fireEvent.click(button);

    await waitFor(() => {
      expect(mockSignOut).toHaveBeenCalled();
      expect(mockPush).toHaveBeenCalledWith('/login');
      expect(mockRefresh).toHaveBeenCalled();
    });
  });

  it('should have ghost variant styling', () => {
    render(<LogoutButton />);

    const button = screen.getByRole('button', { name: /sign out/i });
    // Check it has the expected base classes (ghost variant uses specific styling)
    expect(button).toHaveClass('text-zinc-400');
  });
});

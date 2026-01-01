/**
 * @jest-environment jsdom
 */

import { render, screen } from '@testing-library/react';
import { TopBar } from '@/components/layout/top-bar';
import { User } from '@supabase/supabase-js';

// Mock the LogoutButton since it has its own tests
jest.mock('@/components/auth/logout-button', () => ({
  LogoutButton: () => (
    <button aria-label="Sign out" data-testid="logout-button">
      Logout
    </button>
  ),
}));

const mockUser: User = {
  id: '123',
  email: 'test@example.com',
  app_metadata: {},
  user_metadata: {},
  aud: 'authenticated',
  created_at: '2024-01-01T00:00:00.000Z',
};

describe('TopBar', () => {
  it('should render the logo', () => {
    render(<TopBar user={mockUser} />);

    expect(screen.getByText('ContrarianAI')).toBeInTheDocument();
  });

  it('should render the online status badge', () => {
    render(<TopBar user={mockUser} />);

    expect(screen.getByText('Online')).toBeInTheDocument();
  });

  it('should have accessible status badge with aria-label', () => {
    render(<TopBar user={mockUser} />);

    const badge = screen.getByLabelText('System Online');
    expect(badge).toBeInTheDocument();
  });

  it('should display user avatar with first letter of email', () => {
    render(<TopBar user={mockUser} />);

    expect(screen.getByText('T')).toBeInTheDocument();
  });

  it('should display placeholder equity ticker', () => {
    render(<TopBar user={mockUser} />);

    expect(screen.getByText('Equity:')).toBeInTheDocument();
    expect(screen.getByText('$10,000.00')).toBeInTheDocument();
  });

  it('should display placeholder P&L', () => {
    render(<TopBar user={mockUser} />);

    expect(screen.getByText('24h P&L:')).toBeInTheDocument();
    expect(screen.getByText('+$125.50 (+1.26%)')).toBeInTheDocument();
  });

  it('should render the logout button', () => {
    render(<TopBar user={mockUser} />);

    expect(screen.getByTestId('logout-button')).toBeInTheDocument();
  });

  it('should handle user without email gracefully', () => {
    const userWithoutEmail: User = {
      ...mockUser,
      email: undefined,
    };

    render(<TopBar user={userWithoutEmail} />);

    // Should show 'U' as fallback
    expect(screen.getByText('U')).toBeInTheDocument();
  });

  it('should be sticky at top', () => {
    render(<TopBar user={mockUser} />);

    const header = screen.getByRole('banner');
    expect(header).toHaveClass('sticky');
    expect(header).toHaveClass('top-0');
  });

  it('should have proper dark theme styling', () => {
    render(<TopBar user={mockUser} />);

    const header = screen.getByRole('banner');
    expect(header).toHaveClass('bg-zinc-900');
    expect(header).toHaveClass('border-zinc-800');
  });
});

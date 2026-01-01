/**
 * @jest-environment jsdom
 */

import { render, screen } from '@testing-library/react';
import { MobileNav } from '@/components/layout/mobile-nav';

// Mock next/navigation
jest.mock('next/navigation', () => ({
  usePathname: jest.fn(),
}));

import { usePathname } from 'next/navigation';
const mockUsePathname = usePathname as jest.Mock;

describe('MobileNav', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUsePathname.mockReturnValue('/dashboard');
  });

  it('should render mobile navigation items', () => {
    render(<MobileNav />);

    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Council')).toBeInTheDocument();
    expect(screen.getByText('Trades')).toBeInTheDocument();
    expect(screen.getByText('Scanner')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('should have correct links for navigation items', () => {
    render(<MobileNav />);

    expect(screen.getByRole('link', { name: /home/i })).toHaveAttribute(
      'href',
      '/dashboard'
    );
    expect(screen.getByRole('link', { name: /council/i })).toHaveAttribute(
      'href',
      '/dashboard/council'
    );
    expect(screen.getByRole('link', { name: /trades/i })).toHaveAttribute(
      'href',
      '/dashboard/trades'
    );
    expect(screen.getByRole('link', { name: /scanner/i })).toHaveAttribute(
      'href',
      '/dashboard/scanner'
    );
    expect(screen.getByRole('link', { name: /settings/i })).toHaveAttribute(
      'href',
      '/dashboard/settings'
    );
  });

  it('should highlight active route with aria-current', () => {
    mockUsePathname.mockReturnValue('/dashboard');
    render(<MobileNav />);

    const homeLink = screen.getByRole('link', { name: /home/i });
    expect(homeLink).toHaveAttribute('aria-current', 'page');
  });

  it('should not highlight inactive routes', () => {
    mockUsePathname.mockReturnValue('/dashboard');
    render(<MobileNav />);

    const settingsLink = screen.getByRole('link', { name: /settings/i });
    expect(settingsLink).not.toHaveAttribute('aria-current');
  });

  it('should apply active styles to current route', () => {
    mockUsePathname.mockReturnValue('/dashboard/trades');
    render(<MobileNav />);

    const tradesLink = screen.getByRole('link', { name: /trades/i });
    expect(tradesLink).toHaveClass('text-emerald-500');
  });

  it('should apply inactive styles to non-current routes', () => {
    mockUsePathname.mockReturnValue('/dashboard');
    render(<MobileNav />);

    const settingsLink = screen.getByRole('link', { name: /settings/i });
    expect(settingsLink).toHaveClass('text-zinc-400');
  });

  it('should accept additional className prop', () => {
    render(<MobileNav className="lg:hidden" />);

    const nav = screen.getByRole('navigation');
    expect(nav).toHaveClass('lg:hidden');
  });

  it('should be fixed at bottom of screen', () => {
    render(<MobileNav />);

    const nav = screen.getByRole('navigation');
    expect(nav).toHaveClass('fixed');
    expect(nav).toHaveClass('bottom-0');
  });
});

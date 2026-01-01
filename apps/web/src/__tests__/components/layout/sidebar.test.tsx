/**
 * @jest-environment jsdom
 */

import { render, screen } from '@testing-library/react';
import { Sidebar } from '@/components/layout/sidebar';

// Mock next/navigation
jest.mock('next/navigation', () => ({
  usePathname: jest.fn(),
}));

import { usePathname } from 'next/navigation';
const mockUsePathname = usePathname as jest.Mock;

describe('Sidebar', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUsePathname.mockReturnValue('/dashboard');
  });

  it('should render all navigation items', () => {
    render(<Sidebar />);

    expect(screen.getByText('Overview')).toBeInTheDocument();
    expect(screen.getByText('Council Feed')).toBeInTheDocument();
    expect(screen.getByText('Active Trades')).toBeInTheDocument();
    expect(screen.getByText('Market Scanner')).toBeInTheDocument();
    expect(screen.getByText('History')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('should have correct links for navigation items', () => {
    render(<Sidebar />);

    expect(screen.getByRole('link', { name: /overview/i })).toHaveAttribute(
      'href',
      '/dashboard'
    );
    expect(screen.getByRole('link', { name: /council feed/i })).toHaveAttribute(
      'href',
      '/dashboard/council'
    );
    expect(
      screen.getByRole('link', { name: /active trades/i })
    ).toHaveAttribute('href', '/dashboard/trades');
    expect(
      screen.getByRole('link', { name: /market scanner/i })
    ).toHaveAttribute('href', '/dashboard/scanner');
    expect(screen.getByRole('link', { name: /history/i })).toHaveAttribute(
      'href',
      '/dashboard/history'
    );
    expect(screen.getByRole('link', { name: /settings/i })).toHaveAttribute(
      'href',
      '/dashboard/settings'
    );
  });

  it('should highlight active route with aria-current', () => {
    mockUsePathname.mockReturnValue('/dashboard');
    render(<Sidebar />);

    const overviewLink = screen.getByRole('link', { name: /overview/i });
    expect(overviewLink).toHaveAttribute('aria-current', 'page');
  });

  it('should not highlight inactive routes', () => {
    mockUsePathname.mockReturnValue('/dashboard');
    render(<Sidebar />);

    const settingsLink = screen.getByRole('link', { name: /settings/i });
    expect(settingsLink).not.toHaveAttribute('aria-current');
  });

  it('should apply active styles to current route', () => {
    mockUsePathname.mockReturnValue('/dashboard/council');
    render(<Sidebar />);

    const councilLink = screen.getByRole('link', { name: /council feed/i });
    expect(councilLink).toHaveClass('text-emerald-500');
    expect(councilLink).toHaveClass('bg-zinc-800');
  });

  it('should apply inactive styles to non-current routes', () => {
    mockUsePathname.mockReturnValue('/dashboard');
    render(<Sidebar />);

    const settingsLink = screen.getByRole('link', { name: /settings/i });
    expect(settingsLink).toHaveClass('text-zinc-400');
  });

  it('should accept additional className prop', () => {
    render(<Sidebar className="hidden lg:flex" />);

    const sidebar = screen.getByRole('complementary');
    expect(sidebar).toHaveClass('hidden');
    expect(sidebar).toHaveClass('lg:flex');
  });

  it('should render as aside element', () => {
    render(<Sidebar />);

    expect(screen.getByRole('complementary')).toBeInTheDocument();
  });
});

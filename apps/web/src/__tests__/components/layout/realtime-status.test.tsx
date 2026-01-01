/**
 * @jest-environment jsdom
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { RealtimeStatusIndicator } from '@/components/layout/realtime-status';
import { useRealtimeStatus, RealtimeStatus } from '@/hooks/use-realtime-status';

// Mock the hook
jest.mock('@/hooks/use-realtime-status', () => ({
  useRealtimeStatus: jest.fn(),
}));

const mockUseRealtimeStatus = useRealtimeStatus as jest.Mock;

describe('RealtimeStatusIndicator Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Connecting State', () => {
    beforeEach(() => {
      mockUseRealtimeStatus.mockReturnValue('connecting');
    });

    it('should display "Connecting" text', () => {
      render(<RealtimeStatusIndicator />);

      expect(screen.getByText('Connecting')).toBeInTheDocument();
    });

    it('should have correct data-status attribute', () => {
      render(<RealtimeStatusIndicator />);

      const indicator = screen.getByTestId('realtime-status-indicator');
      expect(indicator).toHaveAttribute('data-status', 'connecting');
    });

    it('should have amber color styling', () => {
      render(<RealtimeStatusIndicator />);

      const indicator = screen.getByTestId('realtime-status-indicator');
      expect(indicator.className).toContain('border-amber-500/50');
      expect(indicator.className).toContain('text-amber-500');
    });
  });

  describe('Connected State', () => {
    beforeEach(() => {
      mockUseRealtimeStatus.mockReturnValue('connected');
    });

    it('should display "Live" text', () => {
      render(<RealtimeStatusIndicator />);

      expect(screen.getByText('Live')).toBeInTheDocument();
    });

    it('should have correct data-status attribute', () => {
      render(<RealtimeStatusIndicator />);

      const indicator = screen.getByTestId('realtime-status-indicator');
      expect(indicator).toHaveAttribute('data-status', 'connected');
    });

    it('should have emerald color styling', () => {
      render(<RealtimeStatusIndicator />);

      const indicator = screen.getByTestId('realtime-status-indicator');
      expect(indicator.className).toContain('border-emerald-500/50');
      expect(indicator.className).toContain('text-emerald-500');
    });
  });

  describe('Disconnected State', () => {
    beforeEach(() => {
      mockUseRealtimeStatus.mockReturnValue('disconnected');
    });

    it('should display "Offline" text', () => {
      render(<RealtimeStatusIndicator />);

      expect(screen.getByText('Offline')).toBeInTheDocument();
    });

    it('should have correct data-status attribute', () => {
      render(<RealtimeStatusIndicator />);

      const indicator = screen.getByTestId('realtime-status-indicator');
      expect(indicator).toHaveAttribute('data-status', 'disconnected');
    });

    it('should have rose color styling', () => {
      render(<RealtimeStatusIndicator />);

      const indicator = screen.getByTestId('realtime-status-indicator');
      expect(indicator.className).toContain('border-rose-500/50');
      expect(indicator.className).toContain('text-rose-500');
    });
  });

  describe('Error State', () => {
    beforeEach(() => {
      mockUseRealtimeStatus.mockReturnValue('error');
    });

    it('should display "Error" text', () => {
      render(<RealtimeStatusIndicator />);

      expect(screen.getByText('Error')).toBeInTheDocument();
    });

    it('should have correct data-status attribute', () => {
      render(<RealtimeStatusIndicator />);

      const indicator = screen.getByTestId('realtime-status-indicator');
      expect(indicator).toHaveAttribute('data-status', 'error');
    });

    it('should have rose color styling', () => {
      render(<RealtimeStatusIndicator />);

      const indicator = screen.getByTestId('realtime-status-indicator');
      expect(indicator.className).toContain('border-rose-500/50');
      expect(indicator.className).toContain('text-rose-500');
    });
  });

  describe('Accessibility', () => {
    it('should have aria-label for connected state', () => {
      mockUseRealtimeStatus.mockReturnValue('connected');
      render(<RealtimeStatusIndicator />);

      const indicator = screen.getByTestId('realtime-status-indicator');
      expect(indicator).toHaveAttribute('aria-label', 'Realtime connection: Live');
    });

    it('should have aria-label for disconnected state', () => {
      mockUseRealtimeStatus.mockReturnValue('disconnected');
      render(<RealtimeStatusIndicator />);

      const indicator = screen.getByTestId('realtime-status-indicator');
      expect(indicator).toHaveAttribute('aria-label', 'Realtime connection: Offline');
    });

    it('should have aria-label for connecting state', () => {
      mockUseRealtimeStatus.mockReturnValue('connecting');
      render(<RealtimeStatusIndicator />);

      const indicator = screen.getByTestId('realtime-status-indicator');
      expect(indicator).toHaveAttribute('aria-label', 'Realtime connection: Connecting');
    });

    it('should have aria-label for error state', () => {
      mockUseRealtimeStatus.mockReturnValue('error');
      render(<RealtimeStatusIndicator />);

      const indicator = screen.getByTestId('realtime-status-indicator');
      expect(indicator).toHaveAttribute('aria-label', 'Realtime connection: Error');
    });
  });

  describe('Component Structure', () => {
    it('should render as a Badge component', () => {
      mockUseRealtimeStatus.mockReturnValue('connected');
      render(<RealtimeStatusIndicator />);

      const indicator = screen.getByTestId('realtime-status-indicator');
      // Badge renders as a span element
      expect(indicator.tagName.toLowerCase()).toBe('span');
    });

    it('should have outline variant styling', () => {
      mockUseRealtimeStatus.mockReturnValue('connected');
      render(<RealtimeStatusIndicator />);

      const indicator = screen.getByTestId('realtime-status-indicator');
      // Badge with outline variant should have border styling
      expect(indicator.className).toContain('border');
    });
  });
});

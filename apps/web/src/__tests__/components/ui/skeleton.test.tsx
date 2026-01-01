/**
 * @jest-environment jsdom
 */

import { render, screen } from '@testing-library/react';
import { Skeleton } from '@/components/ui/skeleton';

describe('Skeleton Component', () => {
  it('should render skeleton element', () => {
    render(<Skeleton data-testid="skeleton" />);

    const skeleton = screen.getByTestId('skeleton');
    expect(skeleton).toBeInTheDocument();
  });

  it('should have animation class', () => {
    render(<Skeleton data-testid="skeleton" />);

    const skeleton = screen.getByTestId('skeleton');
    expect(skeleton).toHaveClass('animate-pulse');
  });

  it('should have background class', () => {
    render(<Skeleton data-testid="skeleton" />);

    const skeleton = screen.getByTestId('skeleton');
    expect(skeleton).toHaveClass('bg-muted');
  });

  it('should have rounded corners', () => {
    render(<Skeleton data-testid="skeleton" />);

    const skeleton = screen.getByTestId('skeleton');
    expect(skeleton).toHaveClass('rounded-md');
  });

  it('should accept additional className', () => {
    render(<Skeleton data-testid="skeleton" className="h-10 w-full" />);

    const skeleton = screen.getByTestId('skeleton');
    expect(skeleton).toHaveClass('h-10');
    expect(skeleton).toHaveClass('w-full');
  });

  it('should have data-slot attribute', () => {
    render(<Skeleton data-testid="skeleton" />);

    const skeleton = screen.getByTestId('skeleton');
    expect(skeleton).toHaveAttribute('data-slot', 'skeleton');
  });
});

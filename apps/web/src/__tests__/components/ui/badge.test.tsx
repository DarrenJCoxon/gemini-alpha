/**
 * @jest-environment jsdom
 */

import { render, screen } from '@testing-library/react';
import { Badge } from '@/components/ui/badge';

describe('Badge Component', () => {
  it('should render badge with default variant', () => {
    render(<Badge>Default Badge</Badge>);

    const badge = screen.getByText('Default Badge');
    expect(badge).toBeInTheDocument();
  });

  it('should render badge with secondary variant', () => {
    render(<Badge variant="secondary">Secondary Badge</Badge>);

    const badge = screen.getByText('Secondary Badge');
    expect(badge).toBeInTheDocument();
  });

  it('should render badge with destructive variant', () => {
    render(<Badge variant="destructive">Destructive Badge</Badge>);

    const badge = screen.getByText('Destructive Badge');
    expect(badge).toBeInTheDocument();
  });

  it('should render badge with outline variant', () => {
    render(<Badge variant="outline">Outline Badge</Badge>);

    const badge = screen.getByText('Outline Badge');
    expect(badge).toBeInTheDocument();
  });

  it('should accept additional className', () => {
    render(<Badge className="custom-class">Custom Badge</Badge>);

    const badge = screen.getByText('Custom Badge');
    expect(badge).toHaveClass('custom-class');
  });

  it('should render with data-slot attribute', () => {
    render(<Badge>Test Badge</Badge>);

    const badge = screen.getByText('Test Badge');
    expect(badge).toHaveAttribute('data-slot', 'badge');
  });

  it('should render children correctly', () => {
    render(
      <Badge>
        <span data-testid="child-element">Child Element</span>
      </Badge>
    );

    expect(screen.getByTestId('child-element')).toBeInTheDocument();
  });
});

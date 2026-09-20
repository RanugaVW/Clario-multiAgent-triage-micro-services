import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Card } from './Card';

describe('Card', () => {
  it('renders children on a bordered surface with card padding', () => {
    render(<Card>Body</Card>);
    const cls = screen.getByText('Body').className;
    expect(cls).toContain('bg-surface');
    expect(cls).toContain('border-border');
    expect(cls).toContain('p-card');
  });

  it('can be raised for overlays and floating panels', () => {
    render(<Card raised>Floating</Card>);
    expect(screen.getByText('Floating').className).toContain('shadow-raised');
  });

  it('passes through props and extra classes', () => {
    render(<Card data-testid="c" className="mt-4" />);
    expect(screen.getByTestId('c').className).toContain('mt-4');
  });
});

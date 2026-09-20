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

  it('has the exact class token p-card by default', () => {
    render(<Card data-testid="c">Default</Card>);
    const cls = screen.getByTestId('c').className;
    expect(cls.split(' ')).toContain('p-card');
  });

  it('does not emit p-card when flush is true', () => {
    render(<Card flush data-testid="c">Flush</Card>);
    const cls = screen.getByTestId('c').className;
    expect(cls.split(' ')).not.toContain('p-card');
  });

  it('does not pass flush as a DOM attribute', () => {
    const { container } = render(<Card flush data-testid="c">Flush</Card>);
    const element = container.querySelector('[data-testid="c"]');
    expect(element).not.toHaveAttribute('flush');
  });
});

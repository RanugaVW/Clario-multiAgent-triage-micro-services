import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Badge } from './Badge';

describe('Badge', () => {
  it('renders its label', () => {
    render(<Badge>Resolved</Badge>);
    expect(screen.getByText('Resolved')).toBeInTheDocument();
  });

  it('is neutral by default', () => {
    render(<Badge>Open</Badge>);
    expect(screen.getByText('Open').className).toContain('text-fg-muted');
  });

  it.each([
    ['success', 'text-success'],
    ['warning', 'text-warning'],
    ['danger', 'text-danger'],
    ['info', 'text-info'],
    ['accent', 'text-accent'],
    ['brand', 'text-brand'],
  ] as const)('%s tone uses %s', (tone, cls) => {
    render(<Badge tone={tone}>x</Badge>);
    expect(screen.getByText('x').className).toContain(cls);
  });

  it.each(['brand', 'accent', 'success', 'warning', 'danger', 'info'] as const)(
    '%s tone sits on a solid surface, never a tinted fill',
    (tone) => {
      render(<Badge tone={tone}>x</Badge>);
      const tokens = screen.getByText('x').className.split(' ');
      expect(tokens).toContain('bg-surface');
      expect(tokens).toContain(`border-${tone}/40`);
      expect(tokens.some((t) => t.includes('/15') || t.startsWith('bg-brand-soft'))).toBe(false);
    }
  );
});

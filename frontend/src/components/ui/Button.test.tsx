import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Button, ButtonLink, buttonClass } from './Button';

describe('Button', () => {
  it('defaults to type="button" so it never submits a form by accident', () => {
    render(<Button>Save</Button>);
    expect(screen.getByRole('button', { name: 'Save' })).toHaveAttribute('type', 'button');
  });

  it('can still be a submit button', () => {
    render(<Button type="submit">Send</Button>);
    expect(screen.getByRole('button', { name: 'Send' })).toHaveAttribute('type', 'submit');
  });

  it('is the primary variant at medium size by default', () => {
    render(<Button>Save</Button>);
    const cls = screen.getByRole('button').className;
    expect(cls).toContain('bg-brand');
    expect(cls).toContain('h-10');
  });

  it('applies the requested variant and size', () => {
    render(
      <Button variant="destructive" size="lg">
        Delete
      </Button>
    );
    const cls = screen.getByRole('button').className;
    expect(cls).toContain('bg-danger');
    expect(cls).toContain('h-12');
  });

  it('keeps classes passed by the caller', () => {
    render(<Button className="w-full">Wide</Button>);
    expect(screen.getByRole('button').className).toContain('w-full');
  });

  it('respects disabled', () => {
    render(<Button disabled>Nope</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });
});

describe('ButtonLink', () => {
  it('renders a real link with button styling', () => {
    render(<ButtonLink href="/register" variant="secondary">Get started</ButtonLink>);
    const link = screen.getByRole('link', { name: 'Get started' });
    expect(link).toHaveAttribute('href', '/register');
    expect(link.className).toContain('border-border-strong');
  });
});

describe('buttonClass', () => {
  it('returns the same classes for use on any element', () => {
    expect(buttonClass({ variant: 'ghost', size: 'sm' })).toContain('h-8');
  });
});

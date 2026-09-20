import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Notice } from './Notice';

describe('Notice', () => {
  it('renders its message with the role it is given', () => {
    render(<Notice tone="danger" role="alert">Invalid login credentials</Notice>);
    expect(screen.getByRole('alert')).toHaveTextContent('Invalid login credentials');
  });

  it('can be a polite status message with a title', () => {
    render(
      <Notice tone="success" role="status" title="Check your email">
        We sent you a link.
      </Notice>
    );
    const status = screen.getByRole('status');
    expect(status).toHaveTextContent('Check your email');
    expect(status).toHaveTextContent('We sent you a link.');
  });

  it('has no role unless one is given', () => {
    const { container } = render(<Notice tone="info">FYI</Notice>);
    expect((container.firstElementChild as HTMLElement).getAttribute('role')).toBeNull();
  });

  it.each([
    ['success', 'text-success'],
    ['danger', 'text-danger'],
    ['info', 'text-info'],
  ] as const)('%s uses the %s token on a solid surface', (tone, cls) => {
    const { container } = render(<Notice tone={tone}>x</Notice>);
    const tokens = (container.firstElementChild as HTMLElement).className.split(' ');
    expect(tokens).toContain(cls);
    expect(tokens).toContain('bg-surface');
  });

  it('takes focus on mount only when focusOnMount is set', () => {
    render(
      <Notice tone="success" role="status" focusOnMount>
        Done
      </Notice>
    );
    const status = screen.getByRole('status');
    expect(status).toHaveFocus();
    expect(status).toHaveAttribute('tabindex', '-1');
  });

  it('does not take focus or become focusable by default', () => {
    render(
      <Notice tone="success" role="status">
        Done
      </Notice>
    );
    const status = screen.getByRole('status');
    expect(status).not.toHaveFocus();
    expect(document.body).toHaveFocus();
    expect(status).not.toHaveAttribute('tabindex');
  });
});

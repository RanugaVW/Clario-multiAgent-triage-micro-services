import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Input, PasswordInput, Textarea } from './Input';

describe('Input', () => {
  it('passes props through and accepts typing', async () => {
    render(<Input aria-label="Email" placeholder="you@company.com" />);
    const input = screen.getByLabelText('Email');
    await userEvent.type(input, 'a@b.co');
    expect(input).toHaveValue('a@b.co');
  });

  it('marks itself invalid for assistive tech and shows the danger border', () => {
    render(<Input aria-label="Email" invalid />);
    const input = screen.getByLabelText('Email');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input.className).toContain('border-danger');
  });

  it('is not marked invalid by default', () => {
    render(<Input aria-label="Email" />);
    expect(screen.getByLabelText('Email')).not.toHaveAttribute('aria-invalid');
  });
});

const tokens = (el: HTMLElement) => el.className.split(' ');

describe('invalid state keeps the danger border on hover and focus', () => {
  it.each([
    ['Input', <Input key="i" aria-label="f" invalid />],
    ['Textarea', <Textarea key="t" aria-label="f" invalid />],
  ])('%s (invalid)', (_name, ui) => {
    render(ui);
    const t = tokens(screen.getByLabelText('f'));
    expect(t).toContain('border-danger');
    expect(t).toContain('hover:border-danger');
    expect(t).toContain('focus-visible:border-danger');
    expect(t).not.toContain('hover:border-fg-subtle');
    expect(t).not.toContain('focus-visible:border-brand');
    expect(t).not.toContain('border-border-strong');
  });

  it.each([
    ['Input', <Input key="i" aria-label="f" />],
    ['Textarea', <Textarea key="t" aria-label="f" />],
  ])('%s (valid) keeps the neutral hover and focus borders', (_name, ui) => {
    render(ui);
    const t = tokens(screen.getByLabelText('f'));
    expect(t).toContain('border-border-strong');
    expect(t).toContain('hover:border-fg-subtle');
    expect(t).toContain('focus-visible:border-brand');
    expect(t).not.toContain('border-danger');
    expect(t).not.toContain('hover:border-danger');
    expect(t).not.toContain('focus-visible:border-danger');
  });
});

describe('Textarea', () => {
  it('renders a resizable textarea', () => {
    render(<Textarea aria-label="Message" />);
    const el = screen.getByLabelText('Message');
    expect(el.tagName).toBe('TEXTAREA');
    expect(el.className).toContain('resize-y');
  });
});

describe('PasswordInput', () => {
  it('starts hidden and toggles visibility with an accurate accessible state', async () => {
    render(<PasswordInput aria-label="Password" />);
    const input = screen.getByLabelText('Password');
    expect(input).toHaveAttribute('type', 'password');

    await userEvent.click(screen.getByRole('button', { name: 'Show password' }));
    expect(input).toHaveAttribute('type', 'text');
    const hide = screen.getByRole('button', { name: 'Hide password' });
    expect(hide).toHaveAttribute('aria-pressed', 'true');

    await userEvent.click(hide);
    expect(input).toHaveAttribute('type', 'password');
  });

  it('never submits the surrounding form when the toggle is used', async () => {
    const onSubmit = vi.fn((e: React.FormEvent) => e.preventDefault());
    render(
      <form onSubmit={onSubmit}>
        <PasswordInput aria-label="Password" />
      </form>
    );
    await userEvent.click(screen.getByRole('button', { name: 'Show password' }));
    expect(onSubmit).not.toHaveBeenCalled();
  });
});

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import MorphButton from './MorphButton';
import RotateButton from './RotateButton';
import ShakeButton from './ShakeButton';
import { resolveColor } from './AudioWaveform';

describe('dashboard action buttons', () => {
  it('MorphButton is a non-submitting button with theme-token colours', () => {
    render(<MorphButton textToCopy="abc" label="Copy ID" />);
    const b = screen.getByRole('button', { name: /copy id/i });
    expect(b).toHaveAttribute('type', 'button');
    expect(b.className).toMatch(/\btext-fg\b/);
    expect(b.className).not.toMatch(/white|#/);
  });

  it('ShakeButton calls onDelete and uses the danger token', async () => {
    const onDelete = vi.fn();
    render(<ShakeButton onDelete={onDelete} />);
    const b = screen.getByRole('button', { name: /delete/i });
    expect(b).toHaveAttribute('type', 'button');
    await userEvent.setup().click(b);
    expect(onDelete).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Delete')).toHaveClass('text-danger');
  });

  it('RotateButton is disabled while loading and never submits a form', () => {
    render(<RotateButton isLoading />);
    const b = screen.getByRole('button', { name: /reload/i });
    expect(b).toBeDisabled();
    expect(b).toHaveAttribute('type', 'button');
  });
});

describe('resolveColor', () => {
  it('passes plain colours through unchanged', () => {
    expect(resolveColor(document.body, '#123456')).toBe('#123456');
  });
  it('falls back to the raw value when the variable cannot be resolved', () => {
    expect(resolveColor(document.body, 'var(--c-does-not-exist)')).toBe('var(--c-does-not-exist)');
  });
});

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { PasswordInput } from '../../components/ui';

// SRS 3.9.1 (Authentication Interface): "Password visibility toggle".
describe('PasswordInput', () => {
  it('starts hidden and reveals the password when the toggle is pressed', async () => {
    const user = userEvent.setup();
    render(<PasswordInput aria-label="pw" defaultValue="hunter2" />);

    const input = screen.getByLabelText('pw');
    expect(input).toHaveAttribute('type', 'password');

    await user.click(screen.getByRole('button', { name: 'Show password' }));
    expect(input).toHaveAttribute('type', 'text');

    await user.click(screen.getByRole('button', { name: 'Hide password' }));
    expect(input).toHaveAttribute('type', 'password');
  });

  it('announces its state to assistive technology', async () => {
    const user = userEvent.setup();
    render(<PasswordInput aria-label="pw" />);

    const toggle = screen.getByRole('button', { name: 'Show password' });
    expect(toggle).toHaveAttribute('aria-pressed', 'false');

    await user.click(toggle);
    expect(screen.getByRole('button', { name: 'Hide password' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('can be operated from the keyboard alone', async () => {
    const user = userEvent.setup();
    render(<PasswordInput aria-label="pw" />);

    await user.tab(); // input
    await user.tab(); // toggle
    expect(screen.getByRole('button', { name: 'Show password' })).toHaveFocus();

    await user.keyboard('{Enter}');
    expect(screen.getByLabelText('pw')).toHaveAttribute('type', 'text');
    await user.keyboard(' ');
    expect(screen.getByLabelText('pw')).toHaveAttribute('type', 'password');
  });

  it('never submits the surrounding form when toggled', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn((e: React.FormEvent) => e.preventDefault());
    render(
      <form onSubmit={onSubmit}>
        <PasswordInput aria-label="pw" />
      </form>
    );

    await user.click(screen.getByRole('button', { name: 'Show password' }));

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('passes the value and typing through unchanged', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<PasswordInput aria-label="pw" value="" onChange={onChange} />);

    await user.type(screen.getByLabelText('pw'), 'a');

    expect(onChange).toHaveBeenCalled();
  });
});

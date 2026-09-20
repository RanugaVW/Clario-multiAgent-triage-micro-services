import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { AppShell } from './AppShell';

const setup = (over: Partial<React.ComponentProps<typeof AppShell>> = {}) => {
  const onSignOut = vi.fn();
  render(
    <AppShell
      brand={{ icon: <svg data-testid="brand-icon" />, title: 'Agent workspace', subtitle: 'Clario Platform' }}
      nav={[
        { key: 'queue', label: 'Escalation queue', icon: <svg />, href: '/agent', active: true },
        { key: 'other', label: 'Other', icon: <svg />, href: '/other' },
      ]}
      links={[{ key: 'admin', label: 'Admin panel', icon: <svg />, href: '/admin' }]}
      email="agent@example.com"
      onSignOut={onSignOut}
      {...over}
    >
      <h1>Page content</h1>
    </AppShell>
  );
  return { onSignOut };
};

describe('AppShell tabs and tones', () => {
  it('renders an onClick item as a button (in-page tab) that reports its state with aria-current', async () => {
    const onClick = vi.fn();
    render(
      <AppShell
        brand={{ icon: <svg />, title: 'T', subtitle: 'S' }}
        nav={[
          { key: 'a', label: 'Tab A', icon: <svg />, onClick, active: true },
          { key: 'b', label: 'Tab B', icon: <svg />, onClick: vi.fn() },
        ]}
        onSignOut={vi.fn()}
      >
        x
      </AppShell>
    );
    const a = screen.getByRole('button', { name: 'Tab A' });
    expect(a).toHaveAttribute('aria-current', 'page');
    expect(a).toHaveAttribute('type', 'button'); // never submits a surrounding form
    expect(screen.getByRole('button', { name: 'Tab B' })).not.toHaveAttribute('aria-current');
    await userEvent.setup().click(a);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('draws attention to a warn item only while it is not the active one', () => {
    const { rerender } = render(
      <AppShell brand={{ icon: <svg />, title: 'T', subtitle: 'S' }} nav={[{ key: 'q', label: 'Queue (3)', icon: <svg data-testid="i" />, onClick: vi.fn(), warn: true }]} onSignOut={vi.fn()}>x</AppShell>
    );
    expect(screen.getByTestId('i').parentElement).toHaveClass('text-[#FB923C]');
    rerender(
      <AppShell brand={{ icon: <svg />, title: 'T', subtitle: 'S' }} nav={[{ key: 'q', label: 'Queue (3)', icon: <svg data-testid="i" />, onClick: vi.fn(), warn: true, active: true }]} onSignOut={vi.fn()}>x</AppShell>
    );
    expect(screen.getByTestId('i').parentElement).not.toHaveClass('text-[#FB923C]');
  });

  it('accepts a rich brand title and extra classes for the content area', () => {
    render(
      <AppShell brand={{ icon: <svg />, title: <h1>Clario Triage</h1>, subtitle: 'Portal' }} nav={[]} onSignOut={vi.fn()} mainClassName="items-center">
        <p>body</p>
      </AppShell>
    );
    expect(screen.getByRole('heading', { name: 'Clario Triage' })).toBeInTheDocument();
    expect(screen.getByRole('main')).toHaveClass('items-center');
  });
});

describe('AppShell (UR-001 shared navigation layout)', () => {
  it('renders brand, primary nav, identity, footer links, sign out and the page content', () => {
    setup();
    expect(screen.getByText('Agent workspace')).toBeInTheDocument();
    expect(screen.getByText('Clario Platform')).toBeInTheDocument();
    expect(screen.getByText('agent@example.com')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Admin panel' })).toHaveAttribute('href', '/admin');
    expect(screen.getByRole('button', { name: /sign out/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Page content' })).toBeInTheDocument();
  });

  it('exposes landmarks: one navigation, one complementary sidebar, one main', () => {
    setup();
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument();
    expect(screen.getAllByRole('complementary')).toHaveLength(1);
    expect(screen.getAllByRole('main')).toHaveLength(1);
  });

  it('marks only the current destination with aria-current="page"', () => {
    setup();
    const nav = screen.getByRole('navigation', { name: 'Main' });
    expect(within(nav).getByRole('link', { name: 'Escalation queue' })).toHaveAttribute('aria-current', 'page');
    expect(within(nav).getByRole('link', { name: 'Other' })).not.toHaveAttribute('aria-current');
  });

  it('calls onSignOut when Sign out is pressed', async () => {
    const { onSignOut } = setup();
    await userEvent.setup().click(screen.getByRole('button', { name: /sign out/i }));
    expect(onSignOut).toHaveBeenCalledTimes(1);
  });

  it('omits the identity line and footer links when not supplied', () => {
    setup({ email: null, links: [] });
    expect(screen.queryByText(/Logged in as/)).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Admin panel' })).not.toBeInTheDocument();
  });

  it('is keyboard reachable: nav links, footer links and sign out are all tabbable in order', async () => {
    setup();
    const user = userEvent.setup();
    await user.tab(); expect(screen.getByRole('link', { name: 'Escalation queue' })).toHaveFocus();
    await user.tab(); expect(screen.getByRole('link', { name: 'Other' })).toHaveFocus();
    await user.tab(); expect(screen.getByRole('link', { name: 'Admin panel' })).toHaveFocus();
    await user.tab(); expect(screen.getByRole('button', { name: /sign out/i })).toHaveFocus();
  });
});

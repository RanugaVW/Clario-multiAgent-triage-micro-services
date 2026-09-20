import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { AppShell } from './AppShell';
import { renderWithTheme } from '../test/renderWithTheme';

vi.mock('next/navigation', () => ({ usePathname: () => '/dashboard' }));

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
    expect(screen.getByTestId('i').parentElement).toHaveClass('text-warning');
    rerender(
      <AppShell brand={{ icon: <svg />, title: 'T', subtitle: 'S' }} nav={[{ key: 'q', label: 'Queue (3)', icon: <svg data-testid="i" />, onClick: vi.fn(), warn: true, active: true }]} onSignOut={vi.fn()}>x</AppShell>
    );
    expect(screen.getByTestId('i').parentElement).not.toHaveClass('text-warning');
  });

  it('never puts brand-coloured text on the brand-soft wash of the active item (AA contrast)', () => {
    render(
      <AppShell brand={{ icon: <svg />, title: 'T', subtitle: 'S' }} nav={[{ key: 'q', label: 'Queue', icon: <svg data-testid="i" />, onClick: vi.fn(), active: true }]} onSignOut={vi.fn()}>x</AppShell>
    );
    const item = screen.getByRole('button', { name: 'Queue' });
    expect(item).toHaveClass('bg-brand-soft', 'text-fg');
    expect(item).not.toHaveClass('text-brand');
    // Below lg the tabs share the top-bar row instead of each claiming the full width (which hid the second tab off-screen).
    expect(item).toHaveClass('flex-1', 'lg:w-full');
    expect(item).not.toHaveClass('w-full');
    expect(screen.getByTestId('i').parentElement).toHaveClass('text-brand');
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

describe('AppShell theme toggle and token styling', () => {
  it('shows the colour theme toggle once when a ThemeProvider is present', () => {
    renderWithTheme(
      <AppShell brand={{ icon: <svg />, title: 'T', subtitle: 'S' }} nav={[]} onSignOut={vi.fn()}>x</AppShell>,
      ['/dashboard']
    );
    expect(screen.getAllByRole('group', { name: 'Color theme' })).toHaveLength(1);
  });

  it('lets the footer wrap below lg instead of clipping the toggle', () => {
    renderWithTheme(
      <AppShell brand={{ icon: <svg />, title: 'T', subtitle: 'S' }} nav={[]} email="a@b.co" links={[{ key: 'x', href: '/x', label: 'Back', icon: <svg /> }]} onSignOut={vi.fn()}>x</AppShell>,
      ['/dashboard']
    );
    const actions = screen.getByRole('button', { name: 'Sign out' }).parentElement as HTMLElement;
    const tokens = actions.className.split(' ');
    expect(tokens).toContain('flex-wrap');
    expect(tokens).not.toContain('shrink-0');
    expect(tokens).not.toContain('overflow-x-auto');
    expect(actions.parentElement?.className.split(' ')).toContain('flex-wrap');
    expect(actions.parentElement?.className.split(' ')).toContain('lg:flex-col');
  });

  it('omits the toggle (and does not crash) without a ThemeProvider', () => {
    setup();
    expect(screen.queryByRole('group', { name: 'Color theme' })).not.toBeInTheDocument();
  });

  it('styles footer link tones with theme tokens', () => {
    render(
      <AppShell
        brand={{ icon: <svg />, title: 'T', subtitle: 'S' }}
        nav={[]}
        links={[
          { key: 'a', label: 'Brand link', icon: <svg />, href: '/a', tone: 'brand' },
          { key: 'b', label: 'Success link', icon: <svg />, href: '/b', tone: 'success' },
        ]}
        onSignOut={vi.fn()}
      >x</AppShell>
    );
    expect(screen.getByRole('link', { name: 'Brand link' })).toHaveClass('text-brand');
    expect(screen.getByRole('link', { name: 'Success link' })).toHaveClass('text-success');
  });
});

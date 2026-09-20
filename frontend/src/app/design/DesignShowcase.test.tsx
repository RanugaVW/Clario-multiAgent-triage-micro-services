import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../../theme/ThemeProvider';
import { DesignShowcase } from './DesignShowcase';

vi.mock('next/navigation', () => ({ usePathname: () => '/design' }));

beforeEach(() => {
  localStorage.clear();
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: true,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia;
});

const setup = () =>
  render(
    <ThemeProvider migratedRoutes={['/design']}>
      <DesignShowcase />
    </ThemeProvider>
  );

describe('DesignShowcase', () => {
  it('shows every primitive group', () => {
    setup();
    for (const name of ['Colors', 'Type scale', 'Buttons', 'Badges', 'Form fields', 'Cards']) {
      expect(screen.getByRole('heading', { name })).toBeInTheDocument();
    }
  });

  it('includes the theme toggle', () => {
    setup();
    expect(screen.getByRole('radiogroup', { name: 'Color theme' })).toBeInTheDocument();
  });

  it('opens and closes the modal example', async () => {
    setup();
    await userEvent.click(screen.getByRole('button', { name: 'Open modal' }));
    expect(screen.getByRole('dialog', { name: 'Modal title' })).toBeInTheDocument();
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});

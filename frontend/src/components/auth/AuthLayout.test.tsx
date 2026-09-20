import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { renderWithTheme } from '../../test/renderWithTheme';
import { theme } from '../../theme/theme.config';
import { AUTH_LINK, AuthLayout } from './AuthLayout';

vi.mock('next/navigation', () => ({ usePathname: () => '/login' }));

const setup = (props: { description?: string; footer?: React.ReactNode } = {}) =>
  renderWithTheme(
    <AuthLayout title="Welcome back" {...props}>
      <p>Form goes here</p>
    </AuthLayout>,
    ['/login']
  );

describe('AuthLayout', () => {
  it('has one h1 with the title, inside the main landmark', () => {
    setup();
    const h1 = screen.getByRole('heading', { level: 1, name: 'Welcome back' });
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(screen.getByRole('main')).toContainElement(h1);
    expect(screen.getByText('Form goes here')).toBeInTheDocument();
  });

  it('shows the optional description and footer', () => {
    setup({ description: 'Sign in to your account.', footer: <a href="/register">Create one</a> });
    expect(screen.getByText('Sign in to your account.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Create one' })).toBeInTheDocument();
  });

  it('links the brand back to the home page', () => {
    setup();
    expect(screen.getByRole('link', { name: `${theme.brand.name} home` })).toHaveAttribute('href', '/');
  });

  it('offers the theme toggle at every width', () => {
    setup();
    expect(screen.getByRole('group', { name: 'Color theme' })).toBeInTheDocument();
  });

  it('exports one link style for inline links', () => {
    expect(AUTH_LINK).toContain('underline');
  });
});

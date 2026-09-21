import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { MIGRATED_ROUTES } from './migrated-routes';
import { ThemeScript } from './ThemeScript';

// Guards the wiring, not the list: the real MIGRATED_ROUTES must be what reaches the pre-paint script
// (and, via the default prop, ThemeProvider; see ThemeProvider.test.tsx). Later phases add routes freely.
describe('MIGRATED_ROUTES', () => {
  it('includes the design showcase', () => {
    expect(MIGRATED_ROUTES).toContain('/design');
  });

  it('includes the landing page', () => {
    expect(MIGRATED_ROUTES).toContain('/');
  });

  it('includes the login page', () => {
    expect(MIGRATED_ROUTES).toContain('/login');
  });

  it('includes the register page', () => {
    expect(MIGRATED_ROUTES).toContain('/register');
  });

  it('includes the password recovery pages', () => {
    expect(MIGRATED_ROUTES).toContain('/forgot-password');
    expect(MIGRATED_ROUTES).toContain('/reset-password');
  });

  it('includes /dashboard (the customer dashboard is on the theme tokens)', () => {
    expect(MIGRATED_ROUTES).toContain('/dashboard');
  });

  it('includes /agent (the agent console is on the theme tokens)', () => {
    expect(MIGRATED_ROUTES).toContain('/agent');
  });

  it('is what the rendered ThemeScript embeds', () => {
    const html = renderToStaticMarkup(<ThemeScript />);
    expect(html).toContain(JSON.stringify(MIGRATED_ROUTES));
  });
});

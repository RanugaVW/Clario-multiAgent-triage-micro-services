import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, it, expect } from 'vitest';

// UR-001 guardrail. Behaviour is covered by the rendered-page tests; this pins the *structure* so a new page
// cannot quietly go back to hand-rolling its own chrome.
const src = (rel: string) => readFileSync(join(__dirname, '..', rel), 'utf8');

describe('UR-001 - shared design system usage', () => {
  it.each(['login', 'register', 'forgot-password', 'reset-password'])(
    'the %s page is built from AuthLayout and the shared primitives',
    (page) => {
      const code = src(`${page}/page.tsx`);
      expect(code).toMatch(/import \{[^}]*AuthLayout[^}]*\} from '..\/..\/components\/auth\/AuthLayout'/);
      expect(code).toMatch(/<AuthLayout/);
      expect(code).toMatch(/import \{[^}]*Button[^}]*\} from '..\/..\/components\/ui\/Button'/);
      // theme tokens only: no hard-coded colors, no legacy glass classes, no hand-rolled primary button
      expect(code).not.toMatch(/#[0-9A-Fa-f]{3,8}\b/);
      expect(code).not.toMatch(/rgba?\(/);
      expect(code).not.toMatch(/glass-|bg-white text-black/);
    }
  );

  it('every text/email input on the auth pages uses Input or PasswordInput, not a raw <input>', () => {
    for (const page of ['login', 'register', 'forgot-password', 'reset-password']) {
      expect(src(`${page}/page.tsx`), page).not.toMatch(/<input\b/);
    }
  });

  it.each([
    ['agent/page.tsx', 'AgentShell'],
    ['agent/[id]/page.tsx', 'AgentShell'],
    ['admin/reports/page.tsx', 'AdminShell'],
    ['admin/users/page.tsx', 'AdminShell'],
    ['admin/page.tsx', 'AdminShell'],
    ['dashboard/page.tsx', 'AppShell'],
  ])('%s renders inside the shared navigation shell (%s)', (file, shell) => {
    expect(src(file)).toContain(`<${shell}`);
    expect(src(file)).not.toMatch(/<main\b/); // the shell owns the <main> landmark
    expect(src(file)).not.toMatch(/<aside\b/); // ...and the sidebar: no page builds its own
  });

  it('every workspace page now shares one sidebar implementation', () => {
    // The only <aside> in the workspace pages and components is the shell's.
    const withAside = ['agent/page.tsx', 'agent/[id]/page.tsx', 'admin/page.tsx', 'admin/reports/page.tsx', 'admin/users/page.tsx', 'dashboard/page.tsx']
      .filter((f) => /<aside\b/.test(src(f)));
    expect(withAside).toEqual([]);
    expect(readFileSync(join(__dirname, '..', '..', 'components', 'AppShell.tsx'), 'utf8')).toMatch(/<aside\b/);
  });

  it.each(['agent/AgentShell.tsx', 'admin/AdminShell.tsx'])('%s is itself built on AppShell', (file) => {
    expect(src(file)).toContain('<AppShell');
  });
});

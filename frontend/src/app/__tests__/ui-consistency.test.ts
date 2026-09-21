import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, it, expect } from 'vitest';

// UR-001 guardrail. Behaviour is covered by the rendered-page tests; this pins the *structure* so a new page
// cannot quietly go back to hand-rolling its own chrome.
const src = (rel: string) => readFileSync(join(__dirname, '..', rel), 'utf8');

describe('UR-001 - shared design system usage', () => {
  it.each(['login', 'register', 'forgot-password', 'reset-password'])(
    'the %s page is built from AuthLayout and the shared primitives',
    (page) => {
      const code = src(`${page}/page.tsx`);
      expect(code).toMatch(/import \{[^}]*AuthLayout[^}]*\} from '\.\.\/\.\.\/components\/auth\/AuthLayout'/);
      expect(code).toMatch(/<AuthLayout/);
      expect(code).toMatch(/import \{[^}]*Button[^}]*\} from '\.\.\/\.\.\/components\/ui\/Button'/);
      // theme tokens only: no hard-coded colors, no legacy glass classes, no hand-rolled primary button
      expect(code).not.toMatch(/(?<![\w&])#(?:[0-9A-Fa-f]{8}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3,4})(?![\w-])/);
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

  it.each(['agent/page.tsx', 'agent/[id]/page.tsx'])('%s imports primitives by file path, never the legacy ui.tsx barrel', (file) => {
    expect(src(file)).not.toMatch(/from '(\.\.\/)+components\/ui'/);
  });

  it.each(['admin/reports/page.tsx', 'admin/users/page.tsx', 'admin/page.tsx'])('%s imports primitives by file path, never the legacy ui.tsx barrel', (file) => {
    expect(src(file)).not.toMatch(/from '(\.\.\/)+components\/ui'/);
  });

  it('the admin console carries no legacy colour helpers or inline status hex', () => {
    expect(src('admin/page.tsx')).not.toMatch(/statusColor|priorityColor|sentimentColor/);
  });

  it('the dashboard imports primitives by file path, never the legacy ui.tsx barrel', () => {
    expect(src('dashboard/page.tsx')).not.toMatch(/from '\.\.\/\.\.\/components\/ui'/);
  });
});

// Global token guard: every app and component source file must style through theme tokens only.
const SRC_ROOT = join(__dirname, '..', '..');
const FORBIDDEN: Array<[string, RegExp]> = [
  ['hex colour', /(?<![\w&])#(?:[0-9A-Fa-f]{8}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3,4})(?![\w-])/],
  ['rgb()/rgba()', /rgba?\(/],
  ['white/NN', /white\//],
  ['glass-*', /glass-/],
  ['text-[#...]', /text-\[#/],
  ['off-scale text size', /text-(xs|sm|base|lg|xl|2xl|3xl)\b/],
  [
    'raw palette class',
    /\b(bg|text|border|from|to|via|ring|fill|stroke)-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d/,
  ],
  ['animate-fade-in', /animate-fade-in/],
  ['bare components/ui barrel import (relative)', /from ['"](\.\.\/)+components\/ui['"]/],
  ['bare components/ui barrel import (alias)', /from ['"]@\/components\/ui['"]/],
];
// Files exempt from the guard, each with a justification. Keep empty unless a literal is unavoidable.
const ALLOWLIST: string[] = [];

function collect(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    const rel = relative(SRC_ROOT, full).split('\\').join('/');
    if (statSync(full).isDirectory()) {
      if (rel === 'app/__tests__' || rel.startsWith('theme')) continue;
      collect(full, out);
    } else if (/\.tsx?$/.test(name) && !/\.test\.tsx?$/.test(name)) {
      out.push(rel);
    }
  }
  return out;
}

describe('global token guard', () => {
  const files = [...collect(join(SRC_ROOT, 'app')), ...collect(join(SRC_ROOT, 'components'))].filter((f) => !ALLOWLIST.includes(f));

  it('scans a meaningful set of files', () => {
    expect(files.length).toBeGreaterThan(30);
  });

  it('no app or component file uses a hard-coded colour, legacy class, off-scale size or bare ui barrel', () => {
    const hits: string[] = [];
    for (const f of files) {
      const code = readFileSync(join(SRC_ROOT, f), 'utf8');
      for (const [label, re] of FORBIDDEN) if (re.test(code)) hits.push(`${f}: ${label}`);
    }
    expect(hits).toEqual([]);
  });
});

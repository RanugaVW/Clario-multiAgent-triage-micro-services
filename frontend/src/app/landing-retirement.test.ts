import { existsSync, readFileSync } from 'fs';
import path from 'path';
import { describe, expect, it } from 'vitest';
import nextConfig from '../../next.config';

const root = path.join(__dirname, '..', '..');

// Guards against the old static landing page coming back or being referenced again.
describe('old landing page is retired', () => {
  it('no longer rewrites "/" to a static file', () => {
    expect(nextConfig.rewrites).toBeUndefined();
  });

  it('the static file is gone', () => {
    expect(existsSync(path.join(root, 'public', 'landing.html'))).toBe(false);
  });

  it('the login page no longer embeds it', () => {
    const login = readFileSync(path.join(root, 'src', 'app', 'login', 'page.tsx'), 'utf8');
    expect(login).not.toContain('landing.html');
    expect(login).not.toContain('<iframe');
  });
});

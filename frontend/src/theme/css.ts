import type { ColorSet, Shadows, Theme } from './types';

type Entry = [name: string, value: string | number];

const kebab = (s: string) => s.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`);
const join = (entries: Entry[]) => entries.map(([k, v]) => `${k}:${v}`).join(';');

function sharedEntries(t: Theme): Entry[] {
  const out: Entry[] = [];
  for (const [role, s] of Object.entries(t.type)) {
    out.push([`--t-${role}-size`, s.size], [`--t-${role}-lh`, s.lineHeight], [`--t-${role}-weight`, s.weight], [`--t-${role}-tracking`, s.tracking]);
  }
  for (const [k, v] of Object.entries(t.radius)) out.push([`--r-${k}`, v]);
  for (const [k, v] of Object.entries(t.space)) out.push([`--sp-${k}`, v]);
  for (const [k, v] of Object.entries(t.layout)) out.push([`--l-${kebab(k)}`, v]);
  for (const [k, v] of Object.entries(t.motion)) out.push([`--m-${kebab(k)}`, v]);
  out.push(['--f-sans', `var(--font-face-sans),${t.fontStacks.sans}`]);
  out.push(['--f-mono', `var(--font-face-mono),${t.fontStacks.mono}`]);
  return out;
}

function modeEntries(colors: ColorSet, shadows: Shadows, scheme: 'light' | 'dark'): Entry[] {
  const out: Entry[] = Object.entries(colors).map(([k, v]) => [`--c-${k}`, v]);
  out.push(['--sh-card', shadows.card], ['--sh-raised', shadows.raised], ['color-scheme', scheme]);
  return out;
}

/**
 * Three rules, one per line: shared variables, dark (also the default when no data-theme is set yet) and
 * light. The values come from the developer-owned theme file, so they are injected as-is.
 */
export function themeToCss(t: Theme): string {
  return [
    `:root{${join(sharedEntries(t))}}`,
    `:root,:root[data-theme="dark"]{${join(modeEntries(t.colors.dark, t.shadows.dark, 'dark'))}}`,
    `:root[data-theme="light"]{${join(modeEntries(t.colors.light, t.shadows.light, 'light'))}}`,
  ].join('\n');
}

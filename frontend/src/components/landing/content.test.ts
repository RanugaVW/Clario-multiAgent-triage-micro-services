import { describe, expect, it } from 'vitest';
import { agents, cta, demo, footer, hero, nav, privacy, review, steps } from './content';

const SECTION_IDS = [agents.id, steps.id, review.id, privacy.id];

function collectStrings(value: unknown): string[] {
  if (typeof value === 'string') return [value];
  if (Array.isArray(value)) return value.flatMap(collectStrings);
  if (value && typeof value === 'object') return Object.values(value).flatMap(collectStrings);
  return [];
}

describe('landing content', () => {
  it('every in-page nav link points at a section id that exists', () => {
    for (const link of nav.links) {
      expect(link.href.startsWith('#')).toBe(true);
      expect(SECTION_IDS).toContain(link.href.slice(1));
    }
  });

  it('section ids are unique', () => {
    expect(new Set(SECTION_IDS).size).toBe(SECTION_IDS.length);
  });

  it('account links go to real routes', () => {
    for (const href of [nav.signIn.href, nav.getStarted.href, hero.primary.href, hero.secondary.href, cta.primary.href, cta.secondary.href]) {
      expect(['/login', '/register']).toContain(href);
    }
    expect(footer.links.map((l) => l.href).sort()).toEqual(['/login', '/register']);
  });

  it('describes the pipeline as five steps and three specialist agents', () => {
    expect(steps.items).toHaveLength(5);
    expect(agents.items.map((a) => a.key)).toEqual(['technical', 'billing', 'hr']);
    expect(privacy.items).toHaveLength(3);
  });

  it('says HR replies are always reviewed by a person, never automatic', () => {
    const hr = agents.items.find((a) => a.key === 'hr');
    expect(hr?.badge.text).toBe('Always reviewed by a person');
    expect(hr?.body).toMatch(/person/);
  });

  it('has no empty strings, no arrows and no invented statistics', () => {
    const all = [...collectStrings(hero), ...collectStrings(demo), ...collectStrings(agents), ...collectStrings(steps), ...collectStrings(review), ...collectStrings(privacy), ...collectStrings(cta)];
    for (const text of all) {
      expect(text.trim().length, 'empty string in content').toBeGreaterThan(0);
      expect(text).not.toMatch(/→/);
      expect(text).not.toMatch(/\b\d+\s?[kK]\+|\b\d+%/);
    }
  });
});

import { describe, expect, it } from 'vitest';
import { theme } from '../theme/theme.config';
import { cx } from './cx';

describe('cx', () => {
  it('joins truthy parts with single spaces', () => {
    expect(cx('a', 'b')).toBe('a b');
  });
  it('drops false, null, undefined and empty strings', () => {
    expect(cx('a', false, null, undefined, '', 'b')).toBe('a b');
  });

  describe('conflict resolution', () => {
    it('lets the later utility win', () => {
      expect(cx('inline-flex', 'hidden')).toBe('hidden');
      expect(cx('p-card', 'p-0')).toBe('p-0');
      expect(cx('px-4', 'px-2')).toBe('px-2');
    });
    it('keeps variants independent', () => {
      expect(cx('hidden', 'sm:block')).toBe('hidden sm:block');
    });
  });

  describe('project font sizes', () => {
    it.each(Object.keys(theme.type))('treats text-%s as a size, not a color', (role) => {
      expect(cx('text-' + role, 'text-fg')).toBe('text-' + role + ' text-fg');
      expect(cx('text-fg', 'text-' + role)).toBe('text-fg text-' + role);
    });
    it('makes two sizes conflict', () => {
      expect(cx('text-h2', 'text-h3')).toBe('text-h3');
    });
  });

  describe('project spacing', () => {
    it('recognises the theme space keys', () => {
      expect(cx('p-card', 'p-4')).toBe('p-4');
      expect(cx('py-section', 'py-4')).toBe('py-4');
      expect(cx('pb-section', 'pb-4')).toBe('pb-4');
      expect(cx('gap-stack', 'gap-2')).toBe('gap-2');
      expect(cx('px-page', 'px-2')).toBe('px-2');
    });
  });

  describe('project shadows, containers and radius', () => {
    it('recognises them', () => {
      expect(cx('shadow-card', 'shadow-raised')).toBe('shadow-raised');
      expect(cx('max-w-marketing', 'max-w-app')).toBe('max-w-app');
      expect(cx('rounded-lg', 'rounded-pill')).toBe('rounded-pill');
    });
  });

  describe('theme colors', () => {
    it('conflict with each other but not with sizes or border width', () => {
      expect(cx('text-fg-muted', 'text-brand')).toBe('text-brand');
      expect(cx('bg-canvas', 'bg-surface')).toBe('bg-surface');
      expect(cx('border', 'border-border')).toBe('border border-border');
    });
  });

  it('leaves project-specific non-Tailwind classes untouched', () => {
    expect(cx('rise-in', 'demo-step', 'glow-blob')).toBe('rise-in demo-step glow-blob');
  });

  it('keeps opacity modifiers and arbitrary values', () => {
    expect(cx('bg-canvas/80', 'h-[var(--l-header-height)]')).toBe('bg-canvas/80 h-[var(--l-header-height)]');
  });
});

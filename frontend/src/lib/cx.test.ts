import { describe, expect, it } from 'vitest';
import { cx } from './cx';

describe('cx', () => {
  it('joins truthy parts with single spaces', () => {
    expect(cx('a', 'b')).toBe('a b');
  });
  it('drops false, null, undefined and empty strings', () => {
    expect(cx('a', false, null, undefined, '', 'b')).toBe('a b');
  });
});

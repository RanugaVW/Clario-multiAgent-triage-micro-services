import { describe, expect, it } from 'vitest';
import { categoryDomain, priorityClass, priorityColor, sentimentClass, sentimentColor, splitCategories } from './classification';

describe('splitCategories', () => {
  it('splits a comma-joined multi-label category and trims each label', () => {
    expect(splitCategories('Billing & Invoicing,  Refunds')).toEqual(['Billing & Invoicing', 'Refunds']);
  });

  it('keeps a single label whole, including labels that contain a slash', () => {
    expect(splitCategories('UI/UX')).toEqual(['UI/UX']);
  });

  it('returns an empty list for null, undefined or blank input', () => {
    expect(splitCategories(null)).toEqual([]);
    expect(splitCategories(undefined)).toEqual([]);
    expect(splitCategories(' , ')).toEqual([]);
  });
});

describe('categoryDomain', () => {
  it.each([
    ['Billing & Invoicing', 'billing'],
    ['Refunds, Subscription Management', 'billing'],
    ['Authentication', 'technical'],
    ['Performance, Technical Support', 'technical'],
    // Spans both domains, or names neither: a person has to look at it.
    ['Refunds, Technical Support', 'other'],
    ['Feature Request', 'other'],
    ['General', 'other'],
    [null, 'other'],
  ])('%s -> %s', (category, expected) => {
    expect(categoryDomain(category as string | null)).toBe(expected);
  });

  it('still groups rows written by the previous classifier', () => {
    expect(categoryDomain('Billing')).toBe('billing');
    expect(categoryDomain('account')).toBe('billing');
    expect(categoryDomain('Technical')).toBe('technical');
  });
});

describe('priorityColor', () => {
  it('highlights critical and high, leaves the rest at the default', () => {
    expect(priorityColor('Critical')).toBeDefined();
    expect(priorityColor('High')).toBeDefined();
    expect(priorityColor('critical')).not.toBe(priorityColor('low'));
    expect(priorityColor('Medium')).toBeUndefined();
    expect(priorityColor(null)).toBeUndefined();
  });
});

describe('sentimentColor', () => {
  it('highlights frustrated and negative, leaves neutral at the default', () => {
    expect(sentimentColor('Frustrated')).toBeDefined();
    expect(sentimentColor('negative')).toBeDefined();
    expect(sentimentColor('Neutral')).toBeUndefined();
    expect(sentimentColor(undefined)).toBeUndefined();
  });
});

describe('priorityClass', () => {
  it.each([
    ['critical', 'text-danger'],
    ['High', 'text-warning'],
    ['low', ''],
    [null, ''],
    [undefined, ''],
  ])('maps %s to %s', (p, cls) => {
    expect(priorityClass(p)).toBe(cls);
  });
});

describe('sentimentClass', () => {
  it.each([
    ['Frustrated', 'text-danger'],
    ['Negative', 'text-danger'],
    ['Neutral', ''],
    [null, ''],
    [undefined, ''],
  ])('maps %s to %s', (s, cls) => {
    expect(sentimentClass(s)).toBe(cls);
  });
});

import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { steps } from './content';
import { HowItWorks } from './HowItWorks';

describe('HowItWorks', () => {
  it('is a region named by its heading and can be linked to as #how', () => {
    const { container } = render(<HowItWorks />);
    expect(screen.getByRole('region', { name: steps.title })).toBeInTheDocument();
    expect(container.querySelector('#how')).not.toBeNull();
  });

  it('is a real ordered list of five steps, each with a title and a description', () => {
    render(<HowItWorks />);
    const list = screen.getByRole('list');
    expect(list.tagName).toBe('OL');
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(5);
    steps.items.forEach((step, i) => {
      expect(within(items[i]).getByRole('heading', { level: 3, name: step.title })).toBeInTheDocument();
      expect(within(items[i]).getByText(step.body)).toBeInTheDocument();
    });
  });

  it('shows visible step numbers but hides them from assistive tech (the list already says the order)', () => {
    const { container } = render(<HowItWorks />);
    const numbers = Array.from(container.querySelectorAll('li [aria-hidden="true"]')).map((el) => el.textContent);
    expect(numbers).toEqual(['1', '2', '3', '4', '5']);
  });
});

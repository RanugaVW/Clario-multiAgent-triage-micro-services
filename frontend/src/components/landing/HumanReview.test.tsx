import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { review } from './content';
import { HumanReview } from './HumanReview';

describe('HumanReview', () => {
  it('is a region named by its heading and can be linked to as #review', () => {
    const { container } = render(<HumanReview />);
    expect(screen.getByRole('region', { name: review.title })).toBeInTheDocument();
    expect(container.querySelector('#review')).not.toBeNull();
  });

  it('lists what the reviewer sees and can do', () => {
    render(<HumanReview />);
    for (const point of review.points) expect(screen.getByText(point)).toBeInTheDocument();
  });

  it('shows the example queue as a decorative, non-interactive picture', () => {
    const { container } = render(<HumanReview />);
    const mock = container.querySelector('[aria-hidden="true"]:not(svg)') as HTMLElement;
    expect(mock).not.toBeNull();
    expect(mock).toHaveTextContent(review.mock.label);
    expect(mock.querySelectorAll('a, button, input, [tabindex]')).toHaveLength(0);
  });
});

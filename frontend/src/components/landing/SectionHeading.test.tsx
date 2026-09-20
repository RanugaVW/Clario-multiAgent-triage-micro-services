import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { SectionHeading } from './SectionHeading';

describe('SectionHeading', () => {
  it('renders an h2 with an id derived from the section id, and the intro', () => {
    render(<SectionHeading id="agents" title="Three specialists" intro="Each ticket goes to the right agent." />);
    const heading = screen.getByRole('heading', { level: 2, name: 'Three specialists' });
    expect(heading).toHaveAttribute('id', 'agents-title');
    expect(screen.getByText('Each ticket goes to the right agent.')).toBeInTheDocument();
  });
});

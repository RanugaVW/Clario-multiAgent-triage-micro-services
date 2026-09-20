import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { demo } from './content';
import { TriageDemo } from './TriageDemo';

describe('TriageDemo', () => {
  it('is a labelled group that says it is an example', () => {
    render(<TriageDemo />);
    expect(screen.getByRole('group', { name: demo.ariaLabel })).toBeInTheDocument();
    expect(screen.getByText(demo.label)).toBeInTheDocument();
  });

  it('shows the whole story: ticket, classification, routing, draft and check', () => {
    render(<TriageDemo />);
    expect(screen.getByText(demo.ticket)).toBeInTheDocument();
    for (const label of demo.labels) expect(screen.getByText(label.text)).toBeInTheDocument();
    expect(screen.getByText(demo.routed)).toBeInTheDocument();
    expect(screen.getByText(demo.draft)).toBeInTheDocument();
    expect(screen.getByText(demo.checked)).toBeInTheDocument();
  });

  it('plays its steps in order by giving each one a consecutive demo index', () => {
    const { container } = render(<TriageDemo />);
    const indexes = Array.from(container.querySelectorAll<HTMLElement>('.demo-step')).map((el) => el.style.getPropertyValue('--demo-index'));
    expect(indexes).toEqual(['0', '1', '2', '3', '4']);
  });

  it('contains nothing interactive, so it never needs to be focusable', () => {
    const { container } = render(<TriageDemo />);
    expect(container.querySelectorAll('a, button, input, [tabindex]')).toHaveLength(0);
  });
});

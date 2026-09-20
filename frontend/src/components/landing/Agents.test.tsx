import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Agents } from './Agents';
import { agents } from './content';

describe('Agents', () => {
  it('is a region named by its heading and can be linked to as #agents', () => {
    const { container } = render(<Agents />);
    expect(screen.getByRole('region', { name: agents.title })).toBeInTheDocument();
    expect(container.querySelector('#agents')).not.toBeNull();
  });

  it('presents the three specialists and the input methods as h3 headings', () => {
    render(<Agents />);
    for (const item of agents.items) expect(screen.getByRole('heading', { level: 3, name: item.title })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: agents.inputs.title })).toBeInTheDocument();
  });

  it('marks the HR agent as always reviewed by a person, and only the HR agent', () => {
    render(<Agents />);
    expect(screen.getAllByText('Always reviewed by a person')).toHaveLength(1);
    expect(screen.getAllByText('Can resolve automatically')).toHaveLength(2);
  });
});

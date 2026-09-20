import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { privacy } from './content';
import { Privacy } from './Privacy';

describe('Privacy', () => {
  it('is a region named by its heading and can be linked to as #privacy', () => {
    const { container } = render(<Privacy />);
    expect(screen.getByRole('region', { name: privacy.title })).toBeInTheDocument();
    expect(container.querySelector('#privacy')).not.toBeNull();
  });

  it('states masked first, restored last and access by role', () => {
    render(<Privacy />);
    for (const item of privacy.items) {
      expect(screen.getByRole('heading', { level: 3, name: item.title })).toBeInTheDocument();
      expect(screen.getByText(item.body)).toBeInTheDocument();
    }
  });
});

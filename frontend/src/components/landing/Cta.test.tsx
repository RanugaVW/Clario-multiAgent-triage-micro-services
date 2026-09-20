import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Cta } from './Cta';
import { cta } from './content';

describe('Cta', () => {
  it('is a region with a heading and a short invitation', () => {
    render(<Cta />);
    expect(screen.getByRole('region', { name: cta.title })).toBeInTheDocument();
    expect(screen.getByText(cta.body)).toBeInTheDocument();
  });

  it('links to create an account and to sign in', () => {
    render(<Cta />);
    expect(screen.getByRole('link', { name: cta.primary.label })).toHaveAttribute('href', cta.primary.href);
    expect(screen.getByRole('link', { name: cta.secondary.label })).toHaveAttribute('href', cta.secondary.href);
  });
});

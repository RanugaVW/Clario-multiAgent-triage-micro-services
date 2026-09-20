import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Container, Section } from './Container';

describe('Container', () => {
  it('uses the marketing width by default and centres itself', () => {
    render(<Container data-testid="c" />);
    const cls = screen.getByTestId('c').className;
    expect(cls).toContain('max-w-marketing');
    expect(cls).toContain('mx-auto');
  });

  it('can use the app width', () => {
    render(<Container size="app" data-testid="c" />);
    expect(screen.getByTestId('c').className).toContain('max-w-app');
  });
});

describe('Section', () => {
  it('is a <section> with the theme section gap and a container inside', () => {
    render(
      <Section id="how" data-testid="s">
        <p>Inside</p>
      </Section>
    );
    const section = screen.getByTestId('s');
    expect(section.tagName).toBe('SECTION');
    expect(section.className).toContain('py-section');
    expect(section.id).toBe('how');
    expect(screen.getByText('Inside').parentElement?.className).toContain('max-w-marketing');
  });

  it('can skip the inner container for full-bleed content', () => {
    render(
      <Section contained={false} data-testid="s">
        <p>Wide</p>
      </Section>
    );
    expect(screen.getByText('Wide').parentElement).toBe(screen.getByTestId('s'));
  });
});

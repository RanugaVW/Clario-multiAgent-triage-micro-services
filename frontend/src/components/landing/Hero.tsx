import type { CSSProperties } from 'react';
import { ButtonLink } from '../ui/Button';
import { Container } from '../ui/Container';
import { GlowBackdrop } from '../ui/GlowBackdrop';
import { hero } from './content';
import { TriageDemo } from './TriageDemo';

// --rise-index staggers each block by the theme's hero stagger (see .rise-in in globals.css).
const at = (index: number) => ({ '--rise-index': index }) as CSSProperties;

export function Hero() {
  return (
    <section className="relative overflow-hidden pb-section pt-16 sm:pt-24">
      <GlowBackdrop />
      <Container className="relative flex flex-col items-center text-center">
        <h1 className="rise-in max-w-4xl text-display text-fg" style={at(0)}>
          {hero.headline}
        </h1>
        <p className="rise-in mt-6 max-w-2xl text-body-lg text-fg-muted" style={at(1)}>
          {hero.lead}
        </p>
        <div className="rise-in mt-10 flex flex-wrap items-center justify-center gap-3" style={at(2)}>
          <ButtonLink href={hero.primary.href} size="lg">
            {hero.primary.label}
          </ButtonLink>
          <ButtonLink href={hero.secondary.href} variant="secondary" size="lg">
            {hero.secondary.label}
          </ButtonLink>
        </div>
        <div className="rise-in mt-16 w-full max-w-3xl" style={at(3)}>
          <TriageDemo />
        </div>
      </Container>
    </section>
  );
}

import type { CSSProperties } from 'react';
import { ButtonLink } from '../ui/Button';
import { Container } from '../ui/Container';
import { GlowBackdrop } from '../ui/GlowBackdrop';
import { EventHorizon, EventHorizonReflection } from './EventHorizon';
import { hero } from './content';
import { TriageDemo } from './TriageDemo';

// --rise-index staggers each block by the theme's hero stagger (see .rise-in in globals.css).
// The headline, lead and buttons are z-10 so the horizon glow (a later, positioned sibling) never paints over them.
const at = (index: number) => ({ '--rise-index': index }) as CSSProperties;

export function Hero() {
  return (
    <section className="relative overflow-hidden pb-section pt-16 sm:pt-24">
      <GlowBackdrop />
      <Container className="relative flex flex-col items-center text-center">
        <h1 className="rise-in relative z-10 max-w-4xl text-display text-fg" style={at(0)}>
          {hero.headline}
        </h1>
        <p className="rise-in relative z-10 mt-6 max-w-2xl text-body-lg text-fg-muted" style={at(1)}>
          {hero.lead}
        </p>
        <div className="rise-in relative z-10 mt-10 flex flex-wrap items-center justify-center gap-3" style={at(2)}>
          <ButtonLink href={hero.primary.href} size="lg">
            {hero.primary.label}
          </ButtonLink>
          <ButtonLink href={hero.secondary.href} variant="secondary" size="lg">
            {hero.secondary.label}
          </ButtonLink>
        </div>
        <div className="rise-in relative mt-28 w-full max-w-3xl sm:mt-44" style={at(3)}>
          <EventHorizon />
          <TriageDemo />
          <EventHorizonReflection />
        </div>
      </Container>
    </section>
  );
}

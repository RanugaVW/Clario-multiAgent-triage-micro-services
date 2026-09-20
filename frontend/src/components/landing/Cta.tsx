import { ButtonLink } from '../ui/Button';
import { Section } from '../ui/Container';
import { GlowBackdrop } from '../ui/GlowBackdrop';
import { cta } from './content';
import { Reveal } from './Reveal';

export function Cta() {
  return (
    <Section aria-labelledby="cta-title">
      <Reveal className="relative overflow-hidden rounded-xl border border-border bg-surface px-6 py-16 text-center sm:px-12">
        <GlowBackdrop />
        <div className="relative mx-auto flex max-w-2xl flex-col items-center gap-6">
          <h2 id="cta-title" className="text-h1 text-fg">
            {cta.title}
          </h2>
          <p className="text-body-lg text-fg-muted">{cta.body}</p>
          <div className="flex flex-wrap justify-center gap-3">
            <ButtonLink href={cta.primary.href} size="lg">
              {cta.primary.label}
            </ButtonLink>
            <ButtonLink href={cta.secondary.href} variant="secondary" size="lg">
              {cta.secondary.label}
            </ButtonLink>
          </div>
        </div>
      </Reveal>
    </Section>
  );
}

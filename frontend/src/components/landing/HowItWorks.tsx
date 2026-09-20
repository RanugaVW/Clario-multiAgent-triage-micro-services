import { Section } from '../ui/Container';
import { steps } from './content';
import { Reveal } from './Reveal';
import { SectionHeading } from './SectionHeading';

// The one place on the page with numbers, because the content really is a sequence.
export function HowItWorks() {
  return (
    <Section id={steps.id} aria-labelledby={`${steps.id}-title`} className="scroll-mt-20">
      <SectionHeading id={steps.id} title={steps.title} intro={steps.intro} />

      <ol role="list" className="mt-12 grid gap-8 md:grid-cols-3 lg:grid-cols-5">
        {steps.items.map((step, i) => (
          <li key={step.title}>
            <Reveal delay={i * 0.06} className="flex flex-col gap-3">
              <span
                aria-hidden="true"
                className="grid h-8 w-8 place-items-center rounded-pill border border-border-strong text-mono text-fg-muted"
              >
                {i + 1}
              </span>
              <h3 className="text-h3 text-fg">{step.title}</h3>
              <p className="text-app text-fg-muted">{step.body}</p>
            </Reveal>
          </li>
        ))}
      </ol>
    </Section>
  );
}

import { EyeOff, KeyRound, UserCheck } from 'lucide-react';
import { Section } from '../ui/Container';
import { privacy } from './content';
import { Reveal } from './Reveal';
import { SectionHeading } from './SectionHeading';

const ICONS = { mask: EyeOff, restore: KeyRound, roles: UserCheck } as const;

export function Privacy() {
  return (
    <Section id={privacy.id} aria-labelledby={`${privacy.id}-title`} className="scroll-mt-20">
      <SectionHeading id={privacy.id} title={privacy.title} intro={privacy.intro} />

      <div className="mt-12 grid gap-10 md:grid-cols-3">
        {privacy.items.map((item, i) => {
          const Icon = ICONS[item.key];
          return (
            <Reveal key={item.key} delay={i * 0.06} className="border-t border-border pt-6">
              <Icon className="h-5 w-5 text-brand" aria-hidden="true" />
              <h3 className="mt-4 text-h3 text-fg">{item.title}</h3>
              <p className="mt-2 text-app text-fg-muted">{item.body}</p>
            </Reveal>
          );
        })}
      </div>
    </Section>
  );
}

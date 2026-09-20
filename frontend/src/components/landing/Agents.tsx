import { CreditCard, ImagePlus, Users, Wrench } from 'lucide-react';
import type { ReactNode } from 'react';
import { Badge } from '../ui/Badge';
import { Card } from '../ui/Card';
import { Section } from '../ui/Container';
import { agents } from './content';
import { Reveal } from './Reveal';
import { SectionHeading } from './SectionHeading';

const ICONS = { technical: Wrench, billing: CreditCard, hr: Users } as const;

// Icons sit on brand-soft; that pairing is only contrast-tested for non-text, so never put text on it.
function IconTile({ children }: { children: ReactNode }) {
  return <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-brand-soft text-brand">{children}</span>;
}

export function Agents() {
  return (
    <Section id={agents.id} aria-labelledby={`${agents.id}-title`} className="scroll-mt-20">
      <SectionHeading id={agents.id} title={agents.title} intro={agents.intro} />

      <div className="mt-12 grid gap-4 md:grid-cols-3">
        {agents.items.map((item, i) => {
          const Icon = ICONS[item.key];
          return (
            <Reveal key={item.key} delay={i * 0.06}>
              <Card className="flex h-full flex-col gap-4">
                <div className="flex items-start justify-between gap-3">
                  <IconTile>
                    <Icon className="h-5 w-5" aria-hidden="true" />
                  </IconTile>
                  <Badge tone={item.badge.tone}>{item.badge.text}</Badge>
                </div>
                <h3 className="text-h3 text-fg">{item.title}</h3>
                <p className="text-app text-fg-muted">{item.body}</p>
              </Card>
            </Reveal>
          );
        })}

        <Reveal delay={0.18} className="md:col-span-3">
          <Card className="flex h-full flex-col gap-4 sm:flex-row sm:items-center">
            <IconTile>
              <ImagePlus className="h-5 w-5" aria-hidden="true" />
            </IconTile>
            <div>
              <h3 className="text-h3 text-fg">{agents.inputs.title}</h3>
              <p className="mt-1 text-app text-fg-muted">{agents.inputs.body}</p>
            </div>
          </Card>
        </Reveal>
      </div>
    </Section>
  );
}

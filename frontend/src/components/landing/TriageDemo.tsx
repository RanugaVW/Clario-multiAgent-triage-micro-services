import { Bot, CircleCheck } from 'lucide-react';
import type { CSSProperties, ReactNode } from 'react';
import { Badge } from '../ui/Badge';
import { Card } from '../ui/Card';
import { demo } from './content';

// Each step fades in after the previous one (see .demo-step in globals.css). Plays once, then stays.
function Step({ index, children }: { index: number; children: ReactNode }) {
  return (
    <div className="demo-step" style={{ '--demo-index': index } as CSSProperties}>
      {children}
    </div>
  );
}

export function TriageDemo() {
  return (
    <Card raised role="group" aria-label={demo.ariaLabel} className="text-left">
      <div className="flex items-center justify-between gap-3 border-b border-border pb-4">
        <span className="text-small text-fg-muted">{demo.label}</span>
        <Badge tone="accent">{demo.status}</Badge>
      </div>

      <div className="mt-5 flex flex-col gap-5">
        <Step index={0}>
          <p className="text-small text-fg-muted">{demo.customer}</p>
          <p className="mt-1 text-body text-fg">{demo.ticket}</p>
        </Step>

        <Step index={1}>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-small text-fg-muted">{demo.classified}</span>
            {demo.labels.map((label) => (
              <Badge key={label.text} tone={label.tone}>
                {label.text}
              </Badge>
            ))}
          </div>
        </Step>

        <Step index={2}>
          <p className="flex items-center gap-2 text-app text-fg">
            <Bot className="h-4 w-4 text-accent" aria-hidden="true" />
            {demo.routed}
          </p>
        </Step>

        <Step index={3}>
          <p className="text-small text-fg-muted">{demo.draftLabel}</p>
          <p className="mt-1 rounded-lg border border-border bg-canvas p-4 text-app text-fg">{demo.draft}</p>
        </Step>

        <Step index={4}>
          <p className="flex items-center gap-2 text-app text-fg-muted">
            <CircleCheck className="h-4 w-4 text-success" aria-hidden="true" />
            {demo.checked}
          </p>
        </Step>
      </div>
    </Card>
  );
}

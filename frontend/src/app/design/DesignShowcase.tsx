'use client';

import { useState } from 'react';
import { Badge } from '../../components/ui/Badge';
import { Button, ButtonLink } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { Container } from '../../components/ui/Container';
import { Input, PasswordInput, Textarea } from '../../components/ui/Input';
import { Logo } from '../../components/ui/Logo';
import { ConfirmDialog, Modal } from '../../components/ui/Modal';
import { ThemeToggle } from '../../components/ui/ThemeToggle';

// Class names are written out in full so Tailwind can see them.
const SWATCHES = [
  ['canvas', 'bg-canvas'],
  ['surface', 'bg-surface'],
  ['surface-raised', 'bg-surface-raised'],
  ['border', 'bg-border'],
  ['border-strong', 'bg-border-strong'],
  ['fg', 'bg-fg'],
  ['fg-muted', 'bg-fg-muted'],
  ['fg-subtle', 'bg-fg-subtle'],
  ['brand', 'bg-brand'],
  ['brand-hover', 'bg-brand-hover'],
  ['brand-soft', 'bg-brand-soft'],
  ['accent', 'bg-accent'],
  ['success', 'bg-success'],
  ['warning', 'bg-warning'],
  ['danger', 'bg-danger'],
  ['info', 'bg-info'],
] as const;

const TYPE_SAMPLES = [
  ['display', 'text-display'],
  ['h1', 'text-h1'],
  ['h2', 'text-h2'],
  ['h3', 'text-h3'],
  ['body-lg', 'text-body-lg'],
  ['body', 'text-body'],
  ['app', 'text-app'],
  ['small', 'text-small'],
  ['caption', 'text-caption'],
  ['mono', 'text-mono font-mono'],
] as const;

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-stack">
      <h2 className="text-h2 text-fg">{title}</h2>
      {children}
    </section>
  );
}

export function DesignShowcase() {
  const [modal, setModal] = useState(false);
  const [confirm, setConfirm] = useState(false);

  return (
    <main className="min-h-screen bg-canvas text-fg">
      <header className="border-b border-border">
        <Container size="app" className="flex h-16 items-center justify-between">
          <Logo />
          <ThemeToggle />
        </Container>
      </header>

      <Container size="app" className="flex flex-col gap-section py-12">
        <div className="flex flex-col gap-3">
          <h1 className="text-h1">Design system</h1>
          <p className="max-w-prose text-body-lg text-fg-muted">
            Every primitive on the current theme and mode. Development only; this route returns 404 in production.
          </p>
        </div>

        <Group title="Colors">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-8">
            {SWATCHES.map(([name, cls]) => (
              <div key={name} className="flex flex-col gap-2">
                <div className={`h-16 rounded-lg border border-border ${cls}`} />
                <span className="text-caption text-fg-muted">{name}</span>
              </div>
            ))}
          </div>
        </Group>

        <Group title="Type scale">
          <div className="flex flex-col gap-4">
            {TYPE_SAMPLES.map(([name, cls]) => (
              <div key={name} className="flex flex-col gap-1 border-b border-border pb-4">
                <span className="text-caption text-fg-subtle">{name}</span>
                <span className={cls}>Agents resolve it, people review it</span>
              </div>
            ))}
          </div>
        </Group>

        <Group title="Buttons">
          <div className="flex flex-wrap items-center gap-3">
            <Button>Primary</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="destructive">Destructive</Button>
            <Button disabled>Disabled</Button>
            <ButtonLink href="/design" variant="secondary">
              Link button
            </ButtonLink>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button size="sm">Small</Button>
            <Button size="md">Medium</Button>
            <Button size="lg">Large</Button>
          </div>
        </Group>

        <Group title="Badges">
          <div className="flex flex-wrap gap-2">
            <Badge>Neutral</Badge>
            <Badge tone="brand">Brand</Badge>
            <Badge tone="accent">Agent active</Badge>
            <Badge tone="success">Resolved</Badge>
            <Badge tone="warning">Needs review</Badge>
            <Badge tone="danger">Failed</Badge>
            <Badge tone="info">Info</Badge>
          </div>
        </Group>

        <Group title="Form fields">
          <div className="grid max-w-xl gap-4">
            <Input aria-label="Email" placeholder="you@company.com" />
            <Input aria-label="Email with error" placeholder="Invalid value" invalid />
            <PasswordInput aria-label="Password" placeholder="Password" />
            <Textarea aria-label="Message" placeholder="Describe the problem" />
          </div>
        </Group>

        <Group title="Cards">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <h3 className="mb-1 text-h3">Standard card</h3>
              <p className="text-app text-fg-muted">Surface, hairline border and 24 px padding.</p>
            </Card>
            <Card raised>
              <h3 className="mb-1 text-h3">Raised card</h3>
              <p className="text-app text-fg-muted">For panels that float above the page.</p>
            </Card>
          </div>
        </Group>

        <Group title="Dialogs">
          <div className="flex gap-3">
            <Button variant="secondary" onClick={() => setModal(true)}>
              Open modal
            </Button>
            <Button variant="secondary" onClick={() => setConfirm(true)}>
              Open confirm
            </Button>
          </div>
        </Group>
      </Container>

      <Modal open={modal} onClose={() => setModal(false)} title="Modal title">
        <p className="text-app text-fg-muted">Focus stays inside until you close it.</p>
      </Modal>
      <ConfirmDialog
        open={confirm}
        title="Delete ticket"
        message="This cannot be undone."
        confirmLabel="Delete"
        onConfirm={() => setConfirm(false)}
        onCancel={() => setConfirm(false)}
      />
    </main>
  );
}

import Link from 'next/link';
import type { ReactNode } from 'react';
import { theme } from '../../theme/theme.config';
import { Card } from '../ui/Card';
import { Container } from '../ui/Container';
import { GlowBackdrop } from '../ui/GlowBackdrop';
import { Logo } from '../ui/Logo';
import { ThemeToggle } from '../ui/ThemeToggle';

/** Inline link inside an auth card or footer. */
export const AUTH_LINK = 'font-medium text-fg underline underline-offset-4 transition-colors hover:text-brand';

/**
 * Shared shell for login, register, forgot password and reset password: a glow background, the brand link and
 * theme toggle in a header, and one raised card that carries the page's h1. `footer` renders below the card in
 * a block element, so any content (text, links, paragraphs) is fine.
 */
export function AuthLayout({
  title,
  description,
  footer,
  children,
}: {
  title: string;
  description?: string;
  footer?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-canvas">
      <GlowBackdrop />
      <header className="relative z-10">
        <Container className="flex h-[var(--l-header-height)] items-center justify-between">
          <Link href="/" aria-label={`${theme.brand.name} home`} className="rounded-md">
            <Logo />
          </Link>
          <ThemeToggle />
        </Container>
      </header>

      <main className="relative z-10 flex flex-1 flex-col items-center justify-center px-page pb-16 pt-6">
        <Card raised className="w-full max-w-md p-8 sm:p-10">
          <h1 className="text-h2 text-fg">{title}</h1>
          {description && <p className="mt-2 text-app text-fg-muted">{description}</p>}
          <div className="mt-8">{children}</div>
        </Card>
        {footer && <div className="mt-6 text-center text-app text-fg-muted">{footer}</div>}
      </main>
    </div>
  );
}

import Link from 'next/link';
import { theme } from '../../theme/theme.config';
import { ButtonLink } from '../ui/Button';
import { Container } from '../ui/Container';
import { Logo } from '../ui/Logo';
import { ThemeToggle } from '../ui/ThemeToggle';
import { nav } from './content';

export function Nav() {
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-canvas/80 backdrop-blur-md">
      <Container className="flex h-[var(--l-header-height)] items-center justify-between gap-6">
        <Link href="/" aria-label={`${theme.brand.name} home`} className="rounded-md">
          <Logo />
        </Link>

        <nav aria-label="Primary" className="hidden items-center gap-4 md:flex lg:gap-6">
          {nav.links.map((link) => (
            <a key={link.href} href={link.href} className="whitespace-nowrap text-app text-fg-muted transition-colors hover:text-fg">
              {link.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2 sm:gap-3">
          {/* ThemeToggle has its own inline-flex class; cx does not resolve conflicts, so wrap it to control visibility */}
          <div className="hidden sm:block">
            <ThemeToggle />
          </div>
          <ButtonLink href={nav.signIn.href} variant="ghost" size="sm">
            {nav.signIn.label}
          </ButtonLink>
          <ButtonLink href={nav.getStarted.href} size="sm">
            {nav.getStarted.label}
          </ButtonLink>
        </div>
      </Container>
    </header>
  );
}

import Link from 'next/link';
import { theme } from '../../theme/theme.config';
import { Container } from '../ui/Container';
import { Logo } from '../ui/Logo';
import { ThemeToggle } from '../ui/ThemeToggle';
import { footer } from './content';

export function Footer() {
  return (
    <footer className="border-t border-border py-10">
      <Container className="flex flex-col items-start justify-between gap-6 sm:flex-row sm:items-center">
        <div className="flex flex-col gap-2">
          <Logo />
          <p className="text-small text-fg-muted">
            © {new Date().getFullYear()} {theme.brand.name}
          </p>
        </div>

        <nav aria-label="Footer" className="flex items-center gap-6 text-app text-fg-muted">
          {footer.links.map((link) => (
            <Link key={link.href} href={link.href} className="transition-colors hover:text-fg">
              {link.label}
            </Link>
          ))}
        </nav>

        <ThemeToggle />
      </Container>
    </footer>
  );
}

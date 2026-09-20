'use client';

import type { ReactNode } from 'react';
import Link from 'next/link';
import { LogOut } from 'lucide-react';
import { cx } from '../lib/cx';
import { ThemeToggle } from './ui/ThemeToggle';

// UR-001: every signed-in workspace (customer, agent, admin) shares this one navigation layout instead of
// building its own: brand block, primary nav, signed-in identity, footer links, sign out.
//
// One set of DOM nodes, laid out responsively: a sticky sidebar from `lg` up, the same blocks stacked as a top
// bar below it - so nothing is duplicated for mobile and nothing has to be re-learned on a phone.
//
// A nav item is either a route (`href`) or an in-page tab (`onClick`); both look and behave the same way.

export type ShellNavItem = {
  key: string;
  label: string;
  icon: ReactNode;
  active?: boolean;
  /** Draws attention (e.g. a queue that needs someone). Ignored while the item is active. */
  warn?: boolean;
} & ({ href: string; onClick?: undefined } | { onClick: () => void; href?: undefined });

export type ShellLink = { key: string; label: string; icon: ReactNode; href: string; tone?: 'default' | 'brand' | 'success' };

const NAV_ITEM =
  'flex flex-1 shrink-0 items-center gap-3 rounded-lg border px-3.5 py-2.5 text-left text-app font-medium whitespace-nowrap transition-colors lg:w-full lg:flex-none';
// Text never sits on the brand-soft wash (brand on it is 4.39:1 in light mode, below AA); the wash + border
// mark the active item, and only the decorative icon takes the brand colour.
const NAV_ACTIVE = 'border-brand/40 bg-brand-soft text-fg';
const NAV_IDLE = 'border-transparent text-fg-muted hover:bg-brand-soft hover:text-fg';

const FOOTER_ITEM =
  'flex items-center rounded-lg px-3 py-2 text-app whitespace-nowrap transition-colors hover:bg-brand-soft lg:px-3.5';
const TONES = {
  default: 'text-fg-muted hover:text-fg',
  brand: 'text-brand hover:text-brand-hover',
  success: 'text-success hover:text-fg',
} as const;

export function AppShell({
  brand,
  nav,
  links = [],
  email,
  onSignOut,
  mainClassName,
  children,
}: {
  brand: { icon: ReactNode; title: ReactNode; subtitle: string };
  nav: ShellNavItem[];
  links?: ShellLink[];
  email?: string | null;
  onSignOut: () => void;
  /** Extra classes for the content area (e.g. centring). */
  mainClassName?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-dvh flex-col bg-canvas text-fg lg:flex-row">
      <aside className="flex flex-col border-b border-border bg-surface lg:sticky lg:top-0 lg:h-dvh lg:w-64 lg:shrink-0 lg:border-b-0 lg:border-r">
        <div className="flex items-center gap-3 border-b border-border p-4 lg:p-6">
          <div className="shrink-0 rounded-lg border border-border bg-brand-soft p-2 text-brand">{brand.icon}</div>
          <div className="min-w-0">
            <div className="text-app font-semibold leading-tight text-fg">{brand.title}</div>
            <p className="hidden truncate text-caption text-fg-muted lg:block">{brand.subtitle}</p>
          </div>
        </div>

        <nav aria-label="Main" className="flex flex-row gap-1 overflow-x-auto p-3 lg:flex-1 lg:flex-col lg:overflow-y-auto lg:p-4">
          {nav.map((item) => {
            const className = cx(NAV_ITEM, item.active ? NAV_ACTIVE : NAV_IDLE);
            const content = (
              <>
                <span className={cx('flex shrink-0', item.active && 'text-brand', item.warn && !item.active && 'text-warning')} aria-hidden="true">{item.icon}</span>
                <span className="truncate">{item.label}</span>
              </>
            );
            return item.href !== undefined ? (
              <Link key={item.key} href={item.href} aria-current={item.active ? 'page' : undefined} className={className}>
                {content}
              </Link>
            ) : (
              <button key={item.key} type="button" onClick={item.onClick} aria-current={item.active ? 'page' : undefined} className={className}>
                {content}
              </button>
            );
          })}
        </nav>

        <div className="flex flex-row flex-wrap items-center justify-between gap-3 border-t border-border p-3 lg:flex-col lg:flex-nowrap lg:items-stretch lg:justify-start lg:gap-1 lg:p-4">
          {email && (
            <p className="min-w-0 max-w-full truncate text-caption text-fg-muted lg:pb-2" title={email}>
              Logged in as <span className="text-brand">{email}</span>
            </p>
          )}
          <div className="flex flex-wrap items-center gap-2 lg:flex-col lg:flex-nowrap lg:items-stretch lg:gap-1">
            {links.map((l) => (
              <Link key={l.key} href={l.href} className={cx(FOOTER_ITEM, TONES[l.tone ?? 'default'])}>
                <span className="mr-2 flex" aria-hidden="true">{l.icon}</span>
                {l.label}
              </Link>
            ))}
            <button type="button" onClick={onSignOut} className={cx(FOOTER_ITEM, TONES.default, 'hover:text-danger')}>
              <LogOut className="mr-2 h-4 w-4" aria-hidden="true" /> Sign out
            </button>
            <ThemeToggle className="self-start lg:mt-2" />
          </div>
        </div>
      </aside>

      <main className={cx('min-w-0 max-w-[1800px] flex-1 px-page py-8 lg:px-10', mainClassName)}>{children}</main>
    </div>
  );
}

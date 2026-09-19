'use client';

import type { ReactNode } from 'react';
import Link from 'next/link';
import { LogOut } from 'lucide-react';

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

export type ShellLink = { key: string; label: string; icon: ReactNode; href: string; tone?: 'default' | 'amber' | 'emerald' };

const NAV_ITEM =
  'w-full shrink-0 flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-sm font-medium text-left whitespace-nowrap transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-[#E8A33D]/60';
const NAV_ACTIVE = 'bg-[#E8A33D]/20 text-[#E8A33D] border border-[#E8A33D]/40 shadow-[0_0_15px_rgba(232,163,61,0.15)]';
const NAV_IDLE = 'text-[#8A8F98] hover:text-[#ECECEC] border border-transparent hover:bg-white/[0.04]';

const FOOTER_ITEM =
  'flex items-center text-sm px-3 lg:px-3.5 py-2 rounded-lg whitespace-nowrap transition-colors outline-none focus-visible:ring-2 focus-visible:ring-[#E8A33D]/60 hover:bg-white/[0.06]';
const TONES = {
  default: 'text-[#8A8F98] hover:text-[#ECECEC]',
  amber: 'text-[#E8A33D] hover:text-[#F4B856]',
  emerald: 'text-emerald-300 hover:text-emerald-200',
} as const;

export function AppShell({
  brand,
  nav,
  links = [],
  email,
  onSignOut,
  mainClassName = '',
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
    <div className="min-h-screen flex flex-col lg:flex-row">
      <aside className="flex flex-col lg:w-64 lg:shrink-0 lg:h-screen lg:sticky lg:top-0 border-b lg:border-b-0 lg:border-r border-white/10 bg-white/[0.02] backdrop-blur-xl">
        <div className="p-4 lg:p-6 border-b border-white/10 flex items-center space-x-3">
          <div className="bg-[#E8A33D]/15 p-2 rounded-xl border border-[#E8A33D]/25 shrink-0">{brand.icon}</div>
          <div className="min-w-0">
            <div className="text-sm font-bold text-[#ECECEC] leading-tight">{brand.title}</div>
            <p className="text-xs text-[#8A8F98] truncate hidden lg:block">{brand.subtitle}</p>
          </div>
        </div>

        <nav aria-label="Main" className="flex flex-row lg:flex-col gap-1 p-3 lg:p-4 overflow-x-auto lg:overflow-y-auto lg:flex-1">
          {nav.map((item) => {
            const className = `${NAV_ITEM} ${item.active ? NAV_ACTIVE : NAV_IDLE}`;
            const content = (
              <>
                <span className={`shrink-0 flex ${item.warn && !item.active ? 'text-[#FB923C]' : ''}`} aria-hidden="true">{item.icon}</span>
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

        <div className="p-3 lg:p-4 border-t border-white/10 flex flex-row lg:flex-col items-center lg:items-stretch justify-between lg:justify-start gap-3 lg:gap-1">
          {email && (
            <p className="text-xs text-[#8A8F98] truncate lg:pb-2" title={email}>
              Logged in as <span className="text-[#E8A33D]">{email}</span>
            </p>
          )}
          <div className="flex items-center lg:flex-col lg:items-stretch gap-2 lg:gap-1 shrink-0 overflow-x-auto">
            {links.map((l) => (
              <Link key={l.key} href={l.href} className={`${FOOTER_ITEM} ${TONES[l.tone ?? 'default']}`}>
                <span className="mr-2 flex" aria-hidden="true">{l.icon}</span>
                {l.label}
              </Link>
            ))}
            <button onClick={onSignOut} className={`${FOOTER_ITEM} ${TONES.default} hover:!text-[#FB7185]`}>
              <LogOut className="w-4 h-4 mr-2" aria-hidden="true" /> Sign out
            </button>
          </div>
        </div>
      </aside>

      <main className={`flex-1 min-w-0 py-8 px-4 sm:px-6 lg:px-10 max-w-[1800px] ${mainClassName}`}>{children}</main>
    </div>
  );
}

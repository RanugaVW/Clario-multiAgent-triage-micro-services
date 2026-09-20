'use client';

import { Monitor, Moon, Sun } from 'lucide-react';
import { cx } from '../../lib/cx';
import type { Preference } from '../../theme/mode';
import { useTheme } from '../../theme/ThemeProvider';

const OPTIONS: Array<{ value: Preference; label: string; Icon: typeof Sun }> = [
  { value: 'system', label: 'System', Icon: Monitor },
  { value: 'light', label: 'Light', Icon: Sun },
  { value: 'dark', label: 'Dark', Icon: Moon },
];

export function ThemeToggle({ className }: { className?: string }) {
  const { preference, setPreference } = useTheme();
  return (
    <div
      role="group"
      aria-label="Color theme"
      className={cx('inline-flex items-center gap-0.5 rounded-pill border border-border bg-surface p-0.5', className)}
    >
      {OPTIONS.map(({ value, label, Icon }) => {
        const selected = preference === value;
        return (
          <button
            key={value}
            type="button"
            aria-pressed={selected}
            aria-label={label}
            title={label}
            onClick={() => setPreference(value)}
            className={cx(
              'inline-flex h-8 w-8 items-center justify-center rounded-pill transition-colors',
              selected ? 'bg-brand-soft text-brand' : 'text-fg-muted hover:text-fg'
            )}
          >
            <Icon className="h-4 w-4" aria-hidden="true" />
          </button>
        );
      })}
    </div>
  );
}

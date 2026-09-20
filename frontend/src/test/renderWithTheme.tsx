import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { vi } from 'vitest';
import { ThemeProvider } from '../theme/ThemeProvider';

/**
 * Renders inside <ThemeProvider> so components that use useTheme (ThemeToggle) work. The test file itself must
 * mock next/navigation's usePathname, e.g. vi.mock('next/navigation', () => ({ usePathname: () => '/' })),
 * because vi.mock is hoisted per file.
 */
export function renderWithTheme(ui: ReactElement, migratedRoutes: readonly string[] = ['/']) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: true,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia;
  return render(<ThemeProvider migratedRoutes={migratedRoutes}>{ui}</ThemeProvider>);
}

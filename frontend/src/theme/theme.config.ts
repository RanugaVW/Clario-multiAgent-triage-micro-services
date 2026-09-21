import type { Theme } from './types';

/**
 * THE ONE FILE A COMPANY EDITS TO RE-SKIN THE PRODUCT.
 *
 * Everything visual comes from here: name, logo, colors for light and dark mode, type scale, spacing,
 * radii, layout widths and motion. Components read these through CSS variables (see css.ts) and Tailwind
 * utilities (see globals.css); no component contains a color.
 *
 * Fonts are the one exception: next/font needs literal arguments, so the two font choices live in
 * ./fonts.ts. Change the font there and, if needed, the fallback stacks below.
 *
 * After editing, run `npm test`. theme.config.test.ts fails and names the pair if any text color
 * becomes unreadable on a surface. Colors that the test reads must be #rrggbb.
 *
 * Default theme: "Agentic AI", indigo with a cyan accent.
 */
export const theme: Theme = {
  brand: {
    name: 'Clario',
    tagline: 'Intelligent agentic support',
    description: 'Submit and track support tickets with AI-powered triage.',
    mark: {
      viewBox: '0 0 24 24',
      path: 'M18.5 6.8A8.25 8.25 0 1 0 18.5 17.2',
      dot: { cx: 12, cy: 12, r: 2 },
    },
  },

  colors: {
    dark: {
      canvas: '#0A0B14',
      surface: '#10121F',
      'surface-raised': '#171A2B',
      border: '#23263A',
      'border-strong': '#63698F',
      fg: '#F2F3FA',
      'fg-muted': '#A3A7C2',
      'fg-subtle': '#7D82A2',
      brand: '#7C7CFF',
      'brand-hover': '#9494FF',
      'brand-fg': '#0A0B14',
      'brand-soft': 'rgba(124, 124, 255, 0.14)',
      accent: '#22D3EE',
      success: '#34D399',
      warning: '#FBBF24',
      danger: '#F87171',
      info: '#60A5FA',
      focus: '#A5A5FF',
      glow: 'rgba(124, 124, 255, 0.35)',
    },
    light: {
      canvas: '#F7F8FC',
      surface: '#FFFFFF',
      'surface-raised': '#FFFFFF',
      border: '#E3E5F0',
      'border-strong': '#868BA4',
      fg: '#0E1020',
      'fg-muted': '#4B5070',
      'fg-subtle': '#626784',
      brand: '#5B5BF0',
      'brand-hover': '#4A4AE0',
      'brand-fg': '#FFFFFF',
      'brand-soft': 'rgba(91, 91, 240, 0.10)',
      accent: '#0E7490',
      success: '#047857',
      warning: '#B45309',
      danger: '#DC2626',
      info: '#2563EB',
      focus: '#5B5BF0',
      glow: 'rgba(91, 91, 240, 0.20)',
    },
  },

  shadows: {
    dark: { card: '0 0 #0000', raised: '0 12px 40px rgba(0, 0, 0, 0.45)' },
    light: {
      card: '0 1px 2px rgba(14, 16, 32, 0.05), 0 1px 1px rgba(14, 16, 32, 0.03)',
      raised: '0 8px 24px rgba(14, 16, 32, 0.08), 0 2px 6px rgba(14, 16, 32, 0.05)',
    },
  },

  // Data-viz palettes. Validated per mode by components/charts/tokens.test.ts (contrast, ordering, step gaps).
  // Dark ramps brighten with severity/magnitude; light ramps darken. Emitted as --ch-* by css.ts.
  charts: {
    dark: {
      ink: { primary: '#ECECEC', secondary: '#C3C2B7', muted: '#898781' },
      chrome: { grid: '#2c2c2a', axis: '#383835' },
      series: { blue: '#3987e5', orange: '#d95926', aqua: '#199e70', yellow: '#c98500' },
      ordinal: ['#184f95', '#256abf', '#3987e5', '#86b6ef', '#b7d3f6'],
      sequential: ['#0d366b', '#104281', '#184f95', '#1c5cab', '#256abf', '#2a78d6', '#3987e5', '#5598e7', '#6da7ec', '#86b6ef'],
      emptyCell: '#1a1b21',
      deemphasis: '#60646d',
      status: { good: '#0ca30c', warning: '#fbbf24', serious: '#f4926e', critical: '#e0284a' },
    },
    light: {
      ink: { primary: '#0E1020', secondary: '#3E4360', muted: '#5A6080' },
      chrome: { grid: '#E3E5F0', axis: '#C9CDE0' },
      series: { blue: '#2A5FC0', orange: '#CC4A0E', aqua: '#0B5D57', yellow: '#B8860B' },
      ordinal: ['#BBD1F5', '#86AEEB', '#4F86DD', '#2A5FB5', '#173F86'],
      sequential: ['#DCE8FB', '#C6D9F7', '#AFCAF3', '#98BAEE', '#7FA8E7', '#6595DF', '#4C82D6', '#376DC7', '#2857AD', '#173F86'],
      emptyCell: '#F1F3F9',
      deemphasis: '#7A8098',
      status: { good: '#15803D', warning: '#7A4E00', serious: '#F26A2E', critical: '#B0173A' },
    },
  },

  fontStacks: {
    sans: 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    mono: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
  },

  type: {
    display: { size: 'clamp(2.75rem, 1.6rem + 4.6vw, 4.5rem)', lineHeight: '1.05', weight: 600, tracking: '-0.03em' },
    h1: { size: 'clamp(2rem, 1.3rem + 2.2vw, 3rem)', lineHeight: '1.1', weight: 600, tracking: '-0.025em' },
    h2: { size: 'clamp(1.5rem, 1.1rem + 1.4vw, 2.25rem)', lineHeight: '1.2', weight: 600, tracking: '-0.02em' },
    h3: { size: '1.25rem', lineHeight: '1.35', weight: 600, tracking: '-0.01em' },
    'body-lg': { size: '1.125rem', lineHeight: '1.6', weight: 400, tracking: '0' },
    body: { size: '1rem', lineHeight: '1.6', weight: 400, tracking: '0' },
    app: { size: '0.875rem', lineHeight: '1.5', weight: 400, tracking: '0' },
    small: { size: '0.8125rem', lineHeight: '1.5', weight: 400, tracking: '0' },
    caption: { size: '0.75rem', lineHeight: '1.4', weight: 500, tracking: '0.01em' },
    mono: { size: '0.8125rem', lineHeight: '1.5', weight: 400, tracking: '0' },
  },

  space: {
    section: 'clamp(4rem, 3rem + 5vw, 8rem)', // 64 px on phones, 96 to 128 px on desktop
    page: 'clamp(1rem, 0.5rem + 2vw, 2rem)', // page side padding
    card: '1.5rem', // 24 px
    stack: '1rem', // default gap between related items
  },

  radius: { sm: '6px', md: '10px', lg: '14px', xl: '20px', pill: '9999px' },

  layout: {
    containerMarketing: '75rem', // 1200 px
    containerApp: '90rem', // 1440 px
    headerHeight: '4rem',
    sidebarWidth: '16rem',
  },

  motion: {
    durationFast: '150ms',
    durationBase: '250ms',
    durationSlow: '600ms',
    easeOut: 'cubic-bezier(0.16, 1, 0.3, 1)',
    easeInOut: 'cubic-bezier(0.65, 0, 0.35, 1)',
    heroStagger: 0.08,
    revealOffset: 12,
  },
};

export const COLOR_TOKENS = [
  'canvas',
  'surface',
  'surface-raised',
  'border',
  'border-strong',
  'fg',
  'fg-muted',
  'fg-subtle',
  'brand',
  'brand-hover',
  'brand-fg',
  'brand-soft',
  'accent',
  'success',
  'warning',
  'danger',
  'info',
  'focus',
  'glow',
] as const;

export type ColorToken = (typeof COLOR_TOKENS)[number];
export type ColorSet = Record<ColorToken, string>;

export type TypeRole =
  | 'display'
  | 'h1'
  | 'h2'
  | 'h3'
  | 'body-lg'
  | 'body'
  | 'app'
  | 'small'
  | 'caption'
  | 'mono';

export interface TypeStyle {
  size: string;
  lineHeight: string;
  weight: number;
  tracking: string;
}

export type RadiusKey = 'sm' | 'md' | 'lg' | 'xl' | 'pill';

export interface Shadows {
  card: string;
  raised: string;
}

export interface ChartPalette {
  ink: { primary: string; secondary: string; muted: string };
  chrome: { grid: string; axis: string };
  series: { blue: string; orange: string; aqua: string; yellow: string };
  /** 5 steps, one hue. Dark: index 0 is nearest the surface (darkest) and severity climbs brighter. Light: index 0 is lightest and severity climbs DARKER. */
  ordinal: [string, string, string, string, string];
  /** 10 steps for magnitude (heatmap): more = more prominent against the surface. */
  sequential: [string, string, string, string, string, string, string, string, string, string];
  emptyCell: string;
  deemphasis: string;
  status: { good: string; warning: string; serious: string; critical: string };
}

export interface Theme {
  brand: {
    name: string;
    tagline: string;
    /** Page meta description (search results, link previews). */
    description: string;
    /** Single-stroke logo mark, drawn in the brand color. Company supplies its own path data. */
    mark: { viewBox: string; path: string; dot?: { cx: number; cy: number; r: number } };
  };
  colors: { light: ColorSet; dark: ColorSet };
  shadows: { light: Shadows; dark: Shadows };
  /** Data-viz palettes per mode, emitted as --ch-* variables and read by components/charts/tokens.ts. */
  charts: { light: ChartPalette; dark: ChartPalette };
  /** CSS fallback stacks that follow the next/font face declared in fonts.ts. */
  fontStacks: { sans: string; mono: string };
  type: Record<TypeRole, TypeStyle>;
  space: { section: string; page: string; card: string; stack: string };
  radius: Record<RadiusKey, string>;
  layout: {
    containerMarketing: string;
    containerApp: string;
    headerHeight: string;
    sidebarWidth: string;
  };
  motion: {
    durationFast: string;
    durationBase: string;
    durationSlow: string;
    easeOut: string;
    easeInOut: string;
    /** Seconds between hero elements entering. Read from JS (framer-motion). */
    heroStagger: number;
    /** Pixels an in-view section rises while fading in. Read from JS. */
    revealOffset: number;
  };
}

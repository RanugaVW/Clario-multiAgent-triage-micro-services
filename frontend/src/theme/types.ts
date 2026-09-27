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

/**
 * The lensed-disc ("black hole") effect above the hero card. The bloom is a stack of the same dome
 * shape in five colours, so `core` -> `glow1` -> `glow2` -> `glow3` -> `glow4` must read as one
 * continuous hot-to-cold progression (white -> pink -> magenta -> violet -> blue in dark mode).
 */
export interface HorizonPalette {
  /** White-hot centre of the dome and the brightest part of the horizon line. */
  core: string;
  /** First fringe outside the core (hot pink in dark mode). */
  glow1: string;
  /** Second fringe: the saturated mid band (magenta). */
  glow2: string;
  /** Third fringe: the wide bloom (violet). */
  glow3: string;
  /** Outermost fringe: the faint dome that fades into the page (blue-violet). */
  glow4: string;
  /** The bright photon ring around the disc. */
  ring: string;
  /** Inner photon ring (a second accent hue). */
  ringAlt: string;
  /** Thin flares that run along the horizon line either side of the dome. */
  flare: string;
  /** Hottest point of the horizon streak: the hairline that lands on the card's top edge. */
  line: string;
  /** The widest, softest dome of light behind every other layer (may be translucent). */
  halo: string;
  /** Top of the dark disc inside the rings. */
  disc: string;
  /** Glow at the bottom of the disc, where it meets the horizon. */
  discGlow: string;
  /** The rim of the disc, its darkest point (near-black in dark mode). */
  void: string;
  /** Stars, the faint outer arcs and their node dots. */
  star: string;
  /** Opacity 0..1 of the glow reflected onto the card below, as a string. */
  reflect: string;
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
  /** Landing hero event horizon palettes per mode, emitted as --hz-* variables. */
  horizon: { light: HorizonPalette; dark: HorizonPalette };
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

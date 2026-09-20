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

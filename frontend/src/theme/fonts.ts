import { Inter, JetBrains_Mono } from 'next/font/google';

/**
 * The two font choices for the product. next/font needs literal arguments, which is why these two calls
 * cannot live in theme.config.ts. To change a font: swap the import and the call below, keep the `variable`
 * names as they are, and update fontStacks in theme.config.ts if the fallback should change.
 *
 * Inter is a variable font, so every weight is available from one file. `latin-ext` covers most European
 * languages; add `cyrillic` or `greek` here if a company needs them.
 */
export const sansFont = Inter({ subsets: ['latin', 'latin-ext'], display: 'swap', variable: '--font-face-sans' });
export const monoFont = JetBrains_Mono({ subsets: ['latin'], display: 'swap', variable: '--font-face-mono' });

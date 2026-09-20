import { extendTailwindMerge } from 'tailwind-merge';
import { theme } from '../theme/theme.config';

/**
 * tailwind-merge only knows Tailwind's default scales. This project defines its own utilities in
 * globals.css `@theme inline` (text-h2, p-card, shadow-raised, rounded-pill, max-w-marketing ...), and
 * without registering them `text-h2` would be read as a text COLOR and dropped next to `text-fg`.
 * The keys are derived from theme.config.ts so they stay in sync with it. A brand-new utility family
 * added to globals.css `@theme inline` must be registered here too.
 */
const spacingKeys = Object.keys(theme.space);
const shadowKeys = Object.keys(theme.shadows.light);
const radiusKeys = Object.keys(theme.radius);
// theme.layout uses containerMarketing / containerApp; the utilities are max-w-marketing / max-w-app.
const containerKeys = ['marketing', 'app'];

const twMerge = extendTailwindMerge({
  extend: {
    theme: {
      spacing: spacingKeys,
      container: containerKeys,
      shadow: shadowKeys,
      radius: radiusKeys,
    },
    classGroups: {
      'font-size': [{ text: Object.keys(theme.type) }],
    },
  },
});

export function cx(...parts: Array<string | false | null | undefined>): string {
  return twMerge(parts.filter(Boolean).join(' '));
}

# Re-skinning the product for a company

Colors, type, spacing, radii, layout widths, motion (durations, easing, stagger, reveal distance) and the brand name, description and logo come from `theme.config.ts`; the fonts come from `fonts.ts` (two lines). The landing page copy lives in `src/components/landing/content.ts`.

1. `theme.config.ts`: name, logo, colors (light and dark), type scale, spacing, radii, layout widths, motion.
2. `fonts.ts`: the two font families.

## Steps

1. Copy the repo for the company (or branch it).
2. In `theme.config.ts`:
   - Set `brand.name`, `brand.tagline`, `brand.description` (the page meta description), and `brand.mark` (the logo as one SVG stroke path in a 24 x 24 box, plus an optional dot).
   - Replace the values under `colors.light` and `colors.dark`. Keep every token; add none. The names describe the role (`brand` is the main action color, `accent` marks "an agent is working", `canvas` is the page background), not the hue.
   - Colors the tests read must be `#rrggbb`. `brand-soft` and `glow` may be `rgba(...)`.
3. Run `npm test`. `theme.config.test.ts` checks that every text color is readable (WCAG AA, 4.5:1) on every surface in both modes. If a pair fails, the message names it and the ratio; adjust that one token.
4. To change a font, edit `fonts.ts`: swap the import and call, keep the `variable` names, and update `fontStacks` in `theme.config.ts` if the fallback should change.
5. Run `npm run dev` and open `/design` to see every component in both modes.

## What not to do

- Do not put colors or sizes in components or in `globals.css`. Add or change a token in `theme.config.ts` instead.
- Do not add `dark:` variants. Dark and light are both defined in the theme file and switch through CSS variables.

## What is not themeable yet

- The radius scale stops at `xl`; `2xl` to `4xl` alias it.
- `theme.charts` (the chart palette) arrives in Phase 6.
- The Logo has a fixed 24 x 24 box, stroke width and wordmark styling.
- Destructive buttons hover by opacity; there is no `danger-hover` token.
- `MIGRATED_ROUTES` (`src/theme/migrated-routes.ts`): a new route renders dark-only until it is listed there.
- Badge borders use the tone colour at 40% opacity.
- The example ticket's cadence and step distance, and the glow's drift, blur and size, are written in `src/app/globals.css` and `src/components/ui/GlowBackdrop.tsx`.
- The `scroll-mt-20` anchor offset on the landing sections should equal the header height (`--l-header-height`) but is written by hand.
- The landing icon tiles have a fixed size.

## Passing className to a primitive

`cx` only concatenates class names. Which utility wins a conflict is decided by Tailwind's emit order and the specificity of variants such as `focus:`, not by the order in the string, so a `className` you pass does not reliably override a primitive's own utility. Prefer, in this order:

- An explicit prop: `Card flush` removes the card padding instead of passing a padding class.
- A wrapper element: the landing nav wraps the theme toggle in a `hidden sm:block` element rather than passing display classes to it.
- Putting the utility on a variant that is emitted later: the skip link uses `focus:px-4 focus:py-2` because `focus:not-sr-only` resets padding at a higher specificity than a plain `px-4`.

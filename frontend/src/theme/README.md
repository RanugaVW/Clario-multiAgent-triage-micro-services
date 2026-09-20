# Re-skinning the product for a company

Everything visual comes from two files:

1. `theme.config.ts`: name, logo, colors (light and dark), type scale, spacing, radii, layout widths, motion.
2. `fonts.ts`: the two font families (two lines).

## Steps

1. Copy the repo for the company (or branch it).
2. In `theme.config.ts`:
   - Set `brand.name`, `brand.tagline`, and `brand.mark` (the logo as one SVG stroke path in a 24 x 24 box, plus an optional dot).
   - Replace the values under `colors.light` and `colors.dark`. Keep every token; add none. The names describe the role (`brand` is the main action color, `accent` marks "an agent is working", `canvas` is the page background), not the hue.
   - Colors the tests read must be `#rrggbb`. `brand-soft` and `glow` may be `rgba(...)`.
3. Run `npm test`. `theme.config.test.ts` checks that every text color is readable (WCAG AA, 4.5:1) on every surface in both modes. If a pair fails, the message names it and the ratio; adjust that one token.
4. To change a font, edit `fonts.ts`: swap the import and call, keep the `variable` names, and update `fontStacks` in `theme.config.ts` if the fallback should change.
5. Run `npm run dev` and open `/design` to see every component in both modes.

## What not to do

- Do not put colors or sizes in components or in `globals.css`. Add or change a token in `theme.config.ts` instead.
- Do not add `dark:` variants. Dark and light are both defined in the theme file and switch through CSS variables.

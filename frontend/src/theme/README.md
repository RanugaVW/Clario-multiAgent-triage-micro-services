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

## Modes and charts

Every route follows the theme: the `ThemeToggle` (System, Light, Dark) and the pre-paint script in `ThemeScript.tsx` apply the chosen mode everywhere, with no per-route exceptions. Chart colours live in `theme.charts` in `theme.config.ts` (a categorical palette and tone colours for light and dark), so re-skinning the theme re-skins the charts too.

## What is not themeable yet

- The radius scale stops at `xl`; `2xl` to `4xl` alias it.
- The Logo has a fixed 24 x 24 box, stroke width and wordmark styling.
- Destructive buttons hover by opacity; there is no `danger-hover` token.
- Badge borders use the tone colour at 40% opacity.
- The example ticket's cadence and step distance, and the glow's drift, blur and size, are written in `src/app/globals.css` and `src/components/ui/GlowBackdrop.tsx`.
- The `scroll-mt-20` anchor offset on the landing sections should equal the header height (`--l-header-height`) but is written by hand.
- The landing icon tiles have a fixed size.

## Passing className to a primitive

`cx` merges Tailwind conflicts (tailwind-merge, configured in `src/lib/cx.ts`), so a `className` you pass to a primitive that builds its classes with `cx` overrides that primitive's conflicting utility: `<Card className="p-0">` drops `p-card`, and `hidden sm:inline-flex` replaces `inline-flex` on the theme toggle. Variants stay independent (`hidden` and `sm:block` both survive).

Still fine where they exist: the `Card flush` prop, and wrapper elements such as the `hidden sm:block` wrapper around the landing nav's theme toggle.

Caveat: the merge only knows Tailwind's defaults plus the keys the config registers. Font sizes, spacing, shadow, container and radius keys are derived from `theme.config.ts` automatically. A brand-new utility family added to `globals.css` `@theme inline` is not, and must be registered in `src/lib/cx.ts`, otherwise it can be mis-merged (for example a custom text size mistaken for a text color and dropped).

import type { CSSProperties } from 'react';
import { cx } from '../../lib/cx';

/*
 * The hero's "event horizon": a lensed accretion disc sitting on the top edge of the demo card.
 *
 * Everything is one inline SVG in a 1200 x 420 user space whose BOTTOM EDGE (y = 420) is the horizon,
 * i.e. the top edge of the card. The look comes from stacking the same dome outline five times at
 * different scales, gradients and blurs so the colour runs white -> pink -> magenta -> violet -> blue
 * outward, with a photon ring and a dark disc punched into the middle.
 *
 * Colours are theme variables only (--hz-*, see theme.horizon); the CSS animates transform/opacity only.
 */

const CX = 600; // centre of the hole
const HORIZON = 420; // bottom edge of the viewBox = top edge of the card
const RY = 398; // centre of the photon rings and the disc: low, so they are cut by the horizon
const R_OUT = 88; // outer photon ring
const R_IN = 64; // inner photon ring
const R_DISC = 56; // the dark disc

/**
 * The lensed dome: a bell whose flanks flatten into the horizon, wider than it is tall (the reference's
 * disc is seen almost edge-on). Peak sits 160 units above the horizon; the open path is what carries the
 * bright band, the closed one fills the body behind it.
 */
const DOME_OPEN =
  'M 232 420 C 352 418 424 392 478 330 C 522 280 552 260 600 260 C 648 260 680 280 724 330 C 780 392 862 416 1010 420';
const DOME = `${DOME_OPEN} Z`;

/** Long, thin tapered flares running along the horizon, longer on the right (the reference is asymmetric). */
const FLARE_WIDE =
  'M 118 420 C 320 418 450 404 600 402 C 790 400 920 410 1132 420 Z';
const FLARE_THIN =
  'M 238 420 C 396 419 500 413 600 412 C 736 411 856 415 1032 420 Z';

/**
 * The bloom stack, outermost (widest, bluest, blurriest) first. `sx`/`sy` scale the dome about the
 * centre of the horizon, `blur` is the feGaussianBlur id suffix, `grad` the gradient id.
 */
const BLOOM = [
  { key: 'g4', grad: 'hzG4', blur: 'hzB46', sx: 1.85, sy: 1.75, o: 0.7, dx: 18 },
  { key: 'g3', grad: 'hzG3', blur: 'hzB28', sx: 1.4, sy: 1.38, o: 0.75, dx: 10 },
  { key: 'g2', grad: 'hzG2', blur: 'hzB14', sx: 1.08, sy: 1.08, o: 0.85, dx: 3 },
] as const;

/**
 * The bright band along the dome outline, widest/coldest first. This is what makes the effect read as a
 * lensed disc rather than a blob: a violet halo stroke, a magenta one, a pink one, then a white-hot core.
 */
const BAND = [
  { key: 'b1', w: 104, grad: 'hzBand3', blur: 'hzB28', o: 0.6 },
  { key: 'b2', w: 62, grad: 'hzBand2', blur: 'hzB14', o: 0.8 },
  { key: 'b3', w: 32, grad: 'hzBand1', blur: 'hzB10', o: 0.9 },
  { key: 'b4', w: 20, grad: 'hzBandCore', blur: 'hzB10', o: 1 },
  { key: 'b4b', w: 9, grad: 'hzBandCore', blur: 'hzB5', o: 1 },
  { key: 'b5', w: 5, grad: 'hzBandCore', blur: 'hzB2', o: 1 },
] as const;

/**
 * Faint concentric arcs above the horizon, with a node dot on each. They must stay barely-there: at 1600 px
 * the widest one passes behind the lead paragraph, so it is thinner and fainter than a hairline stroke.
 */
const ARCS = [
  { r: 214, o: 0.11, w: 0.8, node: -58 },
  { r: 306, o: 0.08, w: 0.7, node: 34 },
  { r: 402, o: 0.05, w: 0.6, node: -22 },
] as const;

/** Stars: denser and brighter near the centre. x, y, radius, opacity. */
const STARS: readonly (readonly [number, number, number, number])[] = [
  [232, 214, 1.4, 0.35], [286, 132, 1, 0.3], [318, 268, 1.6, 0.45], [366, 86, 1.2, 0.28],
  [392, 196, 1, 0.4], [428, 292, 1.8, 0.55], [452, 128, 1.4, 0.42], [486, 232, 1.1, 0.5],
  [508, 62, 1, 0.26], [524, 176, 1.6, 0.6], [556, 108, 1.2, 0.5], [578, 30, 1.4, 0.34],
  [592, 148, 1, 0.55], [614, 74, 1.6, 0.52], [640, 24, 1.2, 0.36], [664, 122, 1.5, 0.58],
  [688, 62, 1, 0.42], [704, 184, 1.7, 0.6], [736, 104, 1.2, 0.48], [760, 42, 1.4, 0.3],
  [782, 228, 1.6, 0.52], [812, 146, 1.1, 0.4], [846, 74, 1.3, 0.3], [868, 262, 1.5, 0.44],
  [902, 178, 1, 0.34], [934, 106, 1.4, 0.3], [962, 288, 1.2, 0.3], [998, 208, 1, 0.26],
  [186, 312, 1.2, 0.26], [148, 186, 1, 0.22], [1042, 132, 1.3, 0.24], [1080, 252, 1, 0.2],
  [274, 348, 1.4, 0.3], [960, 358, 1.2, 0.28], [408, 368, 1, 0.22], [796, 344, 1.5, 0.34],
  [640, 300, 1, 0.5], [546, 260, 1.2, 0.46], [346, 168, 1, 0.3], [884, 138, 1, 0.3],
];

const domeTransform = (sx: number, sy: number, dx = 0) =>
  `translate(${CX + dx} ${HORIZON}) scale(${sx} ${sy}) translate(${-CX} ${-HORIZON})`;

const v = (name: string) => `var(--hz-${name})`;

/** A gradient stop whose colour is a theme variable (stop-color only takes a var() through style). */
function Stop({ offset, color, opacity }: { offset: number | string; color: string; opacity: number }) {
  return <stop offset={offset} stopOpacity={opacity} style={{ stopColor: v(color) } as CSSProperties} />;
}

/**
 * Decorative lensed disc that rises from the top edge of its `relative` parent.
 * Colours come from theme.horizon (--hz-*); only transform and opacity are animated (see globals.css).
 */
export function EventHorizon({ className }: { className?: string }) {
  return (
    <div aria-hidden="true" className={cx('hz', className)}>
      {/* The only transform that moves: an HTML wrapper, so the blurred SVG is rasterised once and the
          browser only re-composites it. Scaling the filtered <g> elements instead costs ~2x the frame time. */}
      <div className="hz-breathe">
      <svg className="hz-svg" viewBox={`0 0 1200 ${HORIZON}`} preserveAspectRatio="xMidYMax meet" focusable="false">
        {/*
         * NOTE: these ids are global to the document. EventHorizon is rendered exactly once (in Hero);
         * if it is ever rendered twice the ids must be prefixed per instance, or the second copy will
         * reference the first one's gradients and filters.
         */}
        <defs>
          {/* Blurs. The region is generous so the widest bloom is not clipped by its own filter box. */}
          {[2, 5, 10, 14, 28, 46].map((s) => (
            <filter key={s} id={`hzB${s}`} x="-75%" y="-75%" width="250%" height="250%" colorInterpolationFilters="sRGB">
              <feGaussianBlur stdDeviation={s} />
            </filter>
          ))}
          {/*
           * The same blurs for the FLAT shapes along the horizon (the flares and the line). Their bounding
           * box is only a few user units tall, so a percentage filter region (-75% / 250% of the bbox) is
           * a few units too and hard-clips the blur into a straight seam above the card. These use an
           * explicit user-space region instead, with room for 3 x stdDeviation on every side.
           */}
          {[2, 5, 10, 28].map((s) => (
            <filter key={s} id={`hzF${s}`} filterUnits="userSpaceOnUse" x={-40} y={260} width={1280} height={300} colorInterpolationFilters="sRGB">
              <feGaussianBlur stdDeviation={s} />
            </filter>
          ))}

          {/* The hot interior under the arch: pink near the throat, cooling outward to magenta/violet. */}
          <radialGradient id="hzG1" gradientUnits="userSpaceOnUse" cx={CX} cy={RY} r={280}>
            <Stop offset="0" color="glow-1" opacity={0.55} />
            <Stop offset="0.26" color="glow-1" opacity={0.6} />
            <Stop offset="0.5" color="glow-2" opacity={0.7} />
            <Stop offset="0.8" color="glow-2" opacity={0.5} />
            <Stop offset="1" color="glow-3" opacity={0} />
          </radialGradient>

          {/* Band gradients: brightest at the peak of the arc, cooling toward the tails on the horizon. */}
          <linearGradient id="hzBandCore" gradientUnits="userSpaceOnUse" x1={CX} y1={252} x2={CX} y2={HORIZON}>
            <Stop offset="0" color="core" opacity={1} />
            <Stop offset="0.4" color="core" opacity={0.98} />
            <Stop offset="0.78" color="glow-1" opacity={0.92} />
            <Stop offset="1" color="glow-1" opacity={0.65} />
          </linearGradient>
          <linearGradient id="hzBand1" gradientUnits="userSpaceOnUse" x1={CX} y1={252} x2={CX} y2={HORIZON}>
            <Stop offset="0" color="glow-1" opacity={0.95} />
            <Stop offset="0.5" color="glow-1" opacity={0.9} />
            <Stop offset="1" color="glow-2" opacity={0.8} />
          </linearGradient>
          <linearGradient id="hzBand2" gradientUnits="userSpaceOnUse" x1={CX} y1={252} x2={CX} y2={HORIZON}>
            <Stop offset="0" color="glow-2" opacity={0.9} />
            <Stop offset="0.55" color="glow-2" opacity={0.85} />
            <Stop offset="1" color="glow-3" opacity={0.7} />
          </linearGradient>
          <linearGradient id="hzBand3" gradientUnits="userSpaceOnUse" x1={CX} y1={252} x2={CX} y2={HORIZON}>
            <Stop offset="0" color="glow-2" opacity={0.6} />
            <Stop offset="0.6" color="glow-3" opacity={0.7} />
            <Stop offset="1" color="glow-3" opacity={0.5} />
          </linearGradient>
          <radialGradient id="hzG2" gradientUnits="userSpaceOnUse" cx={CX} cy={400} r={300}>
            <Stop offset="0" color="glow-2" opacity={0.85} />
            <Stop offset="0.45" color="glow-2" opacity={0.52} />
            <Stop offset="0.78" color="glow-3" opacity={0.3} />
            <Stop offset="1" color="glow-3" opacity={0} />
          </radialGradient>
          <radialGradient id="hzG3" gradientUnits="userSpaceOnUse" cx={CX} cy={HORIZON} r={372}>
            <Stop offset="0" color="glow-3" opacity={0.78} />
            <Stop offset="0.42" color="glow-3" opacity={0.46} />
            <Stop offset="0.76" color="glow-4" opacity={0.26} />
            <Stop offset="1" color="glow-4" opacity={0} />
          </radialGradient>
          <radialGradient id="hzG4" gradientUnits="userSpaceOnUse" cx={CX} cy={HORIZON} r={520}>
            <Stop offset="0" color="glow-4" opacity={0.62} />
            <Stop offset="0.5" color="glow-4" opacity={0.34} />
            <Stop offset="1" color="glow-4" opacity={0} />
          </radialGradient>

          {/* The soft dome of light behind everything, wider than the bloom stack. */}
          <radialGradient id="hzHalo" gradientUnits="userSpaceOnUse" cx={CX} cy={HORIZON} r={560}>
            <Stop offset="0" color="halo" opacity={0.85} />
            <Stop offset="0.55" color="halo" opacity={0.28} />
            <Stop offset="1" color="halo" opacity={0} />
          </radialGradient>

          {/*
           * The horizon streak. Three gradients for three passes: a wide violet-magenta wash under the
           * whole run, a saturated body, and the hot hairline that lands on the card's top edge. All three
           * fade to nothing at the ends and carry the tail further right than left (asymmetry).
           */}
          <linearGradient id="hzFlare" gradientUnits="userSpaceOnUse" x1={118} y1={0} x2={1132} y2={0}>
            <Stop offset="0" color="flare" opacity={0} />
            <Stop offset="0.18" color="glow-2" opacity={0.5} />
            <Stop offset="0.42" color="flare" opacity={0.95} />
            <Stop offset="0.52" color="glow-1" opacity={1} />
            <Stop offset="0.66" color="flare" opacity={0.85} />
            <Stop offset="0.86" color="glow-2" opacity={0.35} />
            <Stop offset="1" color="flare" opacity={0} />
          </linearGradient>
          <linearGradient id="hzLineGlow" gradientUnits="userSpaceOnUse" x1={130} y1={0} x2={1140} y2={0}>
            <Stop offset="0" color="glow-2" opacity={0} />
            <Stop offset="0.16" color="glow-2" opacity={0.4} />
            <Stop offset="0.36" color="flare" opacity={0.85} />
            <Stop offset="0.5" color="glow-1" opacity={0.95} />
            <Stop offset="0.68" color="flare" opacity={0.8} />
            <Stop offset="0.88" color="glow-2" opacity={0.3} />
            <Stop offset="1" color="glow-2" opacity={0} />
          </linearGradient>
          <linearGradient id="hzLine" gradientUnits="userSpaceOnUse" x1={168} y1={0} x2={1108} y2={0}>
            <Stop offset="0" color="line" opacity={0} />
            <Stop offset="0.14" color="glow-2" opacity={0.45} />
            <Stop offset="0.3" color="flare" opacity={0.85} />
            <Stop offset="0.46" color="line" opacity={1} />
            <Stop offset="0.58" color="line" opacity={1} />
            <Stop offset="0.72" color="flare" opacity={0.85} />
            <Stop offset="0.9" color="glow-2" opacity={0.4} />
            <Stop offset="1" color="line" opacity={0} />
          </linearGradient>

          {/* Photon rings: brightest at the top of the arc, fading toward the horizon. */}
          <linearGradient id="hzRing" gradientUnits="userSpaceOnUse" x1={CX} y1={RY - R_OUT} x2={CX} y2={RY + R_OUT}>
            <Stop offset="0" color="core" opacity={1} />
            <Stop offset="0.45" color="ring" opacity={1} />
            <Stop offset="0.82" color="glow-1" opacity={0.95} />
            <Stop offset="1" color="glow-1" opacity={0.75} />
          </linearGradient>
          <linearGradient id="hzRingAlt" gradientUnits="userSpaceOnUse" x1={CX} y1={RY - R_IN} x2={CX} y2={RY + R_IN}>
            <Stop offset="0" color="core" opacity={0.95} />
            <Stop offset="0.45" color="ring" opacity={0.9} />
            <Stop offset="1" color="ring-alt" opacity={0.7} />
          </linearGradient>

          {/*
           * The disc. The focal point sits low inside the circle, so the iso-lines curve around the
           * bottom rim: violet where it sinks into the horizon, void at the top. A straight-looking
           * seam here is the giveaway of a flat gradient, hence fx/fy rather than an offset centre.
           */}
          <radialGradient id="hzDisc" gradientUnits="userSpaceOnUse" cx={CX} cy={RY} r={R_DISC} fx={CX} fy={RY + 34}>
            <Stop offset="0" color="disc-glow" opacity={0.92} />
            <Stop offset="0.22" color="disc-glow" opacity={0.66} />
            <Stop offset="0.46" color="disc-glow" opacity={0.3} />
            <Stop offset="0.66" color="disc" opacity={0.88} />
            <Stop offset="0.84" color="disc" opacity={0.98} />
            <Stop offset="1" color="void" opacity={1} />
          </radialGradient>

          {/*
           * Tapers the band so its tails thin out along the horizon instead of ending as a blunt tube.
           * mask-type: alpha, so the mask reads only stop-opacity and the taper is identical in both
           * modes even though --hz-core is a different colour in each.
           */}
          <linearGradient id="hzTaperGrad" gradientUnits="userSpaceOnUse" x1={140} y1={0} x2={1080} y2={0}>
            <Stop offset="0" color="core" opacity={0} />
            <Stop offset="0.2" color="core" opacity={0.55} />
            <Stop offset="0.42" color="core" opacity={1} />
            <Stop offset="0.66" color="core" opacity={1} />
            <Stop offset="0.86" color="core" opacity={0.5} />
            <Stop offset="1" color="core" opacity={0} />
          </linearGradient>
          <mask id="hzTaper" maskUnits="userSpaceOnUse" style={{ maskType: 'alpha' } as CSSProperties} x={0} y={-120} width={1200} height={560}>
            <rect x={0} y={-120} width={1200} height={560} fill="url(#hzTaperGrad)" />
          </mask>
        </defs>

        {/* 1. Soft halo dome */}
        <g className="hz-halo">
          <ellipse cx={CX + 16} cy={HORIZON} rx={540} ry={300} fill="url(#hzHalo)" filter="url(#hzB46)" />
        </g>

        {/* 2. Outer bloom copies (breathe together) */}
        <g className="hz-bloom">
          {BLOOM.map((b) => (
            <path
              key={b.key}
              d={DOME}
              fill={`url(#${b.grad})`}
              filter={`url(#${b.blur})`}
              opacity={b.o}
              transform={domeTransform(b.sx, b.sy, b.dx)}
            />
          ))}
        </g>

        {/* 3. The body inside the band, then the band itself: the bright lensed edge of the disc */}
        <g className="hz-dome">
          <path d={DOME} fill="url(#hzG1)" filter="url(#hzB14)" opacity={0.95} transform={domeTransform(0.94, 0.92)} />
          <g mask="url(#hzTaper)">
            {BAND.map((b) => (
              <path
                key={b.key}
                d={DOME_OPEN}
                fill="none"
                stroke={`url(#${b.grad})`}
                strokeWidth={b.w}
                strokeLinecap="round"
                strokeLinejoin="round"
                filter={`url(#${b.blur})`}
                opacity={b.o}
              />
            ))}
          </g>
        </g>

        {/* 4. Photon rings */}
        <g className="hz-rings">
          <circle cx={CX} cy={RY} r={R_OUT} fill="none" stroke="url(#hzRing)" strokeWidth={26} opacity={0.45} filter="url(#hzB14)" />
          <circle cx={CX} cy={RY} r={R_OUT} fill="none" stroke="url(#hzRing)" strokeWidth={9} opacity={1} filter="url(#hzB5)" />
          <circle cx={CX} cy={RY} r={R_OUT} fill="none" strokeWidth={2.5} opacity={1} filter="url(#hzB2)" style={{ stroke: v('core') } as CSSProperties} />
          <circle cx={CX} cy={RY} r={R_IN} fill="none" stroke="url(#hzRingAlt)" strokeWidth={14} opacity={0.35} filter="url(#hzB10)" />
          <circle cx={CX} cy={RY} r={R_IN} fill="none" stroke="url(#hzRingAlt)" strokeWidth={4} opacity={1} filter="url(#hzB2)" />
        </g>

        {/* 5. Flares along the horizon (behind the disc, so its silhouette stays clean) */}
        <g className="hz-flares">
          <path d={FLARE_WIDE} fill="url(#hzFlare)" filter="url(#hzF28)" opacity={0.9} transform="translate(0 -14) scale(1 1.035)" />
          <path d={FLARE_WIDE} fill="url(#hzFlare)" filter="url(#hzF10)" opacity={0.95} />
          <path d={FLARE_THIN} fill="url(#hzFlare)" filter="url(#hzF5)" opacity={1} />
        </g>

        {/* 6. The dark disc, clipped by the circle itself (never a box), then the horizon streak */}
        <circle className="hz-disc" cx={CX} cy={RY} r={R_DISC} fill="url(#hzDisc)" />
        {/* The streak: a soft coloured bed, then the hot hairline that lands on the card's top edge. */}
        <g className="hz-line">
          <rect x={130} y={HORIZON - 13} width={1010} height={14} fill="url(#hzLineGlow)" filter="url(#hzF10)" opacity={0.85} />
          <rect x={168} y={HORIZON - 6} width={940} height={7} fill="url(#hzLine)" filter="url(#hzF5)" opacity={0.9} />
          {/* Unblurred on purpose: this hairline is the base of the composition, and a blur of 2 over a
              2 px rect dilutes it to nothing against the bloom (invisible in light mode especially). */}
          <rect x={168} y={HORIZON - 4} width={940} height={2} fill="url(#hzLine)" />
        </g>

        {/* 7. Faint arcs with node dots */}
        <g className="hz-arcs">
          {ARCS.map((a) => (
            <g key={a.r} opacity={a.o}>
              <circle cx={CX} cy={HORIZON} r={a.r} fill="none" strokeWidth={a.w} style={{ stroke: v('star') } as CSSProperties} />
              <circle cx={CX + a.node} cy={HORIZON - Math.sqrt(Math.max(a.r * a.r - a.node * a.node, 0))} r={2.5} fill="none" strokeWidth={a.w} style={{ stroke: v('star') } as CSSProperties} />
            </g>
          ))}
        </g>
      </svg>
      </div>

      {/*
       * The moving layers live in their own small, filter-free SVGs on top. An opacity animation on a
       * group inside the big blurred SVG makes the browser re-run every feGaussianBlur each frame
       * (measured: +11 ms per frame); these overlays cost nothing.
       */}
      <svg className="hz-svg hz-overlay hz-shimmer" viewBox={`0 0 1200 ${HORIZON}`} preserveAspectRatio="xMidYMax meet" focusable="false">
        <circle cx={CX} cy={RY} r={R_OUT} fill="none" strokeWidth={2.5} style={{ stroke: v('core') } as CSSProperties} />
        <circle cx={CX} cy={RY} r={R_IN} fill="none" strokeWidth={3} style={{ stroke: v('ring') } as CSSProperties} />
      </svg>

      <svg className="hz-svg hz-overlay hz-stars" viewBox={`0 0 1200 ${HORIZON}`} preserveAspectRatio="xMidYMax meet" focusable="false">
        {STARS.map(([x, y, r, o]) => (
          <circle key={`${x}-${y}`} cx={x} cy={y} r={r} opacity={o} style={{ fill: v('star') } as CSSProperties} />
        ))}
      </svg>
    </div>
  );
}

/** Soft glow reflected onto the panel below the horizon. The parent must be `relative`. */
export function EventHorizonReflection({ className }: { className?: string }) {
  return (
    <div aria-hidden="true" className={cx('hz-reflect', className)}>
      <span className="hz-reflect-core" />
      <span className="hz-reflect-ring" />
    </div>
  );
}

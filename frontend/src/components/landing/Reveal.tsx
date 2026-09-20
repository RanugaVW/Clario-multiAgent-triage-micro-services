'use client';

import { motion } from 'framer-motion';
import type { ComponentProps } from 'react';
import { duration, ease } from '../../theme/motion';
import { theme } from '../../theme/theme.config';

/**
 * Fades a block in and lifts it by the theme's reveal offset, once, when it first scrolls into view.
 * Under `prefers-reduced-motion` the surrounding <LandingMotion> drops the movement and keeps only the fade.
 */
export function Reveal({
  delay = 0,
  ...rest
}: Omit<
  ComponentProps<typeof motion.div>,
  'initial' | 'animate' | 'whileInView' | 'viewport' | 'transition' | 'variants' | 'exit' | 'style'
> & { delay?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: theme.motion.revealOffset }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '0px 0px -80px 0px' }}
      transition={{ duration: duration.slow, ease: ease.out, delay }}
      {...rest}
      // The server HTML carries inline opacity:0 from `initial`. This hook lets the page's <noscript> stylesheet force
      // reveals visible when JavaScript is off. It comes after {...rest} so a caller can never remove it.
      data-reveal=""
    />
  );
}

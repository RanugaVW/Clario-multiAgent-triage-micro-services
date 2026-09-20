'use client';

import { MotionConfig } from 'framer-motion';
import type { ReactNode } from 'react';

// Client wrapper so the server-rendered page can set the reduced-motion policy for every <Reveal> below it.
export function LandingMotion({ children }: { children: ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}

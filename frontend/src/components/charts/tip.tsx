'use client';

import { useCallback, useState, type ReactNode } from 'react';

// A small tooltip for the hand-drawn charts (share bar, heatmap). It follows the pointer on hover and anchors to the mark
// on keyboard focus, so the reader gets the same details either way. Tooltips enhance and never gate: every value shown
// here is also in the chart's table view.

export type TipState = { x: number; y: number; content: ReactNode } | null;

export function useTip() {
  const [tip, setTip] = useState<TipState>(null);
  const show = useCallback((container: HTMLElement | null, clientX: number, clientY: number, content: ReactNode) => {
    if (!container) return;
    const box = container.getBoundingClientRect();
    setTip({ x: clientX - box.left, y: clientY - box.top, content });
  }, []);
  /** Anchors above the centre of the focused/hovered element - used for keyboard focus. */
  const showAtElement = useCallback((container: HTMLElement | null, el: Element, content: ReactNode) => {
    if (!container) return;
    const box = container.getBoundingClientRect();
    const r = el.getBoundingClientRect();
    setTip({ x: r.left - box.left + r.width / 2, y: r.top - box.top, content });
  }, []);
  const hide = useCallback(() => setTip(null), []);
  return { tip, show, showAtElement, hide };
}

/** Rendered inside a `position: relative` container. */
export function TipLayer({ tip }: { tip: TipState }) {
  if (!tip) return null;
  return (
    <div
      role="tooltip"
      className="pointer-events-none absolute z-20 -translate-x-1/2 -translate-y-full bg-surface-raised border border-border text-fg shadow-raised rounded-lg px-3 py-2 text-caption"
      style={{ left: tip.x, top: tip.y - 10, whiteSpace: 'nowrap' }}
    >
      {tip.content}
    </div>
  );
}

/** Values lead, labels follow: the number is the high-contrast element, the name is secondary. */
export function TipRow({ swatch, label, value }: { swatch?: string; label: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      {swatch && <span aria-hidden="true" className="inline-block h-0.5 w-3 rounded-full" style={{ background: swatch }} />}
      <span className="font-semibold text-fg">{value}</span>
      <span>{label}</span>
    </div>
  );
}

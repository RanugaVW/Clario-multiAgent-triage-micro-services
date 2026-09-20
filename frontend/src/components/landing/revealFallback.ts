// Injected inside <noscript> in the root layout head so visitors without JavaScript see the content:
// Reveal renders inline opacity:0 in the server HTML, and an author !important rule beats framer's
// non-important inline styles. A failed hydration WITH JavaScript on is not covered by this.
export const REVEAL_FALLBACK_CSS = '[data-reveal]{opacity:1!important;transform:none!important}';

// TEMPORARY. Routes that have been redesigned onto the theme tokens and are therefore safe in light mode.
// Every other route is forced to dark so pages that still use hard-coded dark colors never render in light.
// Each redesign phase adds its routes here; Phase 6 deletes this file and the gate.
export const MIGRATED_ROUTES: readonly string[] = ['/', '/design'];

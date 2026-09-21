import { THEME_STORAGE_KEY } from './mode';

/**
 * Runs before first paint and sets data-theme, so there is no flash of the wrong theme. The logic mirrors
 * resolveMode() in mode.ts; ThemeScript.test.ts runs this exact string and fails if the two ever disagree.
 */
export function buildThemeScript(storageKey: string = THEME_STORAGE_KEY): string {
  return (
    '(function(){var d=document.documentElement,pref;try{' +
    // Only the read is guarded: blocked storage means "no stored preference" (as in ThemeProvider), not dark.
    `var raw=null;try{raw=localStorage.getItem(${JSON.stringify(storageKey)})}catch(e){}` +
    "pref=raw==='light'||raw==='dark'?raw:'system';" +
    "var sys=matchMedia('(prefers-color-scheme: dark)').matches;" +
    "d.setAttribute('data-theme',pref==='system'?(sys?'dark':'light'):pref);" +
    // pref is hoisted: if matchMedia is unavailable, a stored light/dark preference is still honoured; else dark.
    "}catch(e){d.setAttribute('data-theme',pref==='light'||pref==='dark'?pref:'dark');}})();"
  );
}

export function ThemeScript() {
  return <script dangerouslySetInnerHTML={{ __html: buildThemeScript() }} />;
}

import { themeToCss } from './css';
import { theme } from './theme.config';

// Server component. Rendered inside <head> so the variables exist before first paint.
export function ThemeStyle() {
  return <style id="theme-vars" dangerouslySetInnerHTML={{ __html: themeToCss(theme) }} />;
}

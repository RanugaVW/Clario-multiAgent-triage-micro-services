// Shared timestamp formatting for the ticket rows on the admin and user dashboards.
// Every helper tolerates null/undefined/garbage so a half-written row never blanks the page.

function toDate(value: string | number | null | undefined): Date | null {
  if (value == null || value === '') return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** "01 Sep 2026" */
export function formatDate(value: string | null | undefined): string {
  const d = toDate(value);
  if (!d) return '—';
  return d.toLocaleDateString([], { day: '2-digit', month: 'short', year: 'numeric' });
}

/** "14:32" */
export function formatTime(value: string | null | undefined): string {
  const d = toDate(value);
  if (!d) return '—';
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

/** "01 Sep 2026 · 14:32:07" */
export function formatDateTime(value: string | null | undefined): string {
  const d = toDate(value);
  if (!d) return '—';
  return `${formatDate(value)} · ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`;
}

/** "3d ago" / "4h ago" / "12m ago" / "just now" */
export function formatRelative(value: string | null | undefined): string {
  const d = toDate(value);
  if (!d) return '—';
  const seconds = Math.floor((Date.now() - d.getTime()) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return formatDate(value);
}

/** Elapsed time between two timestamps, e.g. "2d 4h", "18m 3s", "940ms". */
export function formatElapsed(
  from: string | null | undefined,
  to: string | null | undefined
): string {
  const start = toDate(from);
  const end = toDate(to);
  if (!start || !end) return '—';
  return formatDuration(end.getTime() - start.getTime());
}

/** Milliseconds as a compact human duration. */
export function formatDuration(ms: number | null | undefined): string {
  if (ms == null || Number.isNaN(ms)) return '—';
  const abs = Math.max(0, Math.round(ms));
  if (abs < 1000) return `${abs}ms`;
  const totalSeconds = Math.floor(abs / 1000);
  const seconds = totalSeconds % 60;
  const totalMinutes = Math.floor(totalSeconds / 60);
  const minutes = totalMinutes % 60;
  const totalHours = Math.floor(totalMinutes / 60);
  const hours = totalHours % 24;
  const days = Math.floor(totalHours / 24);

  if (days > 0) return `${days}d ${hours}h`;
  if (totalHours > 0) return `${hours}h ${minutes}m`;
  if (totalMinutes > 0) return `${minutes}m ${seconds}s`;
  return `${(abs / 1000).toFixed(2)}s`;
}

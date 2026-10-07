import { cx } from '../../lib/cx';
import { formatTime, formatDateTime } from '../../lib/datetime';
import type { ThreadMessage } from '../../lib/ticketThread';

/** One chat bubble: the viewer's own messages sit on the right in brand colour. */
export function MessageBubble({
  message,
  mine,
  authorLabel,
  onRetry,
}: {
  message: ThreadMessage;
  mine: boolean;
  authorLabel: string;
  onRetry?: () => void;
}) {
  return (
    <li className={cx('flex flex-col gap-1', mine ? 'items-end' : 'items-start')}>
      <div
        className={cx(
          'max-w-[85%] whitespace-pre-wrap break-words rounded-2xl px-4 py-2.5 text-app leading-relaxed',
          mine ? 'rounded-br-sm bg-brand text-brand-fg' : 'rounded-bl-sm border border-border bg-surface-raised text-fg',
          message.state !== 'sent' && 'opacity-70'
        )}
      >
        {message.body}
      </div>
      <div className="flex items-center gap-2 px-1 text-caption text-fg-muted">
        <span>{authorLabel}</span>
        <span aria-hidden="true">·</span>
        {message.state === 'sending' && <span>Sending…</span>}
        {message.state === 'sent' && (
          <time dateTime={message.created_at} title={formatDateTime(message.created_at)}>
            {formatTime(message.created_at)}
          </time>
        )}
        {message.state === 'failed' && (
          <span className="text-danger">
            Not sent.{' '}
            <button type="button" onClick={onRetry} className="font-medium underline underline-offset-2 hover:text-fg">
              Retry
            </button>
          </span>
        )}
      </div>
    </li>
  );
}

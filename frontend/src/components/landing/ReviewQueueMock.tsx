import { cx } from '../../lib/cx';
import { Badge } from '../ui/Badge';
import { buttonClass } from '../ui/Button';
import { Card } from '../ui/Card';
import { review } from './content';

const { mock } = review;

// A picture of the review queue, not a working one: hidden from assistive tech and free of focusable elements.
// The text version of this information is the list beside it.
export function ReviewQueueMock() {
  return (
    <Card raised aria-hidden="true" className="overflow-hidden p-0">
      <div className="flex items-center justify-between border-b border-border px-5 py-3">
        <span className="text-small text-fg-muted">{mock.label}</span>
        <span className="text-small text-fg">{mock.queueTitle}</span>
      </div>

      <ul className="divide-y divide-border">
        {mock.rows.map((row) => (
          <li key={row.subject} className={cx('flex items-center justify-between gap-3 px-5 py-3', row.selected && 'bg-canvas')}>
            <span className="text-app text-fg">{row.subject}</span>
            <span className="flex shrink-0 items-center gap-2">
              <Badge>{row.tag}</Badge>
              <Badge tone="warning">{mock.status}</Badge>
            </span>
          </li>
        ))}
      </ul>

      <div className="border-t border-border px-5 py-4">
        <p className="text-small text-fg-muted">{mock.draftLabel}</p>
        <p className="mt-1 text-app text-fg">{mock.draft}</p>
        <div className="mt-4 flex justify-end gap-2">
          {mock.actions.map((action, i) => (
            <span key={action} className={buttonClass({ variant: i === mock.actions.length - 1 ? 'primary' : 'secondary', size: 'sm' })}>
              {action}
            </span>
          ))}
        </div>
      </div>
    </Card>
  );
}

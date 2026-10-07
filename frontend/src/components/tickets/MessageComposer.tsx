'use client';

import { useState, type KeyboardEvent } from 'react';
import { Button } from '../ui/Button';
import { Textarea } from '../ui/Input';
import { MAX_MESSAGE_LENGTH } from '../../lib/ticketThread';

/** Enter sends, Shift+Enter starts a new line. Staff can also send and close in one step. */
export function MessageComposer({
  onSend,
  canResolve = false,
  placeholder,
}: {
  onSend: (body: string, options: { markResolved?: boolean }) => void;
  canResolve?: boolean;
  placeholder: string;
}) {
  const [draft, setDraft] = useState('');
  const trimmed = draft.trim();
  const tooLong = trimmed.length > MAX_MESSAGE_LENGTH;
  const canSend = trimmed.length > 0 && !tooLong;

  const submit = (markResolved = false) => {
    if (!canSend) return;
    onSend(trimmed, { markResolved });
    setDraft('');
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // isComposing: don't send halfway through an IME composition.
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="space-y-2">
      <Textarea
        className="min-h-0 resize-none"
        rows={2}
        aria-label="Write a reply"
        placeholder={placeholder}
        value={draft}
        invalid={tooLong}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={onKeyDown}
      />
      <div className="flex items-center justify-between gap-2">
        <span className={tooLong ? 'text-caption text-danger' : 'text-caption text-fg-muted'}>
          {tooLong ? `${trimmed.length}/${MAX_MESSAGE_LENGTH} characters` : 'Enter to send · Shift+Enter for a new line'}
        </span>
        <div className="flex gap-2">
          {canResolve && (
            <Button variant="secondary" size="sm" onClick={() => submit(true)} disabled={!canSend}>
              Send &amp; resolve
            </Button>
          )}
          <Button size="sm" onClick={() => submit()} disabled={!canSend}>
            Send
          </Button>
        </div>
      </div>
    </div>
  );
}

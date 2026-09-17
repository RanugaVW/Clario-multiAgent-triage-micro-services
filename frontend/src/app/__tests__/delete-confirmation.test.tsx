import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { useState } from 'react';
import { UserTicketRow } from '../dashboard/page';
import { ConfirmDialog } from '../../components/ui';

// UR-006: deleting a ticket used to call the browser's native confirm()/
// alert(), which can't be styled, isn't reliably announced by screen
// readers, and blocks the entire page. It now opens the app's own
// ConfirmDialog and only performs the delete after an explicit click on its
// confirm button. This wrapper mirrors exactly how Dashboard wires
// UserTicketRow's onDelete to a ConfirmDialog (see src/app/dashboard/page.tsx),
// without needing to mount the whole page and its data-fetching effects.
function DeleteFlowHarness({ onConfirmedDelete }: { onConfirmedDelete: (id: string) => void }) {
  const [pendingId, setPendingId] = useState<string | null>(null);
  const ticket = {
    id: 'ticket-abc-123',
    raw_text: 'My login is broken',
    status: 'received',
    created_at: new Date().toISOString(),
    image_storage_path: null,
    ticket_classifications: [],
    resolutions: [],
  };

  return (
    <>
      <UserTicketRow
        ticket={ticket as unknown as Parameters<typeof UserTicketRow>[0]['ticket']}
        onDelete={(id) => setPendingId(id)}
        userId="user-1"
      />
      <ConfirmDialog
        open={pendingId !== null}
        title="Delete this ticket?"
        message="This will immediately stop processing and cannot be undone."
        confirmLabel="Delete ticket"
        onConfirm={() => {
          if (pendingId) onConfirmedDelete(pendingId);
          setPendingId(null);
        }}
        onCancel={() => setPendingId(null)}
      />
    </>
  );
}

describe('Ticket delete confirmation (UR-006)', () => {
  it('does not delete immediately - it opens a confirmation dialog first', async () => {
    const user = userEvent.setup();
    const onConfirmedDelete = vi.fn();
    render(<DeleteFlowHarness onConfirmedDelete={onConfirmedDelete} />);

    await user.click(screen.getByRole('button')); // the row's only button: delete

    expect(screen.getByText('Delete this ticket?')).toBeInTheDocument();
    expect(onConfirmedDelete).not.toHaveBeenCalled();
  });

  it('deletes only after the dialog is explicitly confirmed', async () => {
    const user = userEvent.setup();
    const onConfirmedDelete = vi.fn();
    render(<DeleteFlowHarness onConfirmedDelete={onConfirmedDelete} />);

    await user.click(screen.getByRole('button'));
    await user.click(screen.getByRole('button', { name: 'Delete ticket' }));

    expect(onConfirmedDelete).toHaveBeenCalledWith('ticket-abc-123');
    expect(screen.queryByText('Delete this ticket?')).not.toBeInTheDocument();
  });

  it('cancels without deleting when Cancel is clicked', async () => {
    const user = userEvent.setup();
    const onConfirmedDelete = vi.fn();
    render(<DeleteFlowHarness onConfirmedDelete={onConfirmedDelete} />);

    await user.click(screen.getByRole('button'));
    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(onConfirmedDelete).not.toHaveBeenCalled();
    expect(screen.queryByText('Delete this ticket?')).not.toBeInTheDocument();
  });
});

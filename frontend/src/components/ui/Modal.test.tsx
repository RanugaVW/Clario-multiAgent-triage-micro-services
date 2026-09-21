import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ConfirmDialog, Modal } from './Modal';

describe('Modal', () => {
  it('renders nothing when closed', () => {
    render(
      <Modal open={false} onClose={() => {}} title="Title">
        Body
      </Modal>
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('is a modal dialog labelled by its title', () => {
    render(
      <Modal open onClose={() => {}} title="Invite a teammate">
        Body
      </Modal>
    );
    const dialog = screen.getByRole('dialog', { name: 'Invite a teammate' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
  });

  it('scrolls inside the viewport instead of overflowing it on short screens', () => {
    render(
      <Modal open onClose={() => {}} title="Invite a teammate">
        body
      </Modal>
    );
    const tokens = screen.getByRole('dialog').className.split(' ');
    expect(tokens).toContain('max-h-[calc(100dvh-2rem)]');
    expect(tokens).toContain('overflow-y-auto');
  });

  it('moves focus into the dialog when it opens', () => {
    render(
      <Modal open onClose={() => {}} title="T">
        <button>Inside</button>
      </Modal>
    );
    expect(screen.getByRole('dialog')).toHaveFocus();
  });

  it('closes on Escape, on the close button and on a backdrop click', async () => {
    const onClose = vi.fn();
    const { container } = render(
      <Modal open onClose={onClose} title="T">
        Body
      </Modal>
    );
    await userEvent.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(1);

    await userEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(onClose).toHaveBeenCalledTimes(2);

    await userEvent.click(container.firstElementChild as HTMLElement);
    expect(onClose).toHaveBeenCalledTimes(3);
  });

  it('does not close when the panel itself is clicked', async () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="T">
        <p>Body</p>
      </Modal>
    );
    await userEvent.click(screen.getByText('Body'));
    expect(onClose).not.toHaveBeenCalled();
  });

  it('keeps Tab focus inside the dialog', async () => {
    render(
      <>
        <button>Outside</button>
        <Modal open onClose={() => {}} title="T">
          <button>First</button>
          <button>Last</button>
        </Modal>
      </>
    );
    // close button, First, Last are the focusable items inside
    await userEvent.tab();
    await userEvent.tab();
    await userEvent.tab();
    expect(screen.getByRole('button', { name: 'Last' })).toHaveFocus();
    await userEvent.tab();
    expect(screen.getByRole('button', { name: 'Close' })).toHaveFocus();
  });

  it('still closes on Escape when focus has left the dialog for the body', async () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="T">
        <button>Inside</button>
      </Modal>
    );
    (document.activeElement as HTMLElement).blur();
    expect(document.body).toHaveFocus();
    await userEvent.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('pulls focus back into the dialog when Tab is pressed from the body', async () => {
    render(
      <>
        <button>Outside</button>
        <Modal open onClose={() => {}} title="T">
          <button>First</button>
        </Modal>
      </>
    );
    (document.activeElement as HTMLElement).blur();
    expect(document.body).toHaveFocus();
    await userEvent.tab();
    expect(screen.getByRole('button', { name: 'Close' })).toHaveFocus();
  });

  it('pulls focus to the last item on Shift+Tab from the body', async () => {
    render(
      <>
        <button>Outside</button>
        <Modal open onClose={() => {}} title="T">
          <button>First</button>
          <button>Last</button>
        </Modal>
      </>
    );
    (document.activeElement as HTMLElement).blur();
    await userEvent.tab({ shift: true });
    expect(screen.getByRole('button', { name: 'Last' })).toHaveFocus();
  });

  it('wraps Tab from the last button even when a hidden input trails it', async () => {
    render(
      <>
        <button>Outside</button>
        <Modal open onClose={() => {}} title="T">
          <button>Last</button>
          <input type="hidden" name="csrf" />
        </Modal>
      </>
    );
    screen.getByRole('button', { name: 'Last' }).focus();
    await userEvent.tab();
    expect(screen.getByRole('button', { name: 'Close' })).toHaveFocus();
  });

  it('returns focus to the element that opened it', () => {
    const opener = document.createElement('button');
    document.body.appendChild(opener);
    opener.focus();
    const { rerender } = render(
      <Modal open onClose={() => {}} title="T">
        Body
      </Modal>
    );
    rerender(
      <Modal open={false} onClose={() => {}} title="T">
        Body
      </Modal>
    );
    expect(opener).toHaveFocus();
    opener.remove();
  });
});

describe('ConfirmDialog', () => {
  const setup = (over: Partial<React.ComponentProps<typeof ConfirmDialog>> = {}) => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
      <ConfirmDialog
        open
        title="Delete ticket"
        message="This cannot be undone."
        confirmLabel="Delete"
        onConfirm={onConfirm}
        onCancel={onCancel}
        {...over}
      />
    );
    return { onConfirm, onCancel };
  };

  it('shows the title and message', () => {
    setup();
    expect(screen.getByRole('dialog', { name: 'Delete ticket' })).toBeInTheDocument();
    expect(screen.getByText('This cannot be undone.')).toBeInTheDocument();
  });

  it('confirms with the destructive button and cancels with the other', async () => {
    const { onConfirm, onCancel } = setup();
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('cancels on Escape', async () => {
    const { onCancel } = setup();
    await userEvent.keyboard('{Escape}');
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});

describe('Modal description and initial focus', () => {
  it('links aria-describedby to the described element', () => {
    render(
      <Modal open onClose={() => {}} title="T" describedBy="why">
        <p id="why">Because.</p>
      </Modal>
    );
    expect(screen.getByRole('dialog', { name: 'T' })).toHaveAttribute('aria-describedby', 'why');
  });

  it('omits aria-describedby when none is given', () => {
    render(
      <Modal open onClose={() => {}} title="T">
        <p>Body</p>
      </Modal>
    );
    expect(screen.getByRole('dialog', { name: 'T' })).not.toHaveAttribute('aria-describedby');
  });

  it('focuses the [data-autofocus] element instead of the panel', () => {
    render(
      <Modal open onClose={() => {}} title="T">
        <button>First</button>
        <button data-autofocus>Second</button>
      </Modal>
    );
    expect(screen.getByRole('button', { name: 'Second' })).toHaveFocus();
  });
});

describe('ConfirmDialog accessibility', () => {
  it('describes the dialog by its message and starts on Cancel, not the destructive button', () => {
    render(
      <ConfirmDialog open title="Delete?" message="This cannot be undone." confirmLabel="Delete" onConfirm={() => {}} onCancel={() => {}} />
    );
    const dialog = screen.getByRole('dialog', { name: 'Delete?' });
    expect(dialog).toHaveAccessibleDescription('This cannot be undone.');
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus();
  });
});

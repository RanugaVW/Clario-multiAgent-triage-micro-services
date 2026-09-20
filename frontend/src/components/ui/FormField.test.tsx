import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { FormField } from './FormField';
import { Input } from './Input';

const field = (props: { hint?: string; error?: string | null } = {}) =>
  render(<FormField label="Email address" {...props}>{(f) => <Input {...f} />}</FormField>);

describe('FormField', () => {
  it('associates the visible label with the input', () => {
    field();
    expect(screen.getByLabelText('Email address')).toBeInTheDocument();
  });

  it('describes the input by its hint', () => {
    field({ hint: 'We never share it.' });
    const input = screen.getByLabelText('Email address');
    expect(input).toHaveAccessibleDescription('We never share it.');
    expect(input).not.toHaveAttribute('aria-invalid');
  });

  it('shows an error as an alert, marks the input invalid and describes it by the error', () => {
    field({ hint: 'We never share it.', error: 'Enter a valid email address.' });
    const input = screen.getByLabelText('Email address');
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a valid email address.');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAccessibleDescription('We never share it. Enter a valid email address.');
  });

  it('renders no alert and no description when there is no hint or error', () => {
    field();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Email address')).not.toHaveAttribute('aria-describedby');
  });

  it('gives every field its own id', () => {
    render(
      <>
        <FormField label="One">{(f) => <Input {...f} />}</FormField>
        <FormField label="Two">{(f) => <Input {...f} />}</FormField>
      </>
    );
    expect(screen.getByLabelText('One').id).not.toBe(screen.getByLabelText('Two').id);
  });
});

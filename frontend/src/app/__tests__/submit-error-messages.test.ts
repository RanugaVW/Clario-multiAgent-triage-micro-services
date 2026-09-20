import { describe, it, expect } from 'vitest';
import { describeSubmitFailure } from '../dashboard/page';

// UR-002: error messages must give corrective information, not a generic
// string that discards whatever the backend actually reported (FR-005's
// validation details, REL-002's "try again shortly", etc).
describe('describeSubmitFailure', () => {
  it('surfaces the backend error message when the response has one', async () => {
    const res = { status: 400, json: async () => ({ error: 'Gateway timeout' }) } as unknown as Response;
    expect(await describeSubmitFailure(res)).toBe('Gateway timeout');
  });

  it('appends validation details when present (FR-005)', async () => {
    const res = {
      status: 400,
      json: async () => ({ error: 'Validation failed', details: 'rawText: rawText is required and cannot be blank' }),
    } as unknown as Response;
    expect(await describeSubmitFailure(res)).toBe(
      'Validation failed: rawText: rawText is required and cannot be blank'
    );
  });

  it('falls back to a friendly 5xx message when the body has no usable error field', async () => {
    const res = { status: 503, json: async () => ({}) } as unknown as Response;
    expect(await describeSubmitFailure(res)).toMatch(/temporarily unavailable/i);
  });

  it('falls back to a friendly 4xx message when the response body is not JSON', async () => {
    const res = { status: 400, json: async () => { throw new Error('not json'); } } as unknown as Response;
    expect(await describeSubmitFailure(res)).toMatch(/check your details/i);
  });

  // SUP-005: the reference lets support find the matching server log lines.
  it('appends the support reference to the backend message', async () => {
    const res = {
      status: 503,
      json: async () => ({ error: 'Ticket service is temporarily unavailable. Please try again shortly.', reference: 'req-42' }),
    } as unknown as Response;
    expect(await describeSubmitFailure(res)).toBe(
      'Ticket service is temporarily unavailable. Please try again shortly. (reference: req-42)'
    );
  });

  it('keeps the reference even when the body has no error field (framework-generated 4xx)', async () => {
    const res = {
      status: 400,
      json: async () => ({ title: 'Bad Request', status: 400, detail: 'Failed to read request', reference: 'req-43' }),
    } as unknown as Response;
    expect(await describeSubmitFailure(res)).toBe(
      "We couldn't submit your ticket. Please check your details and try again. (reference: req-43)"
    );
  });

  it('never invents a reference when the backend sent none', async () => {
    const res = { status: 400, json: async () => ({ error: 'Gateway timeout' }) } as unknown as Response;
    expect(await describeSubmitFailure(res)).toBe('Gateway timeout');
  });

  it('ignores a non-string reference rather than printing it', async () => {
    const res = { status: 400, json: async () => ({ error: 'Nope', reference: { evil: true } }) } as unknown as Response;
    expect(await describeSubmitFailure(res)).toBe('Nope');
  });
});

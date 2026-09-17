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
});

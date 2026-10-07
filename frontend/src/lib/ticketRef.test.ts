import { describe, it, expect } from 'vitest';
import { formatTicketRef, parseTicketRef, matchesTicketQuery } from './ticketRef';

const ID = '5bc09ad7-1f2e-4c3b-9a8d-7e6f5a4b3c2d';

describe('formatTicketRef', () => {
  it('pads small numbers to four digits', () => {
    expect(formatTicketRef({ id: ID, ticket_number: 42 })).toBe('TKT-0042');
  });

  it('lets larger numbers grow past four digits', () => {
    expect(formatTicketRef({ id: ID, ticket_number: 123456 })).toBe('TKT-123456');
  });

  it('falls back to the uppercased first UUID block, without the TKT prefix, when there is no number', () => {
    expect(formatTicketRef({ id: ID })).toBe('5BC09AD7');
    expect(formatTicketRef({ id: ID, ticket_number: null })).toBe('5BC09AD7');
  });
});

describe('parseTicketRef', () => {
  it.each(['TKT-0042', 'tkt-42', 'TKT 42', 'TKT42', '#42', '42', '  0042 '])('reads %j as 42', (input) => {
    expect(parseTicketRef(input)).toBe(42);
  });

  it.each(['', 'TKT-', 'abc', '5bc09ad7', '42a'])('rejects %j', (input) => {
    expect(parseTicketRef(input)).toBeNull();
  });
});

describe('matchesTicketQuery', () => {
  const ticket = { id: ID, ticket_number: 42 };

  it('matches the reference however it is typed', () => {
    expect(matchesTicketQuery(ticket, 'TKT-0042')).toBe(true);
    expect(matchesTicketQuery(ticket, '#42')).toBe(true);
    expect(matchesTicketQuery(ticket, '42')).toBe(true);
  });

  it('still matches part of the UUID, for anyone pasting the copied ID', () => {
    expect(matchesTicketQuery(ticket, '5bc09ad7')).toBe(true);
    expect(matchesTicketQuery(ticket, ID.toUpperCase())).toBe(true);
  });

  it("doesn't match on short digits that only appear inside another ticket's UUID", () => {
    expect(matchesTicketQuery({ id: '00000000-0000-4042-8000-000000000000', ticket_number: 7 }, '42')).toBe(false);
  });

  it('does not match a different number', () => {
    expect(matchesTicketQuery(ticket, 'TKT-0043')).toBe(false);
  });

  it('matches everything on an empty query', () => {
    expect(matchesTicketQuery(ticket, '  ')).toBe(true);
  });
});

import { describe, it, expect } from 'vitest';
import ExcelJS from 'exceljs';
import { PDFDocument } from 'pdf-lib';
import { inflateSync } from 'node:zlib';
import { buildSections, toCsv, toXlsx, toPdf, neutraliseFormula, parseFormat, renderReport, type ReportBundle } from './reportExport';
import { aiPerformance, comparePeriods, parseDateRange, ticketAnalytics, type ReportTicket } from './reports';

const none = { from: null, to: null };
const tickets: ReportTicket[] = [
  {
    id: 'a', status: 'escalated', created_at: '2026-09-01T10:00:00Z',
    ticket_classifications: [{ category: 'Billing & Invoicing, "Refunds"', priority: 'High', sentiment: 'Frustrated' }],
    resolutions: [{ escalated: true, total_latency_ms: 2500, total_llm_calls: 6, total_reflection_count: 1, escalation_reasons: ['=HYPERLINK("http://evil","x")', 'Low, relevance'] }],
    ticket_validations: [{ passed: false, failure_type: 'policy', judge_ran: true }],
    response_evaluations: [{ overall_score: 4 }],
  },
  { id: 'b', status: 'resolved', created_at: '2026-09-03T10:00:00Z', ticket_classifications: [{ category: 'Café ☕', priority: 'Low', sentiment: 'Neutral' }], resolutions: [{ escalated: false, total_latency_ms: 1500 }] },
];
const bundle = (over: Partial<ReportBundle> = {}): ReportBundle => ({
  range: '2026-09-01 to 2026-09-30',
  analytics: ticketAnalytics(tickets, none),
  ai: aiPerformance(tickets, none),
  comparison: null,
  ...over,
});

describe('buildSections - the single definition of report content', () => {
  it('contains the figures an administrator sees on screen', () => {
    const s = Object.fromEntries(buildSections(bundle()).map((x) => [x.title, x]));
    expect(s['Ticket summary'].rows).toContainEqual(['Tickets received', 2]);
    expect(s['Ticket summary'].rows).toContainEqual(['Resolution rate (%)', 50]);
    expect(s['Daily volume'].rows).toEqual([['2026-09-01', 1], ['2026-09-02', 0], ['2026-09-03', 1]]);
    expect(s['AI performance'].rows).toContainEqual(['Median processing time (ms)', 1500]);
    expect(s['AI performance'].rows).toContainEqual(['Escalation rate (%)', 50]);
    expect(s['Validation failure types'].rows).toEqual([['policy', 1]]);
  });
  it('keeps empty measurements empty (null) rather than 0', () => {
    const s = buildSections(bundle({ analytics: ticketAnalytics([], none), ai: aiPerformance([], none) }));
    const ai = s.find((x) => x.title === 'AI performance')!;
    expect(ai.rows.find((r) => r[0] === 'Median processing time (ms)')![1]).toBeNull();
    expect(s.find((x) => x.title === 'Ticket summary')!.rows.find((r) => r[0] === 'Resolution rate (%)')![1]).toBeNull();
  });
});

describe('chart data is exported too - the file matches the dashboard', () => {
  const week = parseDateRange('2026-09-01', '2026-09-07');
  if (!week.ok) throw new Error('range');
  const withComparison = bundle({
    analytics: ticketAnalytics(tickets, week.range),
    ai: aiPerformance(tickets, week.range),
    comparison: comparePeriods(tickets, week.range),
  });
  const sections = Object.fromEntries(buildSections(withComparison).map((x) => [x.title, x]));

  it('includes the previous-period comparison, row for row, when there is one', () => {
    const c = Object.values(sections).find((x) => x.title.startsWith('Comparison with the previous period'))!;
    expect(c.title).toContain('2026-08-25 to 2026-08-31');
    expect(c.columns).toEqual(['Metric', 'This period', 'Previous period', 'Change']);
    expect(c.rows[0].slice(0, 3)).toEqual(['Tickets received (change in %)', 2, 0]);
    expect(c.rows[2][0]).toContain('Resolution rate');
  });
  it('omits the comparison for an open-ended range', () => {
    expect(buildSections(bundle()).some((x) => x.title.startsWith('Comparison'))).toBe(false);
  });
  it('exports the arrivals heatmap as weekday and hour totals that add up to the ticket count', () => {
    const total = withComparison.analytics.total;
    const weekdayTotal = sections['Arrivals by weekday (UTC)'].rows.reduce((s, r) => s + (r[1] as number), 0);
    const hourTotal = sections['Arrivals by hour (UTC)'].rows.reduce((s, r) => s + (r[1] as number), 0);
    expect(sections['Arrivals by weekday (UTC)'].rows).toHaveLength(7);
    expect(sections['Arrivals by hour (UTC)'].rows).toHaveLength(24);
    expect([weekdayTotal, hourTotal]).toEqual([total, total]);
  });
  it('exports the processing-time distribution', () => {
    const rows = sections['Processing time distribution'].rows;
    expect(rows.map((r) => r[0])).toEqual(['<1 s', '1–2 s', '2–5 s', '5–10 s', '10–30 s', '30 s+']);
    expect(rows.reduce((s, r) => s + (r[1] as number), 0)).toBe(withComparison.ai.latencyBuckets.reduce((s, b) => s + b.count, 0));
  });
});

describe('CSV', () => {
  const csv = toCsv(buildSections(bundle()));

  it('starts with a BOM, uses CRLF, and quotes commas and quotes per RFC 4180', () => {
    expect(csv.charCodeAt(0)).toBe(0xfeff);
    expect(csv).toContain('\r\n');
    expect(csv).toContain('"""Refunds"""'); // embedded quotes are doubled and the cell wrapped
    expect(csv).toContain('"Low, relevance"');
  });
  it('round-trips: every section title, column and cell of the model is present', () => {
    for (const s of buildSections(bundle())) {
      expect(csv).toContain(s.title);
      for (const row of s.rows) expect(csv).toContain(String(row[0]).replace(/"/g, '""'));
    }
    expect(csv).toContain('Café ☕');
  });
  it('neutralises spreadsheet formulas in text but never touches real numbers', () => {
    expect(csv).toContain(`'=HYPERLINK`);
    expect(csv).not.toMatch(/(^|,|\r\n)=HYPERLINK/);
    expect(toCsv([{ title: 't', columns: ['n'], rows: [[-5]] }])).toContain('\r\n-5\r\n');
  });
  it.each(['=1+1', '+1', '-1', '@SUM(A1)', '\tx', '\rx'])('neutralises %j', (v) => {
    expect(neutraliseFormula(v)).toBe(`'${v}`);
  });
  it('leaves ordinary text alone', () => expect(neutraliseFormula('Refunds')).toBe('Refunds'));
});

describe('Excel', () => {
  it('produces a real workbook with one sheet per section and matching cell values', async () => {
    const sections = buildSections(bundle());
    const wb = new ExcelJS.Workbook();
    await wb.xlsx.load((await toXlsx(sections)) as unknown as ArrayBuffer);

    expect(wb.worksheets.map((w) => w.name)).toEqual(sections.map((s) => s.title));
    const summary = wb.getWorksheet('Ticket summary')!;
    expect(summary.getRow(1).values).toEqual([undefined, 'Metric', 'Value']);
    expect(summary.getRow(3).values).toEqual([undefined, 'Tickets received', 2]);
    expect(typeof summary.getRow(3).getCell(2).value).toBe('number'); // numbers stay numeric for pivoting
  });
  it('stores a formula-looking string as text, not as a formula', async () => {
    const wb = new ExcelJS.Workbook();
    await wb.xlsx.load((await toXlsx(buildSections(bundle()))) as unknown as ArrayBuffer);
    const cell = wb.getWorksheet('Escalation reasons')!.getRow(2).getCell(1);
    expect(cell.type).toBe(ExcelJS.ValueType.String);
    expect(cell.formula).toBeUndefined();
    expect(String(cell.value)).toContain('=HYPERLINK');
  });
  it('keeps sheet names within Excel limits', async () => {
    const wb = new ExcelJS.Workbook();
    await wb.xlsx.load((await toXlsx([{ title: 'A/very:long*title[with]bad?chars and more than thirty-one characters', columns: ['c'], rows: [] }])) as unknown as ArrayBuffer);
    const name = wb.worksheets[0].name;
    expect(name.length).toBeLessThanOrEqual(31);
    expect(name).not.toMatch(/[\\/?*[\]:]/);
  });
});

describe('PDF', () => {
  it('is a valid multi-section PDF', async () => {
    const bytes = await toPdf(buildSections(bundle()), { title: 'Clario report', range: 'r' });
    expect(new TextDecoder().decode(bytes.slice(0, 5))).toBe('%PDF-');
    const doc = await PDFDocument.load(bytes);
    expect(doc.getPageCount()).toBeGreaterThanOrEqual(1);
    expect(doc.getTitle()).toBe('Clario report');
  });
  it('does not throw on characters the built-in font cannot encode (emoji, CJK)', async () => {
    const s = [{ title: 'Unicode ☕ 你好', columns: ['a'], rows: [['Café ☕ 你好 🎉']] as (string | number | null)[][] }];
    const bytes = await toPdf(s, { title: 't', range: 'r' });
    expect((await PDFDocument.load(bytes)).getPageCount()).toBe(1);
  });
  it('paginates rather than running off the page', async () => {
    const many = [{ title: 'Big', columns: ['d', 'n'], rows: Array.from({ length: 200 }, (_, i) => [`row ${i}`, i]) as (string | number | null)[][] }];
    const doc = await PDFDocument.load(await toPdf(many, { title: 't', range: 'r' }));
    expect(doc.getPageCount()).toBeGreaterThan(2);
  });
  it('contains the report text (uncompressed content streams are searchable)', async () => {
    const bytes = await toPdf(buildSections(bundle()), { title: 'Clario report', range: '2026-09-01 to 2026-09-30' });
    const raw = Buffer.from(bytes);
    // pdf-lib deflates page streams: inflate every stream and look for the text operators' payload.
    const streams: string[] = [];
    let i = 0;
    while ((i = raw.indexOf('stream\n', i)) !== -1) {
      const start = i + 7;
      const end = raw.indexOf('endstream', start);
      try { streams.push(inflateSync(raw.subarray(start, end)).toString('latin1')); } catch { /* font / non-flate stream */ }
      i = end;
    }
    // pdf-lib writes text as hex-encoded WinAnsi strings: `<5469...> Tj`. Decode them back to text.
    const text = streams
      .join('\n')
      .match(/<([0-9A-Fa-f]+)>\s*Tj/g)!
      .map((m) => Buffer.from(m.replace(/[<>\sTj]/g, ''), 'hex').toString('latin1'));
    expect(text).toContain('Tickets received');
    expect(text).toContain('Period: 2026-09-01 to 2026-09-30');
  });
});

describe('format handling', () => {
  it('parseFormat accepts only the three supported formats', () => {
    expect(parseFormat('csv')).toBe('csv');
    expect(parseFormat('xlsx')).toBe('xlsx');
    expect(parseFormat('pdf')).toBe('pdf');
    for (const bad of [null, '', 'CSV', 'docx', 'toString', '__proto__', 'constructor']) expect(parseFormat(bad)).toBeNull();
  });
  it('renderReport dispatches each format to matching bytes', async () => {
    expect([...(await renderReport(bundle(), 'csv')).slice(0, 3)]).toEqual([0xef, 0xbb, 0xbf]); // UTF-8 BOM
    expect(new TextDecoder().decode((await renderReport(bundle(), 'pdf')).slice(0, 4))).toBe('%PDF');
    expect(new TextDecoder().decode((await renderReport(bundle(), 'xlsx')).slice(0, 2))).toBe('PK'); // zip container
  });
});

// FR-053: turns a generated report into CSV / Excel / PDF. Every format is rendered from the same
// neutral table model, so "exported reports preserve report contents" is a property of one function
// (buildSections) rather than three renderers that could drift apart.
import ExcelJS from 'exceljs';
import { PDFDocument, StandardFonts, rgb, type PDFFont, type PDFPage } from 'pdf-lib';
import type { AiPerformance, CountRow, TicketAnalytics } from './reports';

export type Cell = string | number | null;
export type Section = { title: string; columns: string[]; rows: Cell[][] };
export type ReportBundle = { range: string; analytics: TicketAnalytics; ai: AiPerformance };

export { EXPORT_FORMATS, parseFormat, type ExportFormat } from './reportFormats';
import type { ExportFormat } from './reportFormats';

const round = (x: number | null, digits = 1): number | null => (x === null ? null : Number(x.toFixed(digits)));
const rows = (r: CountRow[]): Cell[][] => r.map((x) => [x.label, x.count]);

/** The single source of truth for what an exported report contains. */
export function buildSections(b: ReportBundle): Section[] {
  const a = b.analytics;
  const ai = b.ai;
  const p = ai.processingTime;
  const sections: Section[] = [
    {
      title: 'Ticket summary',
      columns: ['Metric', 'Value'],
      rows: [
        ['Period', b.range],
        ['Tickets received', a.total],
        ['Resolved', a.resolved],
        ['Awaiting human review', a.awaitingHuman],
        ['In progress', a.inProgress],
        ['Resolution rate (%)', a.resolutionRate === null ? null : round(a.resolutionRate * 100)],
      ],
    },
    { title: 'Tickets by category', columns: ['Category', 'Tickets'], rows: rows(a.byCategory) },
    { title: 'Tickets by priority', columns: ['Priority', 'Tickets'], rows: rows(a.byPriority) },
    { title: 'Tickets by sentiment', columns: ['Sentiment', 'Tickets'], rows: rows(a.bySentiment) },
    { title: 'Tickets by status', columns: ['Status', 'Tickets'], rows: rows(a.byStatus) },
    { title: 'Daily volume', columns: ['Date', 'Tickets'], rows: a.dailyVolume.map((d) => [d.date, d.count]) },
    {
      title: 'AI performance',
      columns: ['Metric', 'Value'],
      rows: [
        ['Tickets processed by the AI pipeline', ai.ticketsProcessed],
        ['Processing time samples', p?.samples ?? null],
        ['Median processing time (ms)', round(p?.medianMs ?? null, 0)],
        ['Mean processing time (ms)', round(p?.meanMs ?? null, 0)],
        ['95th percentile processing time (ms)', round(p?.p95Ms ?? null, 0)],
        ['Maximum processing time (ms)', round(p?.maxMs ?? null, 0)],
        ['Average LLM calls per resolution', round(ai.avgLlmCalls, 2)],
        ['Average reflection rounds per resolution', round(ai.avgReflections, 2)],
        ['Escalated tickets', ai.escalation.escalated],
        ['Escalation rate (%)', ai.escalation.rate === null ? null : round(ai.escalation.rate * 100)],
        ['Validations passed', ai.validation.passed],
        ['Validations failed', ai.validation.failed],
        ['Validation pass rate (%)', ai.validation.passRate === null ? null : round(ai.validation.passRate * 100)],
        ['Validations that ran the LLM judge', ai.validation.judged],
        ['Responses scored by the judge', ai.judgeScores.evaluated],
        ['Mean judge score (out of 5)', round(ai.judgeScores.meanOverall, 2)],
      ],
    },
    { title: 'Escalation reasons', columns: ['Reason', 'Tickets'], rows: rows(ai.escalation.reasons) },
    { title: 'Validation failure types', columns: ['Failure type', 'Validations'], rows: rows(ai.validation.failureTypes) },
    { title: 'Judge score distribution', columns: ['Score', 'Responses'], rows: rows(ai.judgeScores.distribution) },
  ];
  return sections;
}

// ------------------------------------------------------------------ CSV

/**
 * Text that starts with = + - @ (or a tab/CR) is executed as a formula by Excel/Sheets when a CSV is
 * opened. Category names and escalation reasons are model- or customer-influenced, so prefix such
 * strings with an apostrophe. Numbers are exempt: a real -5 must stay a number.
 */
export function neutraliseFormula(value: string): string {
  return /^[=+\-@\t\r]/.test(value) ? `'${value}` : value;
}

function csvCell(cell: Cell): string {
  if (cell === null) return '';
  const text = typeof cell === 'number' ? String(cell) : neutraliseFormula(cell);
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function toCsv(sections: Section[]): string {
  const lines: string[] = [];
  sections.forEach((s, i) => {
    if (i > 0) lines.push('');
    lines.push(csvCell(s.title));
    lines.push(s.columns.map(csvCell).join(','));
    for (const row of s.rows) lines.push(row.map(csvCell).join(','));
  });
  // BOM so Excel reads UTF-8 (accented category names) correctly; CRLF per RFC 4180.
  return '\uFEFF' + lines.join('\r\n') + '\r\n';
}

// ------------------------------------------------------------------ Excel

// Sheet names: max 31 chars, none of  \ / ? * [ ] :
const sheetName = (title: string) => title.replace(/[\\/?*[\]:]/g, ' ').slice(0, 31);

export async function toXlsx(sections: Section[]): Promise<Uint8Array> {
  const wb = new ExcelJS.Workbook();
  wb.creator = 'Clario';
  wb.created = new Date();
  for (const s of sections) {
    const ws = wb.addWorksheet(sheetName(s.title));
    const header = ws.addRow(s.columns);
    header.font = { bold: true };
    for (const row of s.rows) {
      // Strings are written as plain text (ExcelJS never evaluates them as formulas unless given { formula }),
      // so no apostrophe prefix is needed here and the cell content stays exactly the report's value.
      ws.addRow(row);
    }
    ws.columns.forEach((col, i) => {
      const longest = Math.max(s.columns[i].length, ...s.rows.map((r) => String(r[i] ?? '').length));
      col.width = Math.min(60, longest + 2);
    });
  }
  return new Uint8Array(await wb.xlsx.writeBuffer());
}

// ------------------------------------------------------------------ PDF

const A4: [number, number] = [595.28, 841.89];
const MARGIN = 48;

// pdf-lib's built-in fonts are WinAnsi only: any other character makes drawText throw. Replace what the
// font cannot encode rather than failing the whole export over one exotic category name.
function pdfSafe(text: string, font: PDFFont): string {
  let out = '';
  for (const ch of text.replace(/[\r\n\t]+/g, ' ')) {
    try {
      font.encodeText(ch);
      out += ch;
    } catch {
      out += '?';
    }
  }
  return out;
}

export async function toPdf(sections: Section[], meta: { title: string; range: string }): Promise<Uint8Array> {
  const doc = await PDFDocument.create();
  doc.setTitle(meta.title);
  doc.setCreator('Clario');
  const font = await doc.embedFont(StandardFonts.Helvetica);
  const bold = await doc.embedFont(StandardFonts.HelveticaBold);

  let page: PDFPage = doc.addPage(A4);
  let y = A4[1] - MARGIN;
  const ensure = (needed: number) => {
    if (y - needed < MARGIN) {
      page = doc.addPage(A4);
      y = A4[1] - MARGIN;
    }
  };
  const text = (s: string, x: number, size: number, f: PDFFont, color = rgb(0.1, 0.1, 0.1)) =>
    page.drawText(pdfSafe(s, f), { x, y, size, font: f, color });
  // Truncate to the column width (with "...") so long values never run off the page.
  const fit = (s: string, f: PDFFont, size: number, width: number) => {
    const full = pdfSafe(s, f);
    if (f.widthOfTextAtSize(full, size) <= width) return full;
    let t = full;
    while (t.length > 0 && f.widthOfTextAtSize(`${t}...`, size) > width) t = t.slice(0, -1);
    return `${t}...`;
  };

  text(meta.title, MARGIN, 20, bold);
  y -= 22;
  text(`Period: ${meta.range}`, MARGIN, 10, font, rgb(0.35, 0.35, 0.35));
  y -= 26;

  const usable = A4[0] - MARGIN * 2;
  for (const s of sections) {
    ensure(60);
    text(s.title, MARGIN, 13, bold);
    y -= 18;
    const colWidth = usable / s.columns.length;
    s.columns.forEach((c, i) => {
      page.drawText(fit(c, bold, 9, colWidth - 8), { x: MARGIN + i * colWidth, y, size: 9, font: bold, color: rgb(0.35, 0.35, 0.35) });
    });
    y -= 14;
    if (s.rows.length === 0) {
      text('No data for this period', MARGIN, 9, font, rgb(0.5, 0.5, 0.5));
      y -= 14;
    }
    for (const row of s.rows) {
      ensure(16);
      row.forEach((cell, i) => {
        page.drawText(fit(cell === null ? '—' : String(cell), font, 9, colWidth - 8), { x: MARGIN + i * colWidth, y, size: 9, font });
      });
      y -= 13;
    }
    y -= 14;
  }
  return doc.save();
}

// ------------------------------------------------------------------ entry point

export async function renderReport(bundle: ReportBundle, format: ExportFormat): Promise<Uint8Array> {
  const sections = buildSections(bundle);
  if (format === 'csv') return new TextEncoder().encode(toCsv(sections));
  if (format === 'xlsx') return toXlsx(sections);
  return toPdf(sections, { title: 'Clario report', range: bundle.range });
}

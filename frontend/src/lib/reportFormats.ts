// Kept apart from reportExport.ts on purpose: the Reports page needs the list of formats, and importing
// them from the renderer module would drag exceljs and pdf-lib into the browser bundle.
export type ExportFormat = 'csv' | 'xlsx' | 'pdf';

export const EXPORT_FORMATS: Record<ExportFormat, { mime: string; extension: string; label: string }> = {
  csv: { mime: 'text/csv; charset=utf-8', extension: 'csv', label: 'CSV' },
  xlsx: { mime: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', extension: 'xlsx', label: 'Excel' },
  pdf: { mime: 'application/pdf', extension: 'pdf', label: 'PDF' },
};

export function parseFormat(value: string | null): ExportFormat | null {
  return value !== null && Object.prototype.hasOwnProperty.call(EXPORT_FORMATS, value) ? (value as ExportFormat) : null;
}

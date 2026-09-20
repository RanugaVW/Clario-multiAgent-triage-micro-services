# FR-053 — Export Reports (SRS §3.1.14)

**Status before:** 🔴 Not implemented — no export code anywhere.
**Status after:** ✅ An administrator can download the report shown on the Reports page as **CSV, Excel (.xlsx) or PDF**.
**Database changes:** none. **New dependencies:** `exceljs`, `pdf-lib` (server-side only — verified absent from the browser bundle).

Acceptance criteria: *exported reports preserve report contents* · *file generation is logged* · Alternative flow A1: *user receives an error message*.

## What was built
- **`src/lib/reportExport.ts`** — `buildSections()` is the single definition of report content (ticket summary, by category/priority/sentiment/status, daily volume, AI performance,
  escalation reasons, validation failure types, judge score distribution). CSV, XLSX and PDF are all rendered from that one model, so contents cannot drift between formats.
  Empty measurements stay empty (`null`), never `0`.
  - **CSV:** RFC 4180 quoting, CRLF, UTF-8 BOM (so Excel reads accented names), and **spreadsheet-formula neutralisation** — text beginning `= + - @ \t \r` gets a leading `'`
    (category names and escalation reasons are model/customer influenced; a cell like `=HYPERLINK(...)` would otherwise execute when the file is opened). Real numbers are untouched.
  - **Excel:** one sheet per section, bold header, sized columns, numbers stay numeric, strings stored as text never as formulas, sheet names sanitised to Excel's limits.
  - **PDF:** A4, paginated, columns truncated with "..." rather than overflowing, characters the built-in font cannot encode replaced with `?` instead of failing the export.
- **`src/lib/reportFormats.ts`** — the format list, kept separate so the page does not pull the two heavy libraries into the browser.
- **`src/lib/reportService.ts`** — `generateReport()` shared by the on-screen report and the export, so a file always equals what was shown for the same range.
- **`GET /api/reports/export?format=csv|xlsx|pdf&from=&to=`** — admin only; 400 for unsupported format (allow-list, `__proto__` safe) or bad dates *before* any data is read;
  `Content-Disposition: attachment` with a filename built only from validated dates; `Cache-Control: no-store`.
- **Logging:** every attempt writes one structured line `{"event":"report.export","outcome":"success|failure|denied","userId","format","period","tickets","bytes","ms"}`;
  report contents are never logged. Failures return a generic message to the user (A1) — internals such as table names are logged, not shown.
- **UI:** CSV / Excel / PDF buttons on `/admin/reports`, exporting the **applied** period (not half-typed dates), disabled while one runs, error shown in an alert, retry possible.

## Tests
| File | Cases | Covers |
|---|---|---|
| `src/lib/reportExport.test.ts` | 21 | contents model vs on-screen figures, null preserved; CSV (BOM, CRLF, quoting, round-trip of every section/cell, formula neutralisation ×6 vectors, numbers untouched); Excel (**re-opened with ExcelJS**: sheets, cell values, numeric type, formula-looking text stays string, sheet-name limits); PDF (valid `%PDF`, reloads with pdf-lib, unencodable characters, pagination over 200 rows, **text extracted back out of the file** matches); format allow-list |
| `src/app/api/reports/export/route.test.ts` | 12 | 401, 403 ×2 (+denial logged), 400 ×4, CSV/XLSX/PDF responses with headers, success log (no contents), A1 failure → generic message + failure log |
| `src/app/__tests__/admin-reports.test.tsx` | +4 | buttons offered, download uses applied period + server filename + token, A1 error & retry, non-JSON error body |

**Mutation checks (reverted after each, all caught):** formula guard weakened to `=` only (5 failures); BOM removed (2 — initially the mutation did not apply because the BOM was an invisible literal in the source, so it was rewritten as an explicit `﻿` escape and re-checked);
a section's content dropped; `no-store` removed; success not logged; agent allowed to export; export using unapplied dates.

**Full verification:** `vitest` 31 files / **290 tests** · `eslint` 0 errors · `next build` OK (`/api/reports/export`) · `tsc` clean apart from the pre-existing `admin-ticket-attachment.test.tsx` error · no `exceljs`/`pdf-lib` in `.next/static` client chunks.

## Known limits
- **"Logged" means a structured server log line, not a database row.** A queryable audit table would need a Supabase table (not created — would need your approval).
- Exports are generated in memory; a very large range (hundreds of thousands of tickets) is capped by the loader's 200k-row limit and would be heavy — narrow the range.
- PDF uses the built-in Helvetica (Latin-1 only); non-Latin text becomes `?`. Embedding a Unicode font would fix it at the cost of file size.
- `npm audit` shows one **new moderate** advisory via `exceljs → uuid` (buffer bounds check when a caller supplies its own buffer — not a path used here). All other audit findings (next, postcss, nanoid, sharp) were already present.
- The report contains aggregate counts only — no ticket text or customer data — but is still admin-restricted and `no-store`.

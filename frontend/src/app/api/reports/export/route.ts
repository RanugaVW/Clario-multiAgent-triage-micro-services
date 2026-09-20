import { NextResponse } from 'next/server';
import { requireUser } from '../../../../lib/apiAuth';
import { createReportClient } from '../../../../lib/reportData';
import { generateReport } from '../../../../lib/reportService';
import { parseDateRange } from '../../../../lib/reports';
import { EXPORT_FORMATS, parseFormat } from '../../../../lib/reportFormats';
import { renderReport } from '../../../../lib/reportExport';

// FR-053: download the report as CSV, Excel or PDF. Admin only.
//
// "File generation is logged": every attempt - success or failure - writes one structured line
// (event, outcome, who, format, period, size, duration). Deliberately no report contents in the log.
function audit(fields: Record<string, unknown>, failed = false) {
  const line = JSON.stringify({ event: 'report.export', at: new Date().toISOString(), ...fields });
  (failed ? console.error : console.info)(line);
}

export async function GET(request: Request) {
  const user = await requireUser(request);
  if (!user) return NextResponse.json({ error: 'Authentication required' }, { status: 401 });
  if (user.role !== 'admin') {
    audit({ outcome: 'denied', userId: user.id, role: user.role }, true);
    return NextResponse.json({ error: 'Administrator access required' }, { status: 403 });
  }

  const { searchParams } = new URL(request.url);
  const format = parseFormat(searchParams.get('format'));
  if (!format) {
    return NextResponse.json({ error: 'format must be one of: csv, xlsx, pdf' }, { status: 400 });
  }
  const parsed = parseDateRange(searchParams.get('from'), searchParams.get('to'));
  if (!parsed.ok) return NextResponse.json({ error: parsed.error }, { status: 400 });

  const client = createReportClient();
  if (!client) return NextResponse.json({ error: 'SUPABASE_SERVICE_ROLE_KEY is not set on the server' }, { status: 500 });

  const started = Date.now();
  try {
    const bundle = await generateReport(client, parsed.range);
    const bytes = await renderReport(bundle, format);
    // Safe to embed: parseDateRange only lets YYYY-MM-DD through.
    const filename = `clario-report-${searchParams.get('from') || 'start'}_${searchParams.get('to') || 'today'}.${EXPORT_FORMATS[format].extension}`;
    audit({ outcome: 'success', userId: user.id, format, period: bundle.range, tickets: bundle.analytics.total, bytes: bytes.byteLength, ms: Date.now() - started });
    return new Response(bytes as BodyInit, {
      headers: {
        'Content-Type': EXPORT_FORMATS[format].mime,
        'Content-Disposition': `attachment; filename="${filename}"`,
        'Cache-Control': 'no-store', // customer ticket statistics must not sit in shared caches
      },
    });
  } catch (e) {
    // A1 - Export Failure: the caller gets an error message, and the failure is on record.
    audit({ outcome: 'failure', userId: user.id, format, error: e instanceof Error ? e.message : String(e), ms: Date.now() - started }, true);
    return NextResponse.json({ error: 'The report could not be generated. Please try again.' }, { status: 500 });
  }
}

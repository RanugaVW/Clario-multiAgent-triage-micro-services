import { NextResponse } from 'next/server';
import { requireUser } from '../../../lib/apiAuth';
import { createReportClient } from '../../../lib/reportData';
import { generateReport } from '../../../lib/reportService';
import { parseDateRange } from '../../../lib/reports';

// FR-051 / FR-052: ticket analytics and AI performance for a configurable date range. Admin only - the SRS actors are the
// System Administrator and AI Operations Engineer, and this app has a single `admin` role for both.
export async function GET(request: Request) {
  const user = await requireUser(request);
  if (!user) return NextResponse.json({ error: 'Authentication required' }, { status: 401 });
  if (user.role !== 'admin') return NextResponse.json({ error: 'Administrator access required' }, { status: 403 });

  const { searchParams } = new URL(request.url);
  const parsed = parseDateRange(searchParams.get('from'), searchParams.get('to'));
  if (!parsed.ok) return NextResponse.json({ error: parsed.error }, { status: 400 });

  const client = createReportClient();
  if (!client) return NextResponse.json({ error: 'SUPABASE_SERVICE_ROLE_KEY is not set on the server' }, { status: 500 });

  try {
    return NextResponse.json(await generateReport(client, parsed.range));
  } catch (e) {
    console.error('report generation failed', e);
    return NextResponse.json({ error: e instanceof Error ? e.message : 'Report generation failed' }, { status: 500 });
  }
}

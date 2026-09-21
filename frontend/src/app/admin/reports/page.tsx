'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Download, Loader2 } from 'lucide-react';
import { AdminShell } from '../AdminShell';
import { useAuth } from '../../../contexts/AuthContext';
import { supabase } from '../../../lib/supabase';
import { fetchJson } from '../../../lib/fetchJson';
import { EXPORT_FORMATS, type ExportFormat } from '../../../lib/reportFormats';
import type { AiPerformance, PeriodComparison, TicketAnalytics } from '../../../lib/reports';
import { ReportDashboard } from '../../../components/charts/ReportDashboard';

type AnalyticsResponse = { range: string; analytics: TicketAnalytics; ai: AiPerformance; comparison: PeriodComparison | null };


const today = () => new Date().toISOString().slice(0, 10);
const daysAgo = (n: number) => new Date(Date.now() - n * 24 * 3600_000).toISOString().slice(0, 10);

async function authHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function AdminReports() {
  const { user, role, loading, roleLoading } = useAuth();
  const router = useRouter();
  const ready = !loading && !roleLoading;
  const isAdmin = !!user && role === 'admin';

  const [from, setFrom] = useState(daysAgo(29));
  const [to, setTo] = useState(today());
  const [report, setReport] = useState<AnalyticsResponse | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // The period the report on screen was generated for. Exports use this, not whatever is half-typed in the inputs,
  // so a downloaded file always matches what the administrator is looking at.
  const [applied, setApplied] = useState({ from: daysAgo(29), to: today() });
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  useEffect(() => {
    if (ready && !isAdmin) router.push('/login');
  }, [ready, isAdmin, router]);

  const load = useCallback(async (f: string, t: string) => {
    try {
      const qs = new URLSearchParams();
      if (f) qs.set('from', f);
      if (t) qs.set('to', t);
      setReport(await fetchJson<AnalyticsResponse>(`/api/reports?${qs}`, { headers: await authHeaders() }));
      setApplied({ from: f, to: t });
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not generate the report');
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (isAdmin) queueMicrotask(() => load(from, to));
    // Only the initial load is automatic; later changes wait for "Apply" so a half-typed date never fires a request.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin, load]);

  const exportReport = async (format: ExportFormat) => {
    setExporting(format);
    setExportError(null);
    try {
      const qs = new URLSearchParams({ format });
      if (applied.from) qs.set('from', applied.from);
      if (applied.to) qs.set('to', applied.to);
      const res = await fetch(`/api/reports/export?${qs}`, { headers: await authHeaders() });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.error || `Export failed (${res.status})`);
      }
      const blob = await res.blob();
      const name = /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') ?? '')?.[1] ?? `clario-report.${EXPORT_FORMATS[format].extension}`;
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = name;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setExportError(e instanceof Error ? e.message : 'Export failed');
    } finally {
      setExporting(null);
    }
  };

  const apply = (f = from, t = to) => {
    setBusy(true);
    load(f, t);
  };

  const preset = (f: string, t: string) => {
    setFrom(f);
    setTo(t);
    apply(f, t);
  };

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-[#E8A33D]" />
      </div>
    );
  }

  const a = report?.analytics;
  const ai = report?.ai;
  const cmp = report?.comparison ?? null;
  const invalidRange = !!from && !!to && from > to;

  return (
    <AdminShell active="reports">
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-bold text-[#ECECEC]">Reports</h1>
        <p className="text-sm text-[#8A8F98]">Ticket analytics and AI performance for a chosen period</p>
      </header>

      {/* One filter row above everything it scopes: every figure and chart below is the same slice. */}
      <form
        onSubmit={(e) => { e.preventDefault(); if (!invalidRange) apply(); }}
        className="glass-panel rounded-[28px] p-6 flex flex-wrap items-end gap-4"
        aria-label="Report period"
      >
        <div>
          <label htmlFor="report-from" className="block text-xs font-medium text-[#8A8F98] mb-1">From</label>
          <input id="report-from" type="date" value={from} max={to || undefined} onChange={(e) => setFrom(e.target.value)} className="glass-input rounded-xl px-3 py-2 text-sm" />
        </div>
        <div>
          <label htmlFor="report-to" className="block text-xs font-medium text-[#8A8F98] mb-1">To</label>
          <input id="report-to" type="date" value={to} min={from || undefined} onChange={(e) => setTo(e.target.value)} className="glass-input rounded-xl px-3 py-2 text-sm" />
        </div>
        <button type="submit" disabled={busy || invalidRange} className="rounded-xl px-5 py-2 text-sm font-semibold bg-gradient-to-r from-[#E8A33D] to-[#F4B856] text-[#08090D] disabled:opacity-50">
          {busy ? 'Generating…' : 'Apply'}
        </button>
        <div className="flex flex-wrap gap-2 ml-auto" role="group" aria-label="Quick ranges">
          <button type="button" onClick={() => preset(daysAgo(6), today())} className="text-xs px-3 py-1.5 rounded-full bg-white/[0.06] text-[#8A8F98] hover:text-[#ECECEC]">Last 7 days</button>
          <button type="button" onClick={() => preset(daysAgo(29), today())} className="text-xs px-3 py-1.5 rounded-full bg-white/[0.06] text-[#8A8F98] hover:text-[#ECECEC]">Last 30 days</button>
          <button type="button" onClick={() => preset(daysAgo(89), today())} className="text-xs px-3 py-1.5 rounded-full bg-white/[0.06] text-[#8A8F98] hover:text-[#ECECEC]">Last 90 days</button>
          <button type="button" onClick={() => preset('', '')} className="text-xs px-3 py-1.5 rounded-full bg-white/[0.06] text-[#8A8F98] hover:text-[#ECECEC]">All time</button>
        </div>
        {invalidRange && <p role="alert" className="w-full text-sm text-[#FB7185]">“From” must not be after “To”.</p>}
      </form>

      {error && (
        <div role="alert" className="bg-[#FB7185]/10 border border-[#FB7185]/30 text-[#FB7185] text-sm p-4 rounded-2xl">
          Could not generate the report: {error}
        </div>
      )}

      {busy && !a && <div className="flex justify-center py-12" role="status" aria-label="Generating report"><Loader2 className="w-6 h-6 animate-spin text-[#E8A33D]" /></div>}

      {/* Refetch keeps the frame: the previous render stays, dimmed, until the new one lands. */}
      {a && ai && (
        <div className={busy ? 'opacity-60 transition-opacity' : ''} aria-busy={busy}>
          <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
            <p className="text-sm text-[#8A8F98]">Period: <span className="text-[#ECECEC]">{report.range}</span>
              {cmp && <span className="ml-3 text-xs">Compared with {cmp.previousLabel}</span>}
            </p>
            <div className="flex items-center gap-2" role="group" aria-label="Export report">
              <span className="text-xs text-[#8A8F98] flex items-center gap-1"><Download className="w-3.5 h-3.5" aria-hidden="true" /> Export</span>
              {(Object.keys(EXPORT_FORMATS) as ExportFormat[]).map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => exportReport(f)}
                  disabled={exporting !== null || busy}
                  className="text-xs px-3 py-1.5 rounded-full bg-white/[0.06] text-[#ECECEC] hover:bg-white/[0.12] disabled:opacity-50"
                >
                  {exporting === f ? 'Preparing…' : EXPORT_FORMATS[f].label}
                </button>
              ))}
            </div>
          </div>
          {exportError && (
            <div role="alert" className="mb-4 bg-[#FB7185]/10 border border-[#FB7185]/30 text-[#FB7185] text-sm p-3 rounded-xl">
              Export failed: {exportError}
            </div>
          )}

          {a.total === 0 ? (
            <div className="glass-panel rounded-[28px] p-12 text-center text-[#8A8F98]">No tickets were received in this period.</div>
          ) : (
            <ReportDashboard analytics={a} ai={ai} comparison={cmp} />
          )}
        </div>
      )}
    </div>
    </AdminShell>
  );
}

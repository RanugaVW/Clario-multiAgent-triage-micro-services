'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Download, Loader2 } from 'lucide-react';
import { AdminShell } from '../AdminShell';
import { useAuth } from '../../../contexts/AuthContext';
import { supabase } from '../../../lib/supabase';
import { fetchJson } from '../../../lib/fetchJson';
import { EXPORT_FORMATS, type ExportFormat } from '../../../lib/reportFormats';
import type { AiPerformance, CountRow, TicketAnalytics } from '../../../lib/reports';

type AnalyticsResponse = { range: string; analytics: TicketAnalytics; ai: AiPerformance };

const pct = (x: number | null) => (x === null ? '—' : `${Math.round(x * 100)}%`);
const seconds = (ms: number) => `${(ms / 1000).toFixed(1)} s`;

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
  const invalidRange = !!from && !!to && from > to;

  return (
    <AdminShell active="reports">
    <div className="max-w-6xl space-y-8">
      <header>
        <div>
          <h1 className="text-2xl font-bold text-[#ECECEC]">Reports</h1>
          <p className="text-sm text-[#8A8F98]">Ticket analytics for a chosen period</p>
        </div>
      </header>

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

      {a && (
        <div className={busy ? 'opacity-60 transition-opacity' : ''} aria-busy={busy}>
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <p className="text-sm text-[#8A8F98]">Period: <span className="text-[#ECECEC]">{report.range}</span></p>
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
            <div className="space-y-8">
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <Stat label="Tickets received" value={a.total} />
                <Stat label="Resolved" value={a.resolved} sub={a.resolutionRate === null ? undefined : `${Math.round(a.resolutionRate * 100)}% of received`} />
                <Stat label="Awaiting human review" value={a.awaitingHuman} />
                <Stat label="In progress" value={a.inProgress} />
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Breakdown title="By category" rows={a.byCategory} total={a.total} note="A ticket with several categories counts once under each." />
                <Breakdown title="By priority" rows={a.byPriority} total={a.total} />
                <Breakdown title="By sentiment" rows={a.bySentiment} total={a.total} />
                <Breakdown title="By status" rows={a.byStatus} total={a.total} />
              </div>

              {ai && <AiSection ai={ai} />}

              <section className="glass-panel rounded-[28px] p-6" aria-labelledby="daily-volume">
                <h2 id="daily-volume" className="text-sm font-semibold text-[#8A8F98] mb-4">Daily volume</h2>
                <table className="w-full text-sm">
                  <thead><tr className="text-left text-[#8A8F98]"><th className="pb-2 font-medium">Date</th><th className="pb-2 font-medium text-right">Tickets</th></tr></thead>
                  <tbody className="divide-y divide-white/5">
                    {a.dailyVolume.map((d) => (
                      <tr key={d.date}><td className="py-1.5 text-[#ECECEC]">{d.date}</td><td className="py-1.5 text-right text-[#ECECEC]">{d.count}</td></tr>
                    ))}
                  </tbody>
                </table>
              </section>
            </div>
          )}
        </div>
      )}
    </div>
    </AdminShell>
  );
}

function Stat({ label, value, sub }: { label: string; value: number | string; sub?: string }) {
  return (
    <div className="glass-panel rounded-[28px] p-5">
      <p className="text-xs font-medium text-[#8A8F98]">{label}</p>
      <p className="text-3xl font-bold text-[#ECECEC] mt-1">{value}</p>
      {sub && <p className="text-xs text-[#8A8F98] mt-1">{sub}</p>}
    </div>
  );
}

function Breakdown({ title, rows, total, note }: { title: string; rows: CountRow[]; total: number; note?: string }) {
  return (
    <section className="glass-panel rounded-[28px] p-6" aria-label={title}>
      <h2 className="text-sm font-semibold text-[#8A8F98] mb-4">{title}</h2>
      <ul className="space-y-3">
        {rows.map((r) => (
          <li key={r.label}>
            <div className="flex justify-between text-sm text-[#ECECEC] mb-1"><span>{r.label}</span><span>{r.count}</span></div>
            <div className="h-1.5 rounded-full bg-white/[0.06]" aria-hidden="true">
              <div className="h-full rounded-full bg-[#2DD4BF]" style={{ width: `${Math.max(2, (r.count / total) * 100)}%` }} />
            </div>
          </li>
        ))}
      </ul>
      {note && <p className="text-xs text-[#8A8F98] mt-4">{note}</p>}
    </section>
  );
}

function AiSection({ ai }: { ai: AiPerformance }) {
  const p = ai.processingTime;
  return (
    <section aria-labelledby="ai-performance" className="space-y-4">
      <h2 id="ai-performance" className="text-lg font-semibold text-[#ECECEC]">AI performance</h2>
      {ai.ticketsProcessed === 0 ? (
        <div className="glass-panel rounded-[28px] p-8 text-center text-[#8A8F98]">The AI pipeline has not processed any tickets in this period.</div>
      ) : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Stat label="Median processing time" value={p ? seconds(p.medianMs) : '—'} sub={p ? `p95 ${seconds(p.p95Ms)} · ${p.samples} measured` : 'no latency recorded'} />
            <Stat label="Escalation rate" value={pct(ai.escalation.rate)} sub={`${ai.escalation.escalated} of ${ai.ticketsProcessed} processed`} />
            <Stat label="Validation pass rate" value={pct(ai.validation.passRate)} sub={`${ai.validation.passed} passed · ${ai.validation.failed} failed`} />
            <Stat label="Mean judge score" value={ai.judgeScores.meanOverall === null ? '—' : `${ai.judgeScores.meanOverall.toFixed(2)} / 5`} sub={`${ai.judgeScores.evaluated} evaluated`} />
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {ai.escalation.reasons.length > 0 && <Breakdown title="Escalation reasons" rows={ai.escalation.reasons} total={Math.max(1, ai.escalation.escalated)} />}
            {ai.validation.failureTypes.length > 0 && <Breakdown title="Validation failures" rows={ai.validation.failureTypes} total={Math.max(1, ai.validation.failed)} />}
          </div>
          <p className="text-xs text-[#8A8F98]">
            Average effort per resolution: {ai.avgLlmCalls === null ? '—' : ai.avgLlmCalls.toFixed(1)} LLM calls, {ai.avgReflections === null ? '—' : ai.avgReflections.toFixed(1)} reflection rounds.
          </p>
        </>
      )}
    </section>
  );
}

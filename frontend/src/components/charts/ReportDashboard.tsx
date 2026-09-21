'use client';

import { volumeSeries, type AiPerformance, type PeriodComparison, type TicketAnalytics } from '../../lib/reports';
import {
  compactNumber, describeDelta, formatDuration, formatPercent, lifecycleTakeaway, meterSeverity, orderPriority, orderSentiment,
  priorityTakeaway, sentimentTakeaway, topWithOther, withShares,
} from '../../lib/reportCharts';
import { ChartCard, LegendKey, type TableData } from './ChartCard';
import { StatTile } from './StatTile';
import { Meter } from './Meter';
import { ShareBar } from './ShareBar';
import { Heatmap } from './Heatmap';
import { TrendChart, TREND_LEGEND } from './TrendChart';
import { BarsChart } from './BarsChart';
import { DEEMPHASIS, INK, LIFECYCLE, PRIORITY_COLOR, SCORE_COLOR, SENTIMENT_COLOR, SERIES } from './tokens';

/** The last 7-day block of a long range can be short; say so, so the dip at the right edge is not read as a collapse. */
export function partialWeekNote(series: ReturnType<typeof volumeSeries>): string {
  const last = series.points[series.points.length - 1];
  return series.granularity === 'week' && last && last.days < 7
    ? `The final point covers only ${last.days} of 7 days, so it is lower by construction.`
    : '';
}

const HOURS = Array.from({ length: 24 }, (_, h) => String(h).padStart(2, '0'));
const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

/** The report body: ticket overview and AI performance, every chart with a table twin. Pure presentation of one report. */
export function ReportDashboard({ analytics, ai, comparison }: { analytics: TicketAnalytics; ai: AiPerformance; comparison: PeriodComparison | null }) {
  const versus = comparison ? `vs ${comparison.previousLabel}` : undefined;
  return (
    <div className="space-y-10">
      <Overview a={analytics} cmp={comparison} versus={versus} />
      <AiSection ai={ai} cmp={comparison} versus={versus} />
    </div>
  );
}

function SectionHeading({ id, children }: { id: string; children: string }) {
  return <h2 id={id} className="text-lg font-semibold mb-4" style={{ color: INK.primary }}>{children}</h2>;
}

const rowsOf = (rows: { label: string; count: number }[]): TableData['rows'] => rows.map((r) => [r.label, r.count]);

function Overview({ a, cmp, versus }: { a: TicketAnalytics; cmp: PeriodComparison | null; versus?: string }) {
  const series = volumeSeries(a.dailyVolume);
  const lifecycle = [
    { label: 'Resolved', count: a.resolved, color: LIFECYCLE.resolved },
    { label: 'Awaiting human review', count: a.awaitingHuman, color: LIFECYCLE.awaitingHuman },
    { label: 'In progress', count: a.inProgress, color: LIFECYCLE.inProgress },
  ];
  const lifecycleShares = withShares(lifecycle);
  const categories = topWithOther(a.byCategory, 8);
  const priority = orderPriority(a.byPriority);
  const sentiment = orderSentiment(a.bySentiment);

  return (
    <section aria-labelledby="overview" className="space-y-6">
      <SectionHeading id="overview">Overview</SectionHeading>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="sm:col-span-2">
          <StatTile
            hero
            label="Tickets received"
            value={compactNumber(a.total)}
            delta={cmp ? describeDelta(cmp.tickets, 'count', null) : null}
            deltaCaption={versus}
            hint={cmp ? undefined : 'Pick a date range to compare with the previous period'}
            spark={series.points.map((p) => p.count)}
          />
        </div>
        <StatTile
          label="Resolved"
          value={compactNumber(a.resolved)}
          delta={cmp ? describeDelta(cmp.resolved, 'count', true) : null}
          deltaCaption={versus}
          hint={`${formatPercent(a.resolutionRate)} of received`}
        />
        <StatTile
          label="Resolution rate"
          value={formatPercent(a.resolutionRate)}
          delta={cmp ? describeDelta(cmp.resolutionRate, 'rate', true) : null}
          deltaCaption={versus}
          hint={`${compactNumber(a.awaitingHuman)} awaiting human review`}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <ChartCard
          className="lg:col-span-2"
          title="Ticket volume"
          subtitle={series.granularity === 'week' ? 'Received per week, in 7-day blocks from the start of the period' : 'Received per day, with the trailing 7-day average'}
          footer={partialWeekNote(series)}
          legend={
            <div className="flex flex-wrap gap-4">
              {TREND_LEGEND.filter((l) => l.label === 'Received' || series.points.some((p) => p.average !== null)).map((l) => (
                <LegendKey key={l.label} color={l.color} label={l.label} />
              ))}
            </div>
          }
          table={{
            columns: series.granularity === 'week' ? ['Week starting', 'Received', 'Days covered'] : ['Date', 'Received', '7-day average'],
            rows: series.points.map((p) => (series.granularity === 'week' ? [p.date, p.count, p.days] : [p.date, p.count, p.average === null ? null : Number(p.average.toFixed(1))])),
          }}
        >
          <TrendChart series={series} />
        </ChartCard>

        <ChartCard
          title="Where tickets stand"
          subtitle="Share of tickets received"
          footer={lifecycleTakeaway(a.awaitingHuman, a.total)}
          table={{ columns: ['State', 'Tickets', 'Share'], rows: lifecycle.map((l, i) => [l.label, l.count, formatPercent(lifecycleShares[i].share, 1)]) }}
        >
          <ShareBar segments={lifecycle} ariaLabel={`Ticket states: ${lifecycle.map((l) => `${l.label} ${l.count}`).join(', ')}`} />
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <ChartCard
          className="lg:col-span-2"
          title="Tickets by category"
          subtitle="A ticket with several categories counts once under each"
          table={{ columns: ['Category', 'Tickets'], rows: rowsOf(a.byCategory) }}
          empty={categories.length === 0}
        >
          <BarsChart data={categories.map((c) => ({ ...c, color: c.label === 'Other' || c.label === 'Unclassified' ? DEEMPHASIS : SERIES.blue }))} ariaLabel="Tickets by category" />
        </ChartCard>

        <ChartCard title="Tickets by priority" subtitle="Most severe first" footer={priorityTakeaway(priority)} table={{ columns: ['Priority', 'Tickets'], rows: rowsOf(priority) }}>
          <BarsChart data={priority.map((p) => ({ ...p, color: PRIORITY_COLOR[p.label] ?? DEEMPHASIS }))} ariaLabel="Tickets by priority" />
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <ChartCard title="Customer sentiment" subtitle="Most negative first" footer={sentimentTakeaway(sentiment)} table={{ columns: ['Sentiment', 'Tickets'], rows: rowsOf(sentiment) }}>
          <BarsChart data={sentiment.map((s) => ({ ...s, color: SENTIMENT_COLOR[s.label] ?? DEEMPHASIS }))} ariaLabel="Tickets by customer sentiment" />
        </ChartCard>

        <ChartCard
          className="lg:col-span-2"
          title="When tickets arrive"
          subtitle="By weekday and hour, UTC — darker means quieter"
          table={{ columns: ['Weekday', ...HOURS], rows: WEEKDAYS.map((d, i) => [d, ...a.arrivals[i]]) }}
        >
          <Heatmap grid={a.arrivals} />
        </ChartCard>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------------------------------ AI performance

function AiSection({ ai, cmp, versus }: { ai: AiPerformance; cmp: PeriodComparison | null; versus?: string }) {
  const p = ai.processingTime;
  if (ai.ticketsProcessed === 0) {
    return (
      <section aria-labelledby="ai-performance">
        <SectionHeading id="ai-performance">AI performance</SectionHeading>
        <div className="glass-panel rounded-[28px] p-8 text-center text-[#8A8F98]">The AI pipeline has not processed any tickets in this period.</div>
      </section>
    );
  }
  const escalationSeverity = meterSeverity(ai.escalation.rate, { worseWhen: 'higher', warn: 0.3, danger: 0.5 });
  const passSeverity = meterSeverity(ai.validation.passRate, { worseWhen: 'lower', warn: 0.9, danger: 0.7 });
  const scores = ai.judgeScores.distribution;

  return (
    <section aria-labelledby="ai-performance" className="space-y-6">
      <SectionHeading id="ai-performance">AI performance</SectionHeading>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatTile
          label="Median processing time"
          value={formatDuration(p?.medianMs ?? null)}
          delta={cmp ? describeDelta(cmp.medianProcessingMs, 'duration', false) : null}
          deltaCaption={versus}
          hint={p ? `95th percentile ${formatDuration(p.p95Ms)} · ${p.samples} measured` : 'No latency recorded'}
        />
        <StatTile
          label="Mean judge score"
          value={ai.judgeScores.meanOverall === null ? '—' : `${ai.judgeScores.meanOverall.toFixed(2)} / 5`}
          delta={cmp ? describeDelta(cmp.judgeScore, 'score', true) : null}
          deltaCaption={versus}
          hint={`${ai.judgeScores.evaluated} responses evaluated`}
        />
        <div className="glass-panel rounded-[28px] p-5 sm:col-span-2 grid gap-5 sm:grid-cols-2">
          <Meter
            label="Escalation rate"
            value={ai.escalation.rate}
            severity={escalationSeverity}
            detail={`${ai.escalation.escalated} of ${ai.ticketsProcessed} processed${cmp ? ` · ${describeDelta(cmp.escalationRate, 'rate', false)?.text ?? 'no comparison'}` : ''}`}
          />
          <Meter
            label="Validation pass rate"
            value={ai.validation.passRate}
            severity={passSeverity}
            detail={`${ai.validation.passed} passed · ${ai.validation.failed} failed${cmp ? ` · ${describeDelta(cmp.validationPassRate, 'rate', true)?.text ?? 'no comparison'}` : ''}`}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <ChartCard
          className="lg:col-span-2"
          title="Processing time distribution"
          subtitle="How long the AI pipeline took per ticket"
          table={{ columns: ['Band', 'Tickets'], rows: rowsOf(ai.latencyBuckets) }}
          empty={!p}
          emptyText="No processing times were recorded in this period."
        >
          <BarsChart orientation="columns" data={ai.latencyBuckets} ariaLabel="Distribution of AI processing time" />
        </ChartCard>

        <ChartCard
          title="Judge scores"
          subtitle="Responses by overall score, 1 (poor) to 5 (excellent)"
          table={{ columns: ['Score', 'Responses'], rows: rowsOf([...scores].reverse()) }}
          empty={ai.judgeScores.evaluated === 0}
          emptyText="No responses were scored in this period."
        >
          <BarsChart orientation="columns" unit="responses" data={[...scores].reverse().map((s) => ({ ...s, color: SCORE_COLOR[s.label] }))} ariaLabel="Distribution of judge scores" />
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard
          title="Why tickets were escalated"
          subtitle="Reasons recorded by the pipeline"
          table={{ columns: ['Reason', 'Tickets'], rows: rowsOf(ai.escalation.reasons) }}
          empty={ai.escalation.reasons.length === 0}
          emptyText="No tickets were escalated in this period."
        >
          <BarsChart data={topWithOther(ai.escalation.reasons, 8)} ariaLabel="Escalation reasons" />
        </ChartCard>

        <ChartCard
          title="Validation failures"
          subtitle="What the response checks rejected"
          table={{ columns: ['Failure type', 'Validations'], rows: rowsOf(ai.validation.failureTypes) }}
          empty={ai.validation.failureTypes.length === 0}
          emptyText="No validations failed in this period."
        >
          <BarsChart data={topWithOther(ai.validation.failureTypes, 8)} unit="validations" ariaLabel="Validation failure types" />
        </ChartCard>
      </div>

      <p className="text-xs" style={{ color: INK.muted }}>
        Average effort per resolution: {ai.avgLlmCalls === null ? '—' : ai.avgLlmCalls.toFixed(1)} LLM calls, {ai.avgReflections === null ? '—' : ai.avgReflections.toFixed(1)} reflection rounds.
      </p>
    </section>
  );
}

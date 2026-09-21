import { loadReportTickets, type ReportClient } from './reportData';
import { aiPerformance, comparePeriods, previousRange, rangeLabel, ticketAnalytics, type DateRange } from './reports';
import type { ReportBundle } from './reportExport';

/** One place that turns a date range into the report shown on screen *and* exported (FR-051/052/053). */
export async function generateReport(client: ReportClient, range: DateRange): Promise<ReportBundle> {
  // One query covers the period and the equal-length period before it, so the comparison and the report are computed
  // from the same snapshot of the data (two queries could disagree if a ticket arrived in between).
  const previous = previousRange(range);
  const tickets = await loadReportTickets(client, previous ? { from: previous.from, to: range.to } : range);
  return {
    range: rangeLabel(range),
    analytics: ticketAnalytics(tickets, range),
    ai: aiPerformance(tickets, range),
    comparison: comparePeriods(tickets, range),
  };
}

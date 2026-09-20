import { loadReportTickets, type ReportClient } from './reportData';
import { aiPerformance, rangeLabel, ticketAnalytics, type DateRange } from './reports';
import type { ReportBundle } from './reportExport';

/** One place that turns a date range into the report shown on screen *and* exported (FR-051/052/053). */
export async function generateReport(client: ReportClient, range: DateRange): Promise<ReportBundle> {
  const tickets = await loadReportTickets(client, range);
  return {
    range: rangeLabel(range),
    analytics: ticketAnalytics(tickets, range),
    ai: aiPerformance(tickets, range),
  };
}

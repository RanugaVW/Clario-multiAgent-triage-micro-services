import type { ServiceClient as ReportClient } from './serviceClient';
import type { DateRange, ReportTicket } from './reports';

export { createServiceClient as createReportClient } from './serviceClient';
export type { ServiceClient as ReportClient } from './serviceClient';

// PostgREST returns at most 1000 rows per request by default, so an unpaginated select would silently
// truncate a report - the totals would look plausible and be wrong. Page until a short page comes back.
const PAGE_SIZE = 1000;
const MAX_PAGES = 200; // hard stop (200k rows) so a runaway query cannot hang the route

type PageQuery<T> = (from: number, to: number) => PromiseLike<{ data: T[] | null; error: { message: string } | null }>;

export async function fetchAllPages<T>(query: PageQuery<T>): Promise<T[]> {
  const rows: T[] = [];
  for (let page = 0; page < MAX_PAGES; page++) {
    const { data, error } = await query(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE - 1);
    if (error) throw new Error(error.message);
    rows.push(...(data ?? []));
    if (!data || data.length < PAGE_SIZE) return rows;
  }
  throw new Error('Report exceeds the maximum supported size; narrow the date range');
}

export async function loadReportTickets(client: ReportClient, range: DateRange): Promise<ReportTicket[]> {
  return fetchAllPages<ReportTicket>((from, to) => {
    let q = client
      .from('tickets')
      .select(`
        id, status, created_at,
        ticket_classifications ( category, priority, sentiment ),
        resolutions ( escalated, resolved_at, total_latency_ms, total_llm_calls, total_reflection_count, escalation_reasons ),
        ticket_validations ( passed, failure_type, judge_ran ),
        response_evaluations ( overall_score, evaluation_latency_ms )
      `)
      .order('created_at', { ascending: true })
      .order('id', { ascending: true }); // stable paging when timestamps tie
    if (range.from) q = q.gte('created_at', range.from.toISOString());
    if (range.to) q = q.lte('created_at', range.to.toISOString());
    return q.range(from, to) as unknown as ReturnType<PageQuery<ReportTicket>>;
  });
}

import { Badge } from './ui/Badge';

type KeywordHit = { phrase: string; weight: number };

export type RoutingExplanationData = {
  decision: string;
  reason: string;
  matchedKeywords: Record<string, KeywordHit[]>;
  scores: Record<string, number>;
  categoryDomains: Record<string, string | null>;
  confidence: number | null;
  confidenceThreshold: number | null;
  categoryTrusted: boolean;
  reroutedFrom: string | null;
  rerouteReason: string | null;
  supervisor: { used: boolean; ruleDecision: string | null; reason: string } | null;
};

const DOMAIN_LABELS: Record<string, string> = {
  technical: 'Technical',
  billing: 'Billing',
  hr: 'HR',
  hr_weak: 'HR (weak signal)',
  both: 'Technical + Billing',
  escalation: 'Human review',
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const toNumber = (value: unknown): number | null => (typeof value === 'number' && Number.isFinite(value) ? value : null);

/**
 * Reads routing_explanation out of the pipeline payload (stored verbatim from
 * the orchestrator's TicketState). Returns null when it is absent or malformed,
 * e.g. tickets processed before routing recorded its reasons.
 */
export function readRoutingExplanation(payload: unknown): RoutingExplanationData | null {
  if (!isRecord(payload) || !isRecord(payload.routing_explanation)) return null;
  const raw = payload.routing_explanation;
  if (typeof raw.decision !== 'string' || typeof raw.reason !== 'string') return null;

  const matchedKeywords: Record<string, KeywordHit[]> = {};
  if (isRecord(raw.matched_keywords)) {
    for (const [domain, hits] of Object.entries(raw.matched_keywords)) {
      if (!Array.isArray(hits)) continue;
      matchedKeywords[domain] = hits
        .filter(isRecord)
        .filter(hit => typeof hit.phrase === 'string' && toNumber(hit.weight) !== null)
        .map(hit => ({ phrase: hit.phrase as string, weight: hit.weight as number }));
    }
  }
  const scores: Record<string, number> = {};
  if (isRecord(raw.scores)) {
    for (const [domain, score] of Object.entries(raw.scores)) {
      const n = toNumber(score);
      if (n !== null) scores[domain] = n;
    }
  }
  const categoryDomains: Record<string, string | null> = {};
  if (isRecord(raw.category_domains)) {
    for (const [label, domain] of Object.entries(raw.category_domains)) {
      categoryDomains[label] = typeof domain === 'string' ? domain : null;
    }
  }

  return {
    decision: raw.decision,
    reason: raw.reason,
    matchedKeywords,
    scores,
    categoryDomains,
    confidence: toNumber(raw.confidence),
    confidenceThreshold: toNumber(raw.confidence_threshold),
    categoryTrusted: raw.category_trusted !== false,
    reroutedFrom: typeof raw.rerouted_from === 'string' ? raw.rerouted_from : null,
    rerouteReason: typeof raw.reroute_reason === 'string' ? raw.reroute_reason : null,
    supervisor: isRecord(raw.supervisor) && typeof raw.supervisor.reason === 'string'
      ? {
          used: raw.supervisor.used === true,
          ruleDecision: typeof raw.supervisor.rule_decision === 'string' ? raw.supervisor.rule_decision : null,
          reason: raw.supervisor.reason,
        }
      : null,
  };
}

const domainLabel = (domain: string) => DOMAIN_LABELS[domain] ?? domain;
const percent = (value: number) => `${Math.round(value * 100)}%`;

export function RoutingExplanation({ payload }: { payload: unknown }) {
  if (isRecord(payload) && payload.cache_hit === true) {
    return (
      <Section title="Why it was routed here">
        <p className="text-app leading-relaxed text-fg">
          Answered from a near-identical resolved ticket (semantic cache), so routing did not run.
        </p>
      </Section>
    );
  }

  const explanation = readRoutingExplanation(payload);
  if (!explanation) {
    return (
      <Section title="Why it was routed here">
        <p className="text-caption text-fg-muted">
          Routing details were not recorded for this ticket. Tickets processed from now on show them here.
        </p>
      </Section>
    );
  }

  const keywordDomains = Object.entries(explanation.matchedKeywords).filter(([, hits]) => hits.length > 0);
  const categories = Object.entries(explanation.categoryDomains);
  const confidenceText = explanation.confidence === null
    ? 'confidence not measured'
    : `confidence ${percent(explanation.confidence)}`;
  const usedText = explanation.categoryTrusted
    ? 'used'
    : `not used (below ${percent(explanation.confidenceThreshold ?? 0.5)})`;
  const routedDomains = new Set(
    explanation.decision === 'both' ? ['technical', 'billing'] : [explanation.decision],
  );

  return (
    <Section title={`Why it was routed to ${domainLabel(explanation.decision)}`}>
      {explanation.supervisor?.used ? (
        <>
          <p className="text-app leading-relaxed text-fg">
            <span className="font-semibold">AI supervisor:</span> {explanation.supervisor.reason}
          </p>
          <p className="mt-1 text-caption text-fg-muted">
            The routing rules were unsure
            {explanation.supervisor.ruleDecision ? ` (they would have chosen ${domainLabel(explanation.supervisor.ruleDecision)})` : ''}
            : {explanation.reason}
          </p>
        </>
      ) : (
        <p className="text-app leading-relaxed text-fg">{explanation.reason}</p>
      )}
      {explanation.supervisor && !explanation.supervisor.used && (
        <p className="mt-1 text-caption text-fg-muted">{explanation.supervisor.reason}</p>
      )}
      {explanation.reroutedFrom && explanation.rerouteReason && (
        <p className="mt-2 text-caption text-warning">{explanation.rerouteReason}</p>
      )}

      <div className="mt-4 space-y-3">
        <div>
          <span className="mb-1.5 block text-caption text-fg-muted">
            Category from the classifier · {confidenceText} · {usedText}
          </span>
          {categories.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {categories.map(([label, domain]) => (
                <Badge key={label} className="font-mono">
                  {label} → {domain ? domainLabel(domain) : 'no domain'}
                </Badge>
              ))}
            </div>
          ) : (
            <span className="text-caption text-fg-muted">No category from the classifier.</span>
          )}
        </div>

        <div>
          <span className="mb-1.5 block text-caption text-fg-muted">Keywords found in the ticket</span>
          {keywordDomains.length > 0 ? (
            <div className="space-y-2">
              {keywordDomains.map(([domain, hits]) => (
                <div key={domain} className="flex flex-wrap items-center gap-2">
                  <span className="w-36 shrink-0 text-caption text-fg">
                    {domainLabel(domain)} · score {explanation.scores[domain] ?? 0}
                  </span>
                  {hits.map(hit => (
                    <Badge
                      key={hit.phrase}
                      tone={routedDomains.has(domain === 'hr_weak' ? 'hr' : domain) ? 'accent' : 'neutral'}
                      className="font-mono"
                    >
                      {hit.phrase} +{hit.weight}
                    </Badge>
                  ))}
                </div>
              ))}
            </div>
          ) : (
            <span className="text-caption text-fg-muted">No routing keywords were found in the ticket text.</span>
          )}
        </div>
      </div>
    </Section>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-6 border-t border-border pt-4">
      <span className="mb-2 block text-caption text-accent">{title}</span>
      {children}
    </div>
  );
}

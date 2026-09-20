// Display helpers for the ticket classification the AI pipeline stores in
// ticket_classifications. The classifier can assign several categories to one
// ticket and stores them comma-joined ("Billing & Invoicing, Refunds"), and its
// priority scale includes "Critical" and its sentiment scale "Frustrated".

export type CategoryDomain = 'billing' | 'technical' | 'other';

// Categories from the Llama-3.2 v2 taxonomy, grouped by the specialist domain
// that handles them (mirrors CATEGORY_DOMAIN in the orchestrator's taxonomy.py).
const BILLING_CATEGORIES = new Set(['billing & invoicing', 'refunds', 'subscription management']);
const TECHNICAL_CATEGORIES = new Set([
  'technical support', 'authentication', 'account access', 'performance',
  'data integrity', 'service outage', 'ui/ux',
]);
// Rows written by the previous classifier stored one bare domain-ish word.
const LEGACY_BILLING = new Set(['billing', 'account']);
const LEGACY_TECHNICAL = new Set(['technical']);

/** "Billing & Invoicing, Refunds" -> ["Billing & Invoicing", "Refunds"]. Tolerates null/empty. */
export function splitCategories(category: string | null | undefined): string[] {
  if (!category) return [];
  return category.split(',').map(part => part.trim()).filter(Boolean);
}

/**
 * The specialist domain a ticket's categories point at. A ticket spanning both
 * domains (or neither) is 'other' - it needs a person to look at it.
 */
export function categoryDomain(category: string | null | undefined): CategoryDomain {
  const labels = splitCategories(category).map(label => label.toLowerCase());
  const billing = labels.some(l => BILLING_CATEGORIES.has(l) || LEGACY_BILLING.has(l));
  const technical = labels.some(l => TECHNICAL_CATEGORIES.has(l) || LEGACY_TECHNICAL.has(l));
  if (billing && !technical) return 'billing';
  if (technical && !billing) return 'technical';
  return 'other';
}

/** Text colour for a priority value; undefined means "use the default colour". */
export function priorityColor(priority: string | null | undefined): string | undefined {
  switch (priority?.toLowerCase()) {
    case 'critical': return '#FB7185';
    case 'high': return '#FB923C';
    default: return undefined;
  }
}

/** Theme text-colour class for a priority; '' means "use the default colour". */
export function priorityClass(priority: string | null | undefined): string {
  switch (priority?.toLowerCase()) {
    case 'critical': return 'text-danger';
    case 'high': return 'text-warning';
    default: return '';
  }
}

/** Text colour for a sentiment value; undefined means "use the default colour". */
export function sentimentColor(sentiment: string | null | undefined): string | undefined {
  switch (sentiment?.toLowerCase()) {
    case 'frustrated':
    case 'negative': return '#FB7185';
    default: return undefined;
  }
}

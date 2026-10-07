import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { RoutingExplanation, readRoutingExplanation } from './RoutingExplanation';

const hrPayload = {
  cache_hit: false,
  routing_explanation: {
    decision: 'hr',
    rule: 'hr_trigger',
    reason: 'The ticket contains HR phrases (score 3) that need human judgement.',
    matched_keywords: { technical: [], billing: [], hr: [{ phrase: 'instructor', weight: 3 }], hr_weak: [] },
    scores: { technical: 0, billing: 0, hr: 3, hr_weak: 0 },
    category_domains: { 'Billing & Invoicing': 'billing', 'Feature Request': null },
    confidence: 0.58,
    confidence_threshold: 0.5,
    category_trusted: true,
  },
};

describe('readRoutingExplanation', () => {
  it('reads the explanation the orchestrator stores', () => {
    const parsed = readRoutingExplanation(hrPayload);
    expect(parsed?.decision).toBe('hr');
    expect(parsed?.matchedKeywords.hr).toEqual([{ phrase: 'instructor', weight: 3 }]);
    expect(parsed?.categoryDomains).toEqual({ 'Billing & Invoicing': 'billing', 'Feature Request': null });
    expect(parsed?.confidence).toBe(0.58);
  });

  it('returns null for tickets processed before routing recorded its reasons', () => {
    expect(readRoutingExplanation({ category: 'Refunds' })).toBeNull();
    expect(readRoutingExplanation(null)).toBeNull();
    expect(readRoutingExplanation({ routing_explanation: { decision: 'hr' } })).toBeNull();
  });

  it('drops malformed keyword entries instead of crashing', () => {
    const parsed = readRoutingExplanation({
      routing_explanation: {
        ...hrPayload.routing_explanation,
        matched_keywords: { hr: [{ phrase: 'instructor', weight: 3 }, { phrase: 5 }, 'junk'] },
      },
    });
    expect(parsed?.matchedKeywords.hr).toEqual([{ phrase: 'instructor', weight: 3 }]);
  });
});

describe('RoutingExplanation', () => {
  it('shows the domain, reason, category mapping and matched keywords', () => {
    render(<RoutingExplanation payload={hrPayload} />);
    expect(screen.getByText('Why it was routed to HR')).toBeInTheDocument();
    expect(screen.getByText(/need human judgement/)).toBeInTheDocument();
    expect(screen.getByText('Billing & Invoicing → Billing')).toBeInTheDocument();
    expect(screen.getByText('Feature Request → no domain')).toBeInTheDocument();
    expect(screen.getByText('instructor +3')).toBeInTheDocument();
    expect(screen.getByText(/confidence 58% · used/)).toBeInTheDocument();
  });

  it('says when the classifier category was not trusted', () => {
    render(<RoutingExplanation payload={{
      routing_explanation: { ...hrPayload.routing_explanation, confidence: 0.3, category_trusted: false },
    }} />);
    expect(screen.getByText(/not used \(below 50%\)/)).toBeInTheDocument();
  });

  it('explains a cache hit and an older ticket without routing data', () => {
    const { rerender } = render(<RoutingExplanation payload={{ cache_hit: true }} />);
    expect(screen.getByText(/semantic cache/)).toBeInTheDocument();
    rerender(<RoutingExplanation payload={{ category: 'Refunds' }} />);
    expect(screen.getByText(/were not recorded for this ticket/)).toBeInTheDocument();
  });
});

describe('RoutingExplanation with the AI supervisor', () => {
  it('shows the supervisor decision and what the rules would have done', () => {
    render(<RoutingExplanation payload={{
      routing_explanation: {
        ...hrPayload.routing_explanation,
        decision: 'billing',
        reason: 'The category does not belong to a specialist domain and the ticket has no routing keywords.',
        supervisor: { used: true, rule_decision: 'escalation', decision: 'billing', reason: 'Asks to change plan.' },
      },
    }} />);
    expect(screen.getByText('Why it was routed to Billing')).toBeInTheDocument();
    expect(screen.getByText(/Asks to change plan\./)).toBeInTheDocument();
    expect(screen.getByText(/would have chosen Human review/)).toBeInTheDocument();
  });
});

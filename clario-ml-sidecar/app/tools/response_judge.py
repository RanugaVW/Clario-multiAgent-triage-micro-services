"""Response Judge LLM - Scores draft responses 1-5 with improvement suggestions.

This module provides a configurable judge LLM that evaluates customer support
draft responses against priority-conditioned tone requirements, ground truth
references, and policy compliance.

Supported providers: OpenAI (GPT-5.4 Mini, default) and Gemini (fallback,
set RESPONSE_JUDGE_PROVIDER=gemini).
"""

from __future__ import annotations

import os
import json
import logging
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict, field

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# PRIORITY-CONDITIONED TONE REQUIREMENTS
# ──────────────────────────────────────────────────────────────────────────────
# These define what language is REQUIRED vs FORBIDDEN for each priority level.
# The judge LLM uses these to score priority_tone_match_score (1-5).

PRIORITY_TONE_REQUIREMENTS: Dict[str, Dict[str, Any]] = {
    "Urgent": {
        "required_phrases": [
            "deeply apologize",
            "sincere apology",
            "escalated immediately",
            "top priority",
            "personal attention",
            "within the hour",
            "immediate action",
            "urgent resolution",
        ],
        "forbidden_phrases": [
            "at your earliest convenience",
            "when you have a moment",
            "general inquiry",
            "standard process",
            "routine timeline",
            "no rush",
        ],
        "guidance": (
            "MUST convey extreme urgency, personal ownership, and concrete immediate action. "
            "Use language like 'I am personally escalating this', 'resolving within the hour', "
            "'this is our top priority'. No generic or deferential language."
        ),
    },
    "Critical": {
        "required_phrases": [
            "deeply apologize",
            "escalated immediately",
            "critical priority",
            "senior team",
            "immediate resolution",
            "personal oversight",
            "executive attention",
        ],
        "forbidden_phrases": [
            "at your earliest convenience",
            "standard timeline",
            "routine",
            "when possible",
            "general process",
        ],
        "guidance": (
            "Critical urgency language, executive/senior team escalation mention, "
            "specific ETA (hours not days), personal accountability statements."
        ),
    },
    "High": {
        "required_phrases": [
            "sincerely apologize",
            "urgent attention",
            "resolve within",
            "escalated to",
            "priority handling",
            "expedited",
        ],
        "forbidden_phrases": [
            "whenever possible",
            "general timeframe",
            "no specific timeline",
            "standard queue",
        ],
        "guidance": (
            "Sincere apology, acknowledged urgency, specific timeline (hours), "
            "clear escalation mention. Avoid vague 'we'll look into it' language."
        ),
    },
    "Medium": {
        "required_phrases": [
            "apologize for the inconvenience",
            "working on this",
            "update within 24",
            "investigating",
            "looking into",
        ],
        "forbidden_phrases": [
            "guaranteed fix today",
            "immediate resolution",
            "top priority",
            "escalated immediately",
        ],
        "guidance": (
            "Professional apology, reasonable timeline (24h), no over-promising. "
            "Balanced tone - not dismissive but not alarmist."
        ),
    },
    "Low": {
        "required_phrases": [
            "thank you for reporting",
            "investigating",
            "no immediate action",
            "appreciate your patience",
        ],
        "forbidden_phrases": [
            "urgent",
            "critical",
            "immediate",
            "escalated",
            "emergency",
        ],
        "guidance": (
            "Acknowledgment, appropriate casualness, no alarmist language. "
            "Can be more conversational. 'Thanks for letting us know' tone."
        ),
    },
}

# Default fallback for unknown priorities
DEFAULT_PRIORITY_REQ = PRIORITY_TONE_REQUIREMENTS["Medium"]

# ──────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class JudgeScore:
    """Structured output from the judge LLM evaluation."""
    overall_score: int
    priority_tone_match_score: int
    completeness_score: int
    accuracy_score: int
    policy_compliance_score: int
    groundedness_score: int
    reasoning: str
    improvement_suggestions: List[str]
    required_phrases_present: List[str]
    required_phrases_missing: List[str]
    forbidden_phrases_found: List[str]
    judge_model: str = "unknown"
    evaluation_latency_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def passes_threshold(self, min_score: int = 3) -> bool:
        """Check if overall score meets minimum threshold."""
        return self.overall_score >= min_score


@dataclass
class JudgeConfig:
    """Configuration for the judge LLM."""
    provider: str = "openai"  # "openai" | "gemini"
    model_name: str = "gpt-5.4-mini"
    temperature: float = 0.1
    min_score_threshold: int = 3
    max_retries: int = 2
    timeout_seconds: int = 30


# ──────────────────────────────────────────────────────────────────────────────
# JUDGE PROMPT TEMPLATE
# ──────────────────────────────────────────────────────────────────────────────

JUDGE_SYSTEM_PROMPT = """You are a Senior QA Engineer evaluating customer support draft responses.
Your evaluations directly impact customer satisfaction and agent performance metrics.
Be precise, fair, and specific in your scoring and feedback."""

JUDGE_USER_PROMPT_TEMPLATE = """TICKET PRIORITY: {priority}
TICKET CATEGORY: {category}
TICKET ISSUE: {ticket_issue}

TONE REQUIREMENTS FOR THIS PRIORITY ({priority}):
- Guidance: {guidance}
- REQUIRED phrases (must appear in draft): {required_phrases}
- FORBIDDEN phrases (must NOT appear in draft): {forbidden_phrases}

REFERENCE RESOLUTIONS (ground truth from similar historical tickets):
{few_shots_section}

RETRIEVED KNOWLEDGE BASE CONTEXT (for groundedness check):
{rag_context_section}

DRAFT TO EVALUATE:
{draft}

OUTPUT JSON ONLY with this exact structure:
{{
  "overall_score": 1-5,
  "priority_tone_match_score": 1-5,
  "completeness_score": 1-5,
  "accuracy_score": 1-5,
  "policy_compliance_score": 1-5,
  "groundedness_score": 1-5,
  "reasoning": "Detailed explanation of scores, referencing specific parts of the draft and comparing to references",
  "improvement_suggestions": [
    "Specific, actionable suggestion 1",
    "Specific, actionable suggestion 2"
  ],
  "required_phrases_present": ["phrase1", "phrase2"],
  "required_phrases_missing": ["phrase3", "phrase4"],
  "forbidden_phrases_found": ["phrase5"]
}}

SCORING RUBRIC (1-5):
- 5: Exceptional - Exceeds expectations, perfect priority tone, complete, accurate, well-grounded
- 4: Good - Meets all requirements, minor gaps only, appropriate tone
- 3: Acceptable - Meets most requirements, some gaps, tone mostly appropriate
- 2: Below Expectations - Significant gaps, tone mismatch, incomplete, minor inaccuracies
- 1: Unacceptable - Wrong tone for priority, major inaccuracies, policy violations, ungrounded

DIMENSION DEFINITIONS:
- priority_tone_match: Does the language match the urgency/expectations for this priority level?
- completeness: Does the draft address all aspects of the issue? Compare to reference resolutions.
- accuracy: Are the technical/billing details correct? No hallucinations?
- policy_compliance: No overcommitments, no PII leaks, appropriate fallback for low context?
- groundedness: Does the draft reference or align with retrieved KB context?"""

# ──────────────────────────────────────────────────────────────────────────────
# RESPONSE JUDGE CLASS
# ──────────────────────────────────────────────────────────────────────────────

class ResponseJudge:
    """Scores draft responses using a configurable judge LLM."""

    def __init__(self, config: Optional[JudgeConfig] = None):
        provider = os.getenv("RESPONSE_JUDGE_PROVIDER", "openai")
        # Model env var is provider-specific so switching RESPONSE_JUDGE_PROVIDER
        # can't accidentally hand one provider's model string to the other's API.
        if provider == "openai":
            model_name = os.getenv("OPENAI_JUDGE_MODEL", "gpt-5.4-mini")
        else:
            # gemini-flash-latest (not a pinned version) so this default can't
            # go stale the way gemini-2.5-pro did - it was deprecated by Google
            # ("no longer available to new users") while still hardcoded here.
            model_name = os.getenv("GEMINI_JUDGE_MODEL", "gemini-flash-latest")

        self.config = config or JudgeConfig(
            provider=provider,
            model_name=model_name,
            min_score_threshold=int(os.getenv("MIN_JUDGE_SCORE", "3")),
        )

        if self.config.provider == "gemini":
            self.client = genai.Client()
        elif self.config.provider == "openai":
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        else:
            raise ValueError(f"Unknown judge provider: {self.config.provider}")

        logger.info(f"ResponseJudge initialized: provider={self.config.provider}, model={self.config.model_name}")

    def _build_prompt(
        self,
        draft: str,
        priority: str,
        category: str,
        ticket_issue: str,
        few_shots: List[Dict],
        rag_context: List[Dict],
    ) -> str:
        """Build the judge prompt with priority-conditioned requirements."""

        req = PRIORITY_TONE_REQUIREMENTS.get(priority, DEFAULT_PRIORITY_REQ)

        # Format few-shot references
        few_shots_section = "None available."
        if few_shots:
            few_shots_section = ""
            for i, fs in enumerate(few_shots):
                few_shots_section += f"\n--- REFERENCE {i+1} (Priority: {fs.get('priority', 'Unknown')}, Category: {fs.get('category', 'Unknown')}) ---\n"
                few_shots_section += f"Issue: {fs.get('issue', '')}\n"
                few_shots_section += f"Resolution: {fs.get('resolution', '')}\n"
                if fs.get('similarity_score'):
                    few_shots_section += f"Similarity: {fs['similarity_score']:.2f}\n"

        # Format RAG context
        rag_context_section = "None retrieved."
        if rag_context:
            rag_context_section = ""
            for i, ctx in enumerate(rag_context[:3]):
                score = ctx.get('score', 0)
                text = ctx.get('text', '')[:800]
                source = ctx.get('source_file', 'unknown')
                rag_context_section += f"\nSource {i+1} (score: {score:.2f}, file: {source}): {text}\n"

        required_str = ", ".join(f'"{p}"' for p in req["required_phrases"])
        forbidden_str = ", ".join(f'"{p}"' for p in req["forbidden_phrases"])

        return JUDGE_USER_PROMPT_TEMPLATE.format(
            priority=priority,
            category=category,
            ticket_issue=ticket_issue,
            guidance=req["guidance"],
            required_phrases=required_str,
            forbidden_phrases=forbidden_str,
            few_shots_section=few_shots_section,
            rag_context_section=rag_context_section,
            draft=draft,
        )

    async def evaluate(
        self,
        draft: str,
        priority: str,
        category: str,
        ticket_issue: str,
        few_shots: Optional[List[Dict]] = None,
        rag_context: Optional[List[Dict]] = None,
    ) -> JudgeScore:
        """Evaluate a draft response and return structured scores.

        Raises once every retry is exhausted, rather than returning a fake
        low score - a judge outage is not the same thing as "this response
        is unacceptable," and disguising one as the other both misleads
        anyone reading response_evaluations and corrupts the admin-override
        feedback loop (app/jobs/sync_judge_references.py). The caller
        (response_judge_node) already catches and logs failures per domain
        rather than storing anything for it - this just lets that existing
        handling actually see failures instead of a fake "successful" score.

        An empty draft is a genuine 1/5, not a failure, so that case alone
        still returns a real score.
        """

        if not draft or not draft.strip():
            return self._empty_score("Empty draft provided")

        prompt = self._build_prompt(draft, priority, category, ticket_issue, few_shots or [], rag_context or [])

        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                start = time.time()
                if self.config.provider == "gemini":
                    response_text = await self._call_gemini(prompt)
                else:
                    response_text = await self._call_openai(prompt)
                latency_ms = int((time.time() - start) * 1000)

                return self._parse_response(response_text, latency_ms)

            except Exception as e:
                last_error = e
                logger.warning(f"Judge attempt {attempt + 1} failed: {e}")
                if attempt < self.config.max_retries:
                    await self._backoff(attempt)

        logger.error(f"Judge evaluation failed after {self.config.max_retries + 1} attempts: {last_error}")
        raise RuntimeError(
            f"Judge evaluation failed after {self.config.max_retries + 1} attempts"
        ) from last_error

    async def _call_gemini(self, prompt: str) -> str:
        # client.models.generate_content is synchronous - every other Gemini
        # call site in this codebase (local_llm.py, local_ocr.py) calls it
        # directly for that reason. This function is async, so it needs the
        # real async accessor (client.aio.models...) instead; awaiting the
        # sync one raised "GenerateContentResponse can't be used in 'await'
        # expression" on every call that would otherwise have succeeded.
        response = await self.client.aio.models.generate_content(
            model=self.config.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=JUDGE_SYSTEM_PROMPT,
                temperature=self.config.temperature,
                response_mime_type="application/json",
            ),
        )
        return response.text

    async def _call_openai(self, prompt: str) -> str:
        response = await self.client.chat.completions.create(
            model=self.config.model_name,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=self.config.temperature,
        )
        return response.choices[0].message.content

    async def _backoff(self, attempt: int) -> None:
        import asyncio
        await asyncio.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s...

    def _parse_response(self, text: str, latency_ms: int = 0) -> JudgeScore:
        """Parse and validate judge JSON response.

        Raises on malformed JSON instead of returning a fake score, so the
        caller's retry loop in evaluate() treats it as a failed attempt
        (worth retrying) rather than a silent, immediate "success."
        """
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse judge JSON: {e}, text: {text[:500]}")
            raise ValueError(f"Invalid JSON from judge: {e}") from e

        # Validate and clamp all scores to 1-5
        score_fields = [
            "overall_score",
            "priority_tone_match_score",
            "completeness_score",
            "accuracy_score",
            "policy_compliance_score",
            "groundedness_score",
        ]

        for field_name in score_fields:
            val = data.get(field_name, 1)
            try:
                data[field_name] = max(1, min(5, int(val)))
            except (ValueError, TypeError):
                data[field_name] = 1

        # Ensure list fields exist
        for list_field in [
            "improvement_suggestions",
            "required_phrases_present",
            "required_phrases_missing",
            "forbidden_phrases_found",
        ]:
            if list_field not in data or not isinstance(data[list_field], list):
                data[list_field] = []

        # Ensure reasoning exists
        if not data.get("reasoning"):
            data["reasoning"] = "No reasoning provided by judge."

        data["judge_model"] = self.config.model_name
        data["evaluation_latency_ms"] = latency_ms

        return JudgeScore(**data)

    def _empty_score(self, reason: str) -> JudgeScore:
        """Return minimum scores with error reason."""
        return JudgeScore(
            overall_score=1,
            priority_tone_match_score=1,
            completeness_score=1,
            accuracy_score=1,
            policy_compliance_score=1,
            groundedness_score=1,
            reasoning=reason,
            improvement_suggestions=["Judge unavailable - manual review required"],
            required_phrases_present=[],
            required_phrases_missing=[],
            forbidden_phrases_found=[],
            judge_model=self.config.model_name,
        )


# ──────────────────────────────────────────────────────────────────────────────
# SINGLETON & HELPER FUNCTIONS
# ──────────────────────────────────────────────────────────────────────────────

_judge_instance: Optional[ResponseJudge] = None


def get_judge(config: Optional[JudgeConfig] = None) -> ResponseJudge:
    """Get or create the singleton ResponseJudge instance."""
    global _judge_instance
    if _judge_instance is None:
        _judge_instance = ResponseJudge(config)
    return _judge_instance


async def evaluate_draft(
    draft: str,
    priority: str,
    category: str,
    ticket_issue: str,
    few_shots: Optional[List[Dict]] = None,
    rag_context: Optional[List[Dict]] = None,
) -> JudgeScore:
    """Convenience function to evaluate a draft using the singleton judge."""
    judge = get_judge()
    return await judge.evaluate(draft, priority, category, ticket_issue, few_shots, rag_context)


# ──────────────────────────────────────────────────────────────────────────────
# SYNCHRONOUS WRAPPER (for non-async contexts)
# ──────────────────────────────────────────────────────────────────────────────

def evaluate_draft_sync(
    draft: str,
    priority: str,
    category: str,
    ticket_issue: str,
    few_shots: Optional[List[Dict]] = None,
    rag_context: Optional[List[Dict]] = None,
) -> JudgeScore:
    """Synchronous wrapper for evaluate_draft."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(
        evaluate_draft(draft, priority, category, ticket_issue, few_shots, rag_context)
    )
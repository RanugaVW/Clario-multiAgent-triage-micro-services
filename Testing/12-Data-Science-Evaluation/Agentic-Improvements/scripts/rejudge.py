"""Fair quality comparison of the A/B arms, after run_agentic_ab.py.

In-run judge scores are biased for the new arm: after a redraft the judge scores
the original AND the rewrite and keeps the higher one (max of two noisy
samples). This script scores every final draft of BOTH arms again, once each,
with identical inputs (score mode), and asks the pairwise judge which arm's
customer reply is better, in both orders to cancel position bias (pairwise mode).

Usage (from the clario-ml-sidecar venv):
    python rejudge.py score
    python rejudge.py pairwise
Resumable: outputs append to results/rejudge_scores.jsonl / results/pairwise.jsonl.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "results"
SIDECAR = HERE.parents[3] / "clario-ml-sidecar"
sys.path.insert(0, str(SIDECAR))
os.chdir(SIDECAR)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(SIDECAR / ".env")
from app.tools.response_judge import get_judge  # noqa: E402

RUNS = RESULTS / "ab_runs.jsonl"
SCORES = RESULTS / "rejudge_scores.jsonl"
PAIRWISE = RESULTS / "pairwise.jsonl"
CUSTOMER_MARKER = "**[CUSTOMER RESPONSE]**"
PACING_SECONDS = 2


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def latest_runs() -> dict[tuple[str, str], dict]:
    """The last successful record per (arm, ticket)."""
    runs = {}
    for r in load_jsonl(RUNS):
        if r.get("drafts") is not None:
            runs[(r["arm"], r["query_id"])] = r
    return runs


def customer_reply(run: dict) -> str | None:
    """What the customer (or the reviewing human) would read for this ticket."""
    text = run.get("final_response")
    if not text:
        drafts = [d for d in (run.get("drafts") or {}).values() if d]
        text = "\n\n".join(drafts) if drafts else None
    if not text:
        return None
    parts = [p.split(CUSTOMER_MARKER, 1)[1].strip() if CUSTOMER_MARKER in p else p.strip()
             for p in text.split("**[INTERNAL TECHNICAL REPORT]**") if p.strip()]
    return "\n\n".join(parts)


async def score_mode() -> None:
    done = {(r["arm"], r["query_id"], r["domain"]) for r in load_jsonl(SCORES)}
    judge = get_judge()
    for (arm, qid), run in sorted(latest_runs().items(), key=lambda kv: (kv[0][1], kv[0][0])):
        for domain, draft in (run.get("drafts") or {}).items():
            if not draft or (arm, qid, domain) in done:
                continue
            context = [{"text": c.get("text") or "", "source_file": c.get("source_file"), "score": c.get("score") or 0}
                       for c in (run.get("retrieved") or {}).get(domain, [])]
            try:
                s = await judge.evaluate(draft, run.get("priority") or "Medium", run.get("category") or "Unknown",
                                         run.get("redacted_text") or "", [], context)
                row = {"arm": arm, "query_id": qid, "domain": domain, **{k: v for k, v in s.to_dict().items()
                                                                         if k.endswith("_score")}}
            except Exception as e:
                row = {"arm": arm, "query_id": qid, "domain": domain, "error": repr(e)[:200]}
            with open(SCORES, "a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            print(arm, qid, domain, row.get("overall_score"), row.get("error", ""), flush=True)
            time.sleep(PACING_SECONDS)


async def pairwise_mode() -> None:
    done = {r["query_id"] for r in load_jsonl(PAIRWISE) if "final_winner" in r}
    judge = get_judge()
    runs = latest_runs()
    for qid in sorted({q for _, q in runs}):
        control, new = runs.get(("control", qid)), runs.get(("new", qid))
        if qid in done or not control or not new:
            continue
        a, b = customer_reply(new), customer_reply(control)
        if not a or not b:
            continue
        if a.strip() == b.strip():
            row = {"query_id": qid, "final_winner": "identical"}
        else:
            try:
                # "draft" slot = new arm, "reference" slot = control arm.
                v = await judge.compare_draft_to_reference(new.get("redacted_text") or "", new.get("priority") or "Medium",
                                                           new.get("category") or "Unknown", a, b)
                winner = {"draft": "new", "reference": "control", "tie": "tie"}[v.final_winner]
                row = {"query_id": qid, "final_winner": winner, "pass1": v.winner_pass1, "pass2": v.winner_pass2,
                       "reasoning": v.reasoning_pass1[:400]}
            except Exception as e:
                row = {"query_id": qid, "error": repr(e)[:200]}
        with open(PAIRWISE, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        print(qid, row.get("final_winner"), row.get("error", ""), flush=True)
        time.sleep(PACING_SECONDS)


if __name__ == "__main__":
    asyncio.run(score_mode() if sys.argv[1:] == ["score"] else pairwise_mode())

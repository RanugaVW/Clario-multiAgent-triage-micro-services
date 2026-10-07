"""Classifier ablation: run the 70 real tickets through the CURRENT pipeline (same routing,
escalation, KB, prompts, judge) with only the classifier swapped.

  --condition new : the current classifier (Gemini-distilled Llama 3.2 adapter, as configured in the sidecar .env)
  --condition old : the first fine-tuned Llama 3.2 adapter, run with the classifier code it originally used
                    (first_model_local_llm.py). Its free-text category goes into `category`, `categories` is
                    empty, so the current routing takes its existing free-text branch. No label mapping is invented.

Extra fields are recorded that earlier runs did not save: classification source, cache hit, LLM call count,
retrieved source files, and the classification time.

Usage (from the sidecar venv):  python run_ablation.py --condition old --tag old_run1
"""
from __future__ import annotations

import argparse, asyncio, csv, importlib.util, json, os, sys, time
from pathlib import Path

ROOT = Path("/home/ranuga-weerasekara/Desktop/clario")
SIDECAR = ROOT / "clario-ml-sidecar"
HERE = Path(__file__).resolve().parent
GT = ROOT / "Testing/12-Data-Science-Evaluation/Track-A-Retrieval-Quality/data/lms_ticket_ground_truth.csv"
OUT_DIR = HERE.parent / "results"
OLD_ADAPTER = str(ROOT / "Fine Tuned LLama-3.2 (3B)")
PACING = 8

FIELDS = ["query_id", "gt_domain", "condition", "classification_source", "category", "categories", "priority", "sentiment",
          "confidence", "classification_seconds", "routing_decision", "escalation_triggered", "escalation_reasons",
          "cache_hit", "llm_call_count", "domain_drafted", "draft", "retrieved_source_files", "retrieved_scores", "retrieved_texts",
          "judge_overall_score", "judge_priority_tone_match_score", "judge_completeness_score", "judge_accuracy_score",
          "judge_policy_compliance_score", "judge_groundedness_score", "judge_reasoning", "error"]


def init_state(qid, text):
    return {"ticket_id": qid, "raw_text": text, "reflection_count": 0, "reflection_critiques": [], "reroute_attempted": False,
            "needs_reroute": False, "agent_drafts": {}, "retrieved_context": {}, "rag_top_score": {},
            "low_relevance_flags": {}, "validation_result": {}}


async def run(condition, tag, start, limit):
    sys.path.insert(0, str(SIDECAR))
    os.chdir(SIDECAR)
    if condition == "old":
        os.environ["LLAMA_ADAPTER_PATH"] = OLD_ADAPTER   # read by first_model_local_llm before load_dotenv
    timings = {}
    import app.tools.classification_tool as ct
    if condition == "old":
        spec = importlib.util.spec_from_file_location("first_model_local_llm", HERE / "first_model_local_llm.py")
        old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)

        def classify_old(text):
            t0 = time.time(); r = old.classify_ticket_local(text); timings["last"] = time.time() - t0
            r = dict(r); r["categories"] = []   # free-text category: current routing uses its existing free-text branch
            return r
        ct.classify_ticket_local = classify_old
    else:
        orig = ct.classify_ticket_local

        def classify_new(text):
            t0 = time.time(); r = orig(text); timings["last"] = time.time() - t0
            return r
        ct.classify_ticket_local = classify_new

    from app.graph.graph_builder import build_graph
    graph = build_graph()
    rows = list(csv.DictReader(open(GT, newline="", encoding="utf-8-sig")))
    rows = rows[start:start + limit] if limit else rows[start:]
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f"ablation_{tag}.csv"
    new_file = not out.exists()
    done = set()
    if not new_file:
        done = {r["query_id"] for r in csv.DictReader(open(out, newline="", encoding="utf-8"))}
    with open(out, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file: w.writeheader()
        for i, row in enumerate(rows, 1):
            qid, text = row["query_id"], row["query_text"]
            if qid in done: continue
            print(f"[{i}/{len(rows)}] {qid}", flush=True)
            base = {"query_id": qid, "gt_domain": row["domain"], "condition": condition}
            try:
                s = await asyncio.wait_for(graph.ainvoke(init_state(qid, text)), timeout=240)
            except Exception as e:
                print("  FAILED:", repr(e)[:200], flush=True)
                w.writerow({**base, "error": repr(e)[:300]}); f.flush(); time.sleep(PACING); continue
            common = {**base, "classification_source": s.get("classification_source"), "category": s.get("category"),
                      "categories": json.dumps(s.get("categories") or []), "priority": s.get("priority"), "sentiment": s.get("sentiment"),
                      "confidence": s.get("classification_confidence"), "classification_seconds": round(timings.get("last", 0), 2),
                      "routing_decision": s.get("routing_decision"), "escalation_triggered": s.get("escalation_triggered"),
                      "escalation_reasons": ";".join(s.get("escalation_reasons") or []), "cache_hit": bool(s.get("cache_hit")),
                      "llm_call_count": s.get("llm_call_count")}
            drafts = {d: t for d, t in (s.get("agent_drafts") or {}).items() if t}
            if not drafts:
                w.writerow(common)
            for d, draft in drafts.items():
                j = (s.get("judge_evaluations") or {}).get(d, {})
                ctx = (s.get("retrieved_context") or {}).get(d, [])
                w.writerow({**common, "domain_drafted": d, "draft": draft,
                            "retrieved_source_files": json.dumps([c.get("source_file") for c in ctx]),
                            "retrieved_scores": json.dumps([round(c.get("score", 0), 4) for c in ctx]),
                            "retrieved_texts": json.dumps([c.get("text", "") for c in ctx]),
                            "judge_overall_score": j.get("overall_score", ""), "judge_priority_tone_match_score": j.get("priority_tone_match_score", ""),
                            "judge_completeness_score": j.get("completeness_score", ""), "judge_accuracy_score": j.get("accuracy_score", ""),
                            "judge_policy_compliance_score": j.get("policy_compliance_score", ""), "judge_groundedness_score": j.get("groundedness_score", ""),
                            "judge_reasoning": j.get("reasoning", "")})
            f.flush(); time.sleep(PACING)
    print("wrote", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--condition", choices=["old", "new"], required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    asyncio.run(run(a.condition, a.tag, a.start, a.limit))

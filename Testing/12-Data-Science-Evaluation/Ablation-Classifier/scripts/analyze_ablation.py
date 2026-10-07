"""Analyse the classifier ablation runs (old vs new classifier, everything else identical).

Usage: python analyze_ablation.py old_run1 new_run1 [new_run2 ...]
The first tag is the baseline (old classifier); the others are compared with it.
Writes results/ablation_summary.json and prints a readable summary.
"""
from __future__ import annotations

import json, sys
from math import comb, sqrt
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

ROOT = Path("/home/ranuga-weerasekara/Desktop/clario/Testing/12-Data-Science-Evaluation")
RES = ROOT / "Ablation-Classifier/results"
sys.path.insert(0, str(ROOT / "Track-C-Response-Quality/scripts"))

gt = pd.read_csv(ROOT / "Track-B-Routing-Escalation-Accuracy/data/routing_ground_truth.csv").set_index("query_id")
ann = pd.read_csv(ROOT / "Track-B-Routing-Escalation-Accuracy/data/routing_annotation_sample.csv").set_index("query_id")
docs = pd.read_csv(ROOT / "Track-A-Retrieval-Quality/data/lms_ticket_ground_truth.csv").set_index("query_id")
agreed = gt[(gt.routing_ground_truth != "NEEDS_REVIEW") & (gt.should_escalate != "NEEDS_REVIEW")]


def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return round((c - h) / d * 100, 1), round((c + h) / d * 100, 1)


def mcnemar(b, c):
    m = b + c
    return 1.0 if m == 0 else min(1.0, 2 * sum(comb(m, i) for i in range(0, min(b, c) + 1)) / 2 ** m)


def load(tag):
    d = pd.read_csv(RES / f"ablation_{tag}.csv")
    per_ticket = d.drop_duplicates("query_id").set_index("query_id")
    return d, per_ticket


def esc_flag(t):
    return t.escalation_triggered.astype(str).str.lower().eq("true") | (t.routing_decision == "escalation")


def label(h):
    o = ann[f"human{h}_routing_ground_truth_override"]
    return ann.routing_ground_truth_mechanical.where(o.isna(), o), ann[f"human{h}_should_escalate"].astype(str).str.lower().eq("yes")


def prf(e, y):
    tp = int((e & y).sum()); fp = int((e & ~y).sum()); fn = int((~e & y).sum())
    p = tp / (tp + fp) if tp + fp else 0.0; r = tp / (tp + fn) if tp + fn else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(p * 100, 1), "recall": round(r * 100, 1), "f1": round(2 * p * r / (p + r) * 100, 1) if p + r else 0.0}


def routing(t):
    out = {}
    ok = (t.routing_decision.loc[agreed.index] == agreed.routing_ground_truth)
    out["routing_agreed56"] = {"correct": int(ok.sum()), "n": len(ok), "pct": round(ok.mean() * 100, 1), "wilson95": wilson(int(ok.sum()), len(ok))}
    y = (agreed.should_escalate == "True")
    out["escalation_agreed56"] = prf(esc_flag(t).loc[agreed.index], y)
    hr = agreed[agreed.routing_ground_truth == "hr"]
    hk = int((t.routing_decision.loc[hr.index] == "hr").sum())
    out["hr_recall"] = {"found": hk, "n": len(hr), "wilson95": wilson(hk, len(hr))}
    for h in (1, 2):
        l, ye = label(h)
        okh = (t.routing_decision == l.loc[t.index])
        out[f"all70_annotator{h}"] = {"routing_pct": round(okh.mean() * 100, 1), "routing_correct": int(okh.sum()), "escalation": prf(esc_flag(t), ye.loc[t.index])}
    out["sent_to_human"] = int(esc_flag(t).loc[agreed.index].sum())
    return out, ok


def base(x): return str(x).split("/")[-1]


def retrieval(d, t):
    """Live retrieval: the search that actually ran. No draft/search (escalated before search) counts as a miss."""
    p1 = []; rec = []; rr = []
    for q, row in t.iterrows():
        rel = [base(x) for x in str(docs.loc[q, "relevant_doc_ids"]).replace(";", ",").split(",") if x.strip()]
        rows = d[(d.query_id == q) & d.retrieved_source_files.notna()]
        lists = [[base(s) for s in json.loads(r)] for r in rows.retrieved_source_files]
        if not lists:
            p1.append(0); rec.append(0.0); rr.append(0.0); continue
        first = lists[0]
        p1.append(int(bool(first) and first[0] in rel))
        merged = [s for l in lists for s in l[:4]]
        rec.append(len({s for s in merged if s in rel}) / len(rel))
        rank = next((i + 1 for i, s in enumerate(first) if s in rel), None)
        rr.append(1 / rank if rank else 0.0)
    return {"precision_at_1": round(np.mean(p1) * 100, 1), "p1_correct": int(sum(p1)), "recall_at_4": round(np.mean(rec) * 100, 1), "mrr": round(float(np.mean(rr)) * 100, 1), "n": len(t)}, np.array(p1)


_model = None


def groundedness(d):
    global _model
    from sentence_transformers import SentenceTransformer, util
    import compute_groundedness as cg
    if _model is None: _model = SentenceTransformer("all-MiniLM-L6-v2")
    rows = []
    for _, r in d[d.draft.notna() & (d.draft.astype(str).str.strip() != "")].iterrows():
        text = cg.extract_customer_response(r.draft)
        sents = [s.strip() for s in cg.SENTENCE_SPLIT.split(text) if len(s.strip()) > 15 and not cg.is_boilerplate(s.strip())]
        srcs = json.loads(r.retrieved_texts) if isinstance(r.retrieved_texts, str) else []
        if not sents: continue
        if not srcs:
            rows += [(r.query_id, r.domain_drafted, s, 0.0, False) for s in sents]; continue
        sim = util.cos_sim(_model.encode(sents, convert_to_tensor=True), _model.encode(srcs, convert_to_tensor=True)).max(dim=1).values.tolist()
        rows += [(r.query_id, r.domain_drafted, s, x, x >= cg.SIMILARITY_THRESHOLD) for s, x in zip(sents, sim)]
    return pd.DataFrame(rows, columns=["query_id", "domain", "sentence", "sim", "supported"])


def reply_quality(d):
    dd = d[d.draft.notna() & (d.draft.astype(str).str.strip() != "")].copy()
    for c in ["judge_overall_score", "judge_priority_tone_match_score", "judge_accuracy_score", "judge_groundedness_score"]:
        dd[c] = pd.to_numeric(dd[c], errors="coerce")
    g = groundedness(d)
    out = {"tickets_with_draft": int(dd.query_id.nunique()), "drafts": len(dd)}
    for dom, x in dd.groupby("domain_drafted"):
        gg = g[g.domain == dom]
        out[dom] = {"n": len(x), "overall": round(x.judge_overall_score.mean(), 2), "tone": round(x.judge_priority_tone_match_score.mean(), 2),
                    "sentences": len(gg), "grounded_pct": round(gg.supported.mean() * 100, 1) if len(gg) else None,
                    "unsupported": int((~gg.supported).sum())}
    return out, dd, g


def main(tags):
    summary = {}; cache = {}
    per = {}
    for tag in tags:
        d, t = load(tag)
        err = int(d.error.notna().sum()) if "error" in d else 0
        r, ok = routing(t)
        ret, p1 = retrieval(d, t)
        rq, dd, g = reply_quality(d)
        summary[tag] = {"tickets": len(t), "errors": err,
                        "classifier_sources": t.classification_source.value_counts(dropna=False).to_dict(),
                        "generic_category": int((t.category.astype(str).isin(["General Support", "General"])).sum()),
                        "cache_hits": int(t.cache_hit.astype(str).str.lower().eq("true").sum()),
                        "routing": r, "retrieval_live": ret, "reply_quality": rq,
                        "no_draft_tickets": int(len(t) - dd.query_id.nunique())}
        per[tag] = (t, ok, dd)
    b = tags[0]
    for tag in tags[1:]:
        t0, ok0, dd0 = per[b]; t1, ok1, dd1 = per[tag]
        bb = int((ok0 & ~ok1).sum()); cc = int((~ok0 & ok1).sum())
        comp = {"routing_agreed56_paired": {"old_right_new_wrong": bb, "old_wrong_new_right": cc, "mcnemar_exact_p": round(mcnemar(bb, cc), 4)}}
        m = dd0.merge(dd1, on=["query_id", "domain_drafted"], suffixes=("_a", "_b"))
        pt = {}
        for dom, x in m.groupby("domain_drafted"):
            for col in ("judge_overall_score", "judge_priority_tone_match_score"):
                y = x[[col + "_a", col + "_b"]].dropna(); df = y[col + "_b"] - y[col + "_a"]
                pt[f"{dom}_{col.replace('judge_', '').replace('_score', '')}"] = {"n": len(y), "mean_old": round(y[col + "_a"].mean(), 2), "mean_new": round(y[col + "_b"].mean(), 2),
                                                                                  "up": int((df > 0).sum()), "down": int((df < 0).sum()),
                                                                                  "wilcoxon_p": round(float(wilcoxon(df[df != 0]).pvalue), 3) if (df != 0).sum() > 0 else None}
        comp["reply_scores_paired"] = pt
        comp["classifier_agreement"] = {"same_priority": int((t0.priority == t1.priority).sum()), "same_sentiment": int((t0.sentiment == t1.sentiment).sum()), "n": len(t0)}
        summary[f"{b}_vs_{tag}"] = comp
    (RES / "ablation_summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps(summary, indent=1, default=str))


if __name__ == "__main__":
    main(sys.argv[1:])

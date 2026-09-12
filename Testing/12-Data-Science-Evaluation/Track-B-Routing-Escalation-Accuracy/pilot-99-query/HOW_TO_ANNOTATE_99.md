# Track B PILOT — How to annotate `data/routing_annotation_sample_99.csv`

This is the pilot round, on Track A's 99-query baseline set, run **before** the real 70-ticket round (see `../README.md`) — same "check a second, independent dataset first" principle used throughout this project.

Two of us (Ranuga, Sineth) each fill in the `human1_*`/`human2_*` columns **independently** — don't compare notes or look at each other's answers until both are done. You will NOT see what the real system actually decided for any of these queries; that's deliberate, so your answer reflects your own read of the query, not a guess at what the pipeline probably does.

## Every column, and what to do with it

| Column | What it means | Do you touch it? |
|---|---|---|
| `pair_id`, `query_id` | Row ID and which query this is | No — read-only |
| `query_text` | The actual query, word for word | No — this is what you're judging. (No priority or recommended-action fields exist for this dataset, unlike the 70-ticket round — judge from this text alone) |
| `track_a_domain` | The domain Track A's own annotation already agreed on for this query | No — read-only reference, don't re-decide this |
| `routing_ground_truth_mechanical` | Our best-guess final routing decision, computed automatically from `track_a_domain` | No — read-only. Trustworthy **unless** `routing_needs_annotation = yes` right next to it |
| `routing_needs_annotation` | `yes`/`no` flag telling you whether this row's routing decision actually needs your judgment | No — already filled in, just tells you whether to fill in the override column below |
| **`human1_should_escalate` / `human2_should_escalate`** | **Your yes/no answer**: should this query have gone to a human before any reply went out? | **Yes — fill in, every row** (whichever number is you) |
| **`human1_routing_ground_truth_override` / `human2_routing_ground_truth_override`** | **Your routing decision**, one of `technical`/`billing`/`both`/`hr`/`escalation` | **Yes — but only when `routing_needs_annotation = yes`.** Leave blank otherwise |
| `human1_notes` / `human2_notes` | Free text if a score needs explaining | Optional |

The two columns in bold are the only ones you actually write into. Everything else is there to give you context or is already filled in.

## What's already decided for you (don't re-do this)

`track_a_domain` and `routing_ground_truth_mechanical` are already filled in, carried over from Track A's own independent classification work. For most rows this mechanical value is trustworthy and you don't need to touch it — see below for the one case where it's just a placeholder guess.

## What you're actually annotating

**Every row: `should_escalate`.** Write `yes` or `no`. Ask yourself: *should this query have been handed to a human before any reply went out, rather than answesudo apt install vlc
red automatically?* Base this on the query text alone — this dataset doesn't have a Priority or Recommended Action field (the 70-ticket round does; see its own instructions). Things that lean toward `yes`: real anger/distress, a policy exception being requested, anything sounding like a repeat or escalated complaint, safety/legal-sounding language, or a query genuinely too vague to act on safely.

**Only rows marked `routing_needs_annotation = yes`: `routing_ground_truth_override`.** These are the genuinely unresolved cases — in this dataset, specifically queries where Track A found **no correct knowledge-base document exists at all** (`relevant_doc_ids: none`). The mechanical value shown for these is just a placeholder (whatever domain Track A guessed), not a real answer. Decide for yourself: given there's no good document to answer this with, should it go to `technical`, `billing`, `hr`, `both`, or `escalation`? Write exactly one of those five words.

Leave `routing_ground_truth_override` blank for every row where `routing_needs_annotation = no` — the mechanical value already stands for those.

Add a short note in `human1_notes`/`human2_notes` if something is genuinely unclear — not required, but useful if our two answers end up far apart.

## When you're done

Once **both** of us have filled in every `human1_should_escalate`/`human2_should_escalate`, and every `human1_routing_ground_truth_override`/`human2_routing_ground_truth_override` for the flagged rows, run:

```
python3 scripts/merge_routing_annotations_99.py
```

This checks how much we agree (kappa) and builds `data/routing_ground_truth_99.csv`. If it reports disputes, resolve each by hand — open `routing_disputes_99.txt`, agree on an answer together (discussion is fine at this stage, since the blind annotation part is already done), and edit `routing_ground_truth_99.csv` directly to replace `NEEDS_REVIEW` with the agreed value.

Then run:

```
python3 scripts/run_routing_evaluation_99.py
```

This is the actual test — it runs the real `routing_node.py`/`escalation_node.py` and reports how often they agree with what we decided. A weak result here means going back to those files before spending effort on the 70-ticket round, not the other way around.

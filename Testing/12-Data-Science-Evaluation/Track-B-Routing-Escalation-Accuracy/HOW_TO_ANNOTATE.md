# Track B FINAL — How to annotate `data/routing_annotation_sample.csv`

**Only start this after `pilot-99-query/` is fully scored and any fixes it found have been applied.** That pilot exists specifically to catch routing/escalation-rule problems before spending annotation effort here.

Two of us (Ranuga, Sineth) each fill in the `human1_*`/`human2_*` columns **independently** — don't compare notes until both are done. You won't see what the real system actually decided for any of these tickets.

## Every column, and what to do with it

| Column | What it means | Do you touch it? |
|---|---|---|
| `pair_id`, `query_id` | Row ID and which ticket this is | No — read-only |
| `query_text` | The actual ticket, word for word | No — this is what you're judging |
| `priority` | Real priority level from the support log (`Low`/`Medium`/`High`/`Critical`) | No — read-only, but use it: higher priority leans toward `should_escalate = yes` |
| `recommended_action` | What the original human agent noted should be done about this ticket | No — read-only, but the **strongest signal** for `should_escalate` (see below) |
| `track_a_domain` | The domain(s) Track A's own annotation already agreed on for this ticket | No — read-only reference, don't re-decide this |
| `routing_ground_truth_mechanical` | Our best-guess final routing decision, computed automatically from `track_a_domain` | No — read-only. Trustworthy **unless** `routing_needs_annotation = yes` right next to it |
| `routing_needs_annotation` | `yes`/`no` flag telling you whether this row's routing decision actually needs your judgment | No — already filled in, just tells you whether to fill in the override column below |
| **`human1_should_escalate` / `human2_should_escalate`** | **Your yes/no answer**: should this ticket have gone to a human before any reply went out? | **Yes — fill in, every row** (whichever number is you) |
| **`human1_routing_ground_truth_override` / `human2_routing_ground_truth_override`** | **Your routing decision**, one of `technical`/`billing`/`both`/`hr`/`escalation` | **Yes — but only when `routing_needs_annotation = yes`.** Leave blank otherwise |
| `human1_notes` / `human2_notes` | Free text if a score needs explaining | Optional |

The two columns in bold are the only ones you actually write into. Everything else is there to give you context or is already filled in.

## What's already decided for you

`track_a_domain` and `routing_ground_truth_mechanical` are carried over from Track A's own independent classification work — don't re-do that. `priority` and `recommended_action` come from the real support-ticket log; use them as context for judging escalation.

**One ticket, Q016, has `priority`/`recommended_action` = `UNKNOWN`.** Its query text couldn't be reliably matched back to a specific raw ticket (checked exact match, close-wording match, and a keyword search — none resolved it confidently, including the ticket its position in the list would predict). Rather than guess and risk attaching the wrong ticket's data, it's left blank. Judge `should_escalate` for this one row from its query text alone, the same way every row in the 99-query pilot had to be judged.

## What you're annotating

**Every row: `should_escalate`.** Write `yes` or `no`. The proposal's own definition: a ticket that names a policy problem, or an unresolved repeat issue, should have escalated. Use `priority` and `recommended_action` as real signal here — a `recommended_action` that says things like "escalate," "prioritize," "assign a dedicated followup," or that describes a process the current system can't do (e.g. a manual account fix, a refund exception) is a strong `yes`. A `recommended_action` that's just "tighten wording" or "confirm and reply" is a strong `no`.

**Only rows marked `routing_needs_annotation = yes`: `routing_ground_truth_override`.** In this dataset these are the 11 tickets where Track A found the ticket genuinely needs **both `billing` and `hr`** expertise — a combination the real system has no routing destination for today (only `technical`+`billing`, as `"both"`, exists). Decide: should this actually force into `billing`, force into `hr`, or is `escalation` the honest answer given there's no route that covers both? Write exactly one of: `technical`, `billing`, `both`, `hr`, `escalation`.

Leave `routing_ground_truth_override` blank for every row where `routing_needs_annotation = no`.

Add a short note in `human1_notes`/`human2_notes` if something needs explaining.

## When you're done

```
python3 scripts/merge_routing_annotations.py
```

Resolve any disputes it reports the same way Track A resolved its original 3 (open `routing_disputes.txt`, agree together, edit `routing_ground_truth.csv` directly). Then:

```
python3 scripts/run_routing_evaluation.py
```

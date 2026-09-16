# Comparative Research Paper — Clario vs. Classification-Only Ticket NLP

`main.tex` is a complete IEEE conference-format paper comparing:

1. A reproduction of Selvi et al.'s ticket categorization/prioritization methodology
   (`../README.md`, `../136404.pdf`) on our own 20,000-ticket LMS dataset, and
2. Clario's own production architecture (confidence-gated LLM classification,
   hedged keyword routing, adaptive RAG, LLM-as-judge), evaluated via Track A
   (retrieval quality, complete) and Track D (judge reliability, in progress).

Every number in the paper is copied from, and traceable to:
- `../README.md` (§§10–16 — the 20-model classification reproduction)
- `../../Testing/12-Data-Science-Evaluation/Track-A-Retrieval-Quality/TRACK_A_CONCLUSION.md`
- `../../Testing/12-Data-Science-Evaluation/Track-D-Judge-Reliability/README.md`

No numbers are invented. Where a comparison is not apples-to-apples (e.g. the
paper's binary priority task vs. our 4-class ordinal one), the paper says so
explicitly in the text and in the figure itself, rather than implying a
like-for-like result.

## How to compile

This machine has no local LaTeX toolchain, so the paper has **not** been
compiled here. It is written in standard `IEEEtran` (conference mode), which
Overleaf ships by default:

1. Create a new Overleaf project (or a local project if you install
   `texlive-latex-extra` + `texlive-publishers` for `IEEEtran.cls`).
2. Upload `main.tex` and the `figures/` folder, preserving the relative path
   (`figures/fig1_category_accuracy.pdf`, etc.).
3. Compile with pdfLaTeX. No BibTeX pass is needed — references are a manual
   `thebibliography` block, so a single compile pass resolves everything
   (you may need to compile twice for the `\ref`/`\label` cross-references
   inside the document itself to resolve, which is normal for any LaTeX
   document, not specific to this one).

## Regenerating the figures

All five figures are generated from hard-coded, source-cited numbers by
`generate_figures.py` (requires `matplotlib` + `numpy`):

```bash
python3 generate_figures.py
```

This overwrites the PDFs in `figures/`. Re-run it if any of the underlying
evaluation numbers change (e.g. once Track D's human scoring is complete and
`κ` values are available — see the caveats in Sec. VI-D / VIII of the paper).

## What's deliberately left out (and why)

Per the paper's own Limitations section, this is a **current-state** paper:

- Track D's weighted Cohen's κ (judge vs. human, human vs. human) is not yet
  computed — both human scoring passes are pending. The paper reports the
  score-clustering finding that surfaced while generating the input data, but
  explicitly does not claim a κ result it doesn't have.
- Track B (routing/escalation accuracy) and Track C (final response quality)
  are referenced only where they directly explain a Track D methodology
  choice; neither is a completed track yet.

When those tracks finish, update the relevant numbers/figures and the
Limitations/Future Work sections rather than starting a new paper — the
structure here is meant to absorb that follow-up work.

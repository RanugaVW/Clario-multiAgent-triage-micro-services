# Research Papers

Papers this evaluation's methodology is directly built on — full list in `DATA_SCIENCE_EVALUATION_PROPOSAL.md` §6/§12. This folder holds the one paper the strategy most directly comes from.

## `ARES_2311.09476.pdf`

**Saad-Falcon, J., Khattab, O., Potts, C., Zaharia, M. (2024). *ARES: An Automated Evaluation Framework for Retrieval-Augmented Generation Systems.* Stanford / Databricks / UC Berkeley. arXiv:2311.09476.**

This is where **Track D's entire design comes from**. ARES's core finding: an automatic LLM judge scoring a RAG system's responses can't just be trusted — it has to be checked against a small set of real human ratings first (the paper uses a few hundred), using prediction-powered inference to get a confidence interval on how much to trust the judge. That's exactly what Track D does: generate real drafts, score them with `ResponseJudge`, then have two humans independently score the same drafts and check whether the judge and the humans actually agree (weighted Cohen's κ + Spearman) — before using that judge's scores for anything downstream (like Track C).

The "~150 examples" figure referenced throughout Track D's README/scripts (as the honest caveat on our own 82- and 99-pair sample sizes) is ARES's own benchmark scale for this exact calibration step.

Two other foundational papers (not downloaded here, but citable the same way): **RAGAS** (Es et al., 2023, arXiv:2309.15217 — the retrieval/faithfulness metrics behind Tracks A and C) and **"Judging LLM-as-a-Judge with MT-Bench"** (Zheng et al., 2023, arXiv:2306.05685 — position bias in LLM judges, part of why `PAIRWISE_USER_PROMPT_TEMPLATE` in `response_judge.py` swaps response order between passes).

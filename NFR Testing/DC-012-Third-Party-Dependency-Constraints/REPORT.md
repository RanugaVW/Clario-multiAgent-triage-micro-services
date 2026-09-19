# DC-012 — Third-Party Dependency Constraints

**Status before:** 🟡 Partial — versions were pinned, but there was no process to evaluate updates and nothing documenting the policy.
**Status after:** ✅ Automated, CI-gated update proposals for every active ecosystem, a written policy, and a CI guardrail so it cannot silently rot.
**Database changes:** none.

## What was added
- **`.github/dependabot.yml`** — weekly proposals for npm (`frontend`), Maven (3 Java services), pip (3 Python services, `clario-ml-sidecar`, `ml_finetuning`, `Visualizer/relay`),
  Docker (8 Dockerfiles) and GitHub Actions. Minor+patch grouped per ecosystem; **major upgrades of Next.js, React, Spring Boot and Spring Cloud are ignored** (they need a planned migration).
- **`DEPENDENCIES.md`** — where each ecosystem's versions live, the update/evaluation flow (Dependabot PR → CI must pass → human review; nothing auto-merged or deployed), the AI-provider integration-seam rule, and known exceptions.
- **`tests/contracts/test_dependency_management.py`** (runs in the existing CI *Contract tests* job; `pyyaml` added to that job's install line): every tracked manifest is registered; every entry points at a real manifest; no duplicates; weekly schedule; core majors stay ignored; policy doc exists.

## Verification
- `pytest tests/contracts`: **25 passed** (23 cases from the new file + the 2 existing contract tests).
- **Mutation checks (reverted):** removing the api-gateway Maven entry → fails; a typo'd directory (`/fronted`) → 2 fail; un-ignoring `next` majors → fails.
- The existing `check_architecture.py` PR guard is unaffected (Dependabot PRs each touch one directory).

## Things you must do / know
- **Dependabot must be enabled on the GitHub repo** (Settings → Code security → Dependabot). The file alone does nothing where it is switched off — I cannot verify that from here.
- **Not verified:** that GitHub accepts every entry (only YAML structure and directory existence were checked locally). Its *Insights → Dependency graph → Dependabot* tab shows parse errors.
- **Finding:** root `requirements.txt` is **UTF-16** (a PowerShell `pip freeze`), so it is excluded with the reason recorded in the test. Re-saving as UTF-8 and adding a `pip` entry for `/` would include it — I did not change that file.
- The test enumerates manifests via `git ls-files`, so it sees only tracked files (correct for CI).
- Dependabot PRs will likely surface the existing `npm audit` findings (next, postcss, nanoid) as upgrade proposals.

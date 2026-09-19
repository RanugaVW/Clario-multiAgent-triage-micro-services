# DC-012 — Third-Party Dependency Constraints

**Status before:** 🟡 Partial — versions were pinned, but the update/evaluation process was undocumented.
**Status after:** 🟡→✅ (process + guardrail, **manual by design**) — a written policy and a CI guardrail. There is **no automation**: updates are made by hand from a maintainer's account.
**Database changes:** none.

> **History (2026-09-20):** an earlier version of this item added Dependabot. It opened ~25 pull requests under a bot identity at once, which also queued the project's own CI for a long time. The maintainer does not want bots in this repository, so Dependabot was **removed entirely** (config deleted, its PRs closed, its branches deleted). This report describes what replaced it.

## What exists
- **`DEPENDENCIES.md`** — where each ecosystem's versions live (npm, Maven, pip, Docker, GitHub Actions, by directory), and how an update is made and evaluated: decide deliberately, one concern per change, run the same checks CI runs, CI green before it reaches `main`, majors are planned migrations, AI providers only through the integration seam, record it in the commit message.
- **`tests/contracts/test_dependency_management.py`** (runs in the existing CI *Contract tests* job): every tracked manifest directory (`pom.xml`, `package.json`, `requirements*.txt`, `Dockerfile`) must be listed in `DEPENDENCIES.md`; the parser sees the known manifests; the policy names every ecosystem and the CI gate; **no bot configuration (`dependabot.yml`, Renovate) may be committed**.

## Verification
- `pytest tests/contracts`: **33 passed**.
- Mutations (reverted): removing a directory from the inventory → fails; adding a `.github/dependabot.yml` → fails.
- CI on `main` was green with the Dependabot version of this item; the manual version is verified locally (the contract job needs only `pytest` again — `pyyaml` was removed from the workflow).

## Honest limits
- **No automation means no reminders.** Nothing tells you a library is outdated or has an advisory; you must look (`npm audit`, `./mvnw versions:display-dependency-updates`, `pip list --outdated`). `npm audit` currently reports advisories in `next`, `postcss`, `nanoid` and `sharp` that are worth a deliberate update.
- The guardrail checks that the *inventory is documented*, not that versions are current.
- GitHub's separate **Dependabot security updates** and **alerts** are repository settings, not files. Automatic security-update PRs were already **disabled** on this repository (verified via the API: `enabled: false`); no setting was changed. Vulnerability *alerts* (notifications only) are the maintainer's choice in Settings → Code security.
- The root `requirements.txt` is UTF-16 and remains outside the process; `clario-app/`, `legacy/`, `Testing/` are excluded.

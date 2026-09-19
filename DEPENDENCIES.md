# Dependency management (SRS DC-012)

How third-party libraries, frameworks and base images are versioned, documented and updated in Clario.
Updates are made **by hand, by the maintainers, from their own accounts**. No bot opens pull requests or commits to this
repository (Dependabot/Renovate are deliberately not used).

## Where versions are documented

| Ecosystem | Manifest directory | Version control |
|---|---|---|
| npm | `frontend/` (`package.json` + `package-lock.json`) | Ranges in the manifest, exact resolution in the committed lockfile |
| Maven | `services/api-gateway/`, `services/ticket-core-service/`, `services/agent-review-service/` (`pom.xml`) | Spring Boot parent + Spring Cloud BOM pin the framework line; other versions explicit |
| pip | `services/ai-orchestrator-service/`, `services/nlp-classifier-service/`, `services/voice-to-text-service/`, `clario-ml-sidecar/`, `ml_finetuning/`, `Visualizer/relay/` (`requirements.txt`) | Exact `==` pins (some `>=` lower bounds in `ml_finetuning/`) |
| Docker | the `Dockerfile` in `services/api-gateway/`, `services/ticket-core-service/`, `services/agent-review-service/`, `services/ai-orchestrator-service/`, `services/nlp-classifier-service/`, `services/voice-to-text-service/`, `clario-ml-sidecar/`, `ml_finetuning/` | Explicit base-image tags |
| GitHub Actions | `.github/workflows/*.yml` | Major-version tags |

## How an update is made and evaluated

1. **Decide deliberately.** Update because there is a reason (a security advisory, a bug fix, a needed feature, end of support) — not because a newer number exists. Check `npm audit` / `./mvnw versions:display-dependency-updates` / `pip list --outdated` when reviewing.
2. **One concern per change.** Bump one library or one closely related group, on its own commit (or branch and pull request from your own account).
3. **Prove compatibility before it reaches `main`.** Run the same checks CI runs: `npm run lint && npm run test` for the frontend, `./mvnw test` per Java service, `python -m pytest tests` per Python service, `pytest tests/contracts`. CI (`.github/workflows/ci.yml`) must be green on the commit.
4. **Major upgrades** (Next.js, React, Spring Boot, Spring Cloud, Python libraries with breaking releases) are planned migrations with their own change and test pass, never a drive-by bump.
5. **External AI providers** are only reached through the integration modules in the orchestrator/sidecar (not called ad hoc from feature code), so a provider or SDK change is confined to that seam.
6. **Record it.** The commit message states what changed and why; the manifest and lockfile are the version record.

## Guardrail
`tests/contracts/test_dependency_management.py` fails CI if a dependency manifest is added to the repository without its directory being listed in this document, so the inventory above cannot silently go stale.

## Known exceptions
- The root `requirements.txt` is a UTF-16 `pip freeze` and is not part of the managed set; re-save it as UTF-8 if it should be.
- `clario-app/` (legacy monolith), `legacy/`, `Testing/` and `.worktrees/` are outside this process.

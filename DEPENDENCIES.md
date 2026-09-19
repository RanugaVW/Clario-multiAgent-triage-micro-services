# Dependency management (SRS DC-012)

How third-party libraries, frameworks and base images are versioned, documented and updated in Clario.

## Where versions are documented

| Ecosystem | Manifest(s) | Version control |
|---|---|---|
| npm | `frontend/package.json` + `package-lock.json` | Ranges in the manifest, exact resolution in the lockfile (committed) |
| Maven | `services/{api-gateway,ticket-core-service,agent-review-service}/pom.xml` | Spring Boot parent + Spring Cloud BOM pin the framework line; other versions explicit |
| pip | `services/{ai-orchestrator,nlp-classifier,voice-to-text}-service/requirements.txt`, `clario-ml-sidecar/`, `ml_finetuning/`, `Visualizer/relay/` | Exact `==` pins |
| Docker | each service's `Dockerfile` (base image tag) | Explicit tags |
| GitHub Actions | `.github/workflows/*.yml` | Major-version tags |

## How updates are proposed and evaluated

1. **Dependabot** (`.github/dependabot.yml`) opens pull requests weekly for every ecosystem above. Minor and patch updates are grouped per ecosystem, and **at most one PR is open per manifest directory** — each PR starts a full CI run, and the first activation (unbounded) opened ~25 at once and queued the project's own CI behind them.
2. **CI must pass** (`.github/workflows/ci.yml`: frontend lint + tests, Java tests per service, contract tests). A failing update PR is not merged — this is the
   compatibility evaluation before deployment. Nothing is auto-merged or auto-deployed.
3. **Major upgrades are never proposed by the bot** (all ecosystems); Next.js, React, Spring Boot and Spring Cloud are additionally listed by name. A major is a planned migration with its own change and test pass — enable one deliberately by removing its ignore rule for the duration of the migration.
4. **External AI providers** are only reached through the integration modules in the orchestrator/sidecar (not called ad hoc from feature code), so a provider or SDK change is confined to that seam.
5. **Guardrail:** `tests/contracts/test_dependency_management.py` fails CI if a new manifest is added without being registered with Dependabot, or if the config points at something that no longer exists.

## Known exceptions
- The root `requirements.txt` is a UTF-16 `pip freeze`; it is not registered because Dependabot may misread it. Re-saving it as UTF-8 and adding a `pip` entry for `/` would bring it in.
- `clario-app/` (legacy monolith), `legacy/` and `Testing/` are outside the automated process.
- Dependabot must be enabled for the repository (Settings → Code security → Dependabot). The config file alone does nothing on a repo where it is switched off.

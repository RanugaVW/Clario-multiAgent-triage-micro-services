# SUP-010 — Operational Documentation ("API documentation shall remain synchronized with implemented interfaces")

**Status before:** ✅ Implemented for deployment/CI docs (`DOCKER.md`, `CI.md` were verified accurate); no API documentation existed.
**Status after:** ✅ API documentation added and enforced against drift.

Full details and evidence: `NFR Testing/DC-015-API-Design-Constraints/README.md`.

The sub-requirement "API documentation shall remain synchronized with implemented interfaces" is met
mechanically: the spec is generated from the code, and `OpenApiContractTest` fails the build if the generated
spec differs from the committed snapshot. "Administrator documentation" and "AI workflow documentation" are
outside this change.

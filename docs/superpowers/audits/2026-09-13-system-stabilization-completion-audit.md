# System Stabilization Completion Audit

**Audited:** 2026-09-13

This audit evaluates the acceptance criteria in `2026-09-11-system-stabilization-and-architecture-governance-design.md` against current local source and fresh verification. It is not a completion declaration.

| Acceptance criterion | Current evidence | Status |
| --- | --- | --- |
| Backend tests, frontend tests, production build | `python -m pytest tests -q`: 1962 passed, 12 skipped (366.27 s); `npm run test:all`: 28 Vitest files / 93 tests and 508 contract tests; `npm run test:bundle`: build plus manifest baseline passed | Locally proven |
| CI is fail-closed | `cloud-p1b2a-gate.yml` runs full backend tests, frontend tests/build, bundle baseline, PostgreSQL migration gate and Compose health checks. A source search found no allow-failure/whitelist/`continue-on-error` configuration. | Configuration proven; remote run unproven |
| Alembic/ORM and fresh SQLite/PostgreSQL schema alignment | Fresh backend suite includes the database safety, Alembic and meeting-document-source governance tests. The CI workflow contains a PostgreSQL 16 empty-database `alembic upgrade head` gate. | SQLite/static coverage proven; live PostgreSQL unproven locally |
| Core business smokes and rejected permission paths | Broad route/service permission regression tests pass locally. CI now runs `scripts/ci_compose_business_smoke.py` after nginx health: it initializes the disposable migrated database through the public setup API, logs in through nginx, reads project/task/update/confirmation/meeting/issue/achievement/archive paths, and verifies ordinary-user project creation is denied. | Configuration and local contract proven; remote run unproven |
| Three largest Router domains have clear service boundaries | Project close workflow, confirmation review/writeback workflows, and meeting change-set review workflow have direct boundary tests and their current full backend suite passes. | Locally proven |
| Historical naming is confined | Project-role reads are confined to `app.compatibility.project_roles`; frontend project-name display/grouping is confined to `frontend/src/compatibility/projectNames.ts`; backend project-name resolution is now owned by `app.compatibility.project_names` and all production callers import it directly. Identity, behavior and source-boundary tests pass. Historical model/schema fields remain as compatibility contracts. | Runtime path proven; contract fields retained |
| Performance baseline and lazy heavy dependency | `frontend/performance/bundle-baseline.json` and the fail-closed manifest analyzer passed: initial JS 302987 B, CSS 97388 B, largest route 95588 B, ExcelJS 940194 B with `isInitial: false`. | Locally proven |
| Hygiene | `git status --short` was clean after the compatibility containment commits; generated build output remains ignored. | Locally proven |

## Current blockers to overall completion

1. Docker Desktop's Linux engine is unavailable locally (`npipe:////./pipe/dockerDesktopLinuxEngine`), so a genuine PostgreSQL 16 migration and Compose business smoke cannot be run in this worktree.
2. No remote CI run for the current commits has been observed. Local source confirms the gate configuration, but not its execution on a hosted PostgreSQL service.
3. Historical name fields are still present in database models, schemas and serialized payloads for backward compatibility. Removing them would be a separate API/data migration and is intentionally not part of this containment change.

## Next implementation priority

The backend project-name fallback decision is now centralized and characterized with ID-first/conflict tests. Remaining completion work is evidence collection: run the existing PostgreSQL/Compose/authenticated nginx gate on hosted CI, because Docker Desktop's Linux engine is unavailable locally.

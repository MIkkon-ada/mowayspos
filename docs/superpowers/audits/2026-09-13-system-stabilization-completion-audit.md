# System Stabilization Completion Audit

**Audited:** 2026-09-13

This audit evaluates the acceptance criteria in `2026-09-11-system-stabilization-and-architecture-governance-design.md` against current local source and fresh verification. It is not a completion declaration.

| Acceptance criterion | Current evidence | Status |
| --- | --- | --- |
| Backend tests, frontend tests, production build | `python -m pytest tests -q`: 1953 passed, 12 skipped (387.45 s); `npm run test:all`: 27 Vitest files / 89 tests and 507 contract tests; `npm run test:bundle`: build plus manifest baseline passed | Locally proven |
| CI is fail-closed | `cloud-p1b2a-gate.yml` runs full backend tests, frontend tests/build, bundle baseline, PostgreSQL migration gate and Compose health checks. A source search found no allow-failure/whitelist/`continue-on-error` configuration. | Configuration proven; remote run unproven |
| Alembic/ORM and fresh SQLite/PostgreSQL schema alignment | Fresh backend suite includes the database safety, Alembic and meeting-document-source governance tests. The CI workflow contains a PostgreSQL 16 empty-database `alembic upgrade head` gate. | SQLite/static coverage proven; live PostgreSQL unproven locally |
| Core business smokes and rejected permission paths | Broad route/service permission regression tests pass locally. CI now runs `scripts/ci_compose_business_smoke.py` after nginx health: it initializes the disposable migrated database through the public setup API, logs in through nginx, reads project/task/update/confirmation/meeting/issue/achievement/archive paths, and verifies ordinary-user project creation is denied. | Configuration and local contract proven; remote run unproven |
| Three largest Router domains have clear service boundaries | Project close workflow, confirmation review/writeback workflows, and meeting change-set review workflow have direct boundary tests and their current full backend suite passes. | Locally proven |
| Historical naming is confined | Project-role read fallback is confined to `app.compatibility.project_roles`; the 2026-09-13 inventory now distinguishes physical/API fields, adapters, migrations and runtime fallbacks. The next independently scoped containment is frontend project-name display/grouping. | Partially proven |
| Performance baseline and lazy heavy dependency | `frontend/performance/bundle-baseline.json` and the fail-closed manifest analyzer passed: initial JS 302987 B, CSS 97388 B, largest route 95588 B, ExcelJS 940194 B with `isInitial: false`. | Locally proven |
| Hygiene | `git status --short` was clean after the compatibility containment commits; generated build output remains ignored. | Locally proven |

## Current blockers to overall completion

1. Docker Desktop's Linux engine is unavailable locally (`npipe:////./pipe/dockerDesktopLinuxEngine`), so a genuine PostgreSQL 16 migration and Compose business smoke cannot be run in this worktree.
2. No remote CI run for the current commits has been observed. Local source confirms the gate configuration, but not its execution on a hosted PostgreSQL service.
3. The project-role compatibility leak is fixed and an inventory now defines the allowed categories, but the frontend project-name runtime fallback and backend resource-family fallbacks have not yet been contained.

## Next implementation priority

Implement the frontend project-name compatibility containment plan, then characterize backend resource-family fallbacks. PostgreSQL and authenticated nginx smoke execution remain external evidence until Docker or hosted CI is available.

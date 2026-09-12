# Historical Naming Inventory

**Audited:** 2026-09-13
**Scope:** `bowei_ai_dashboard/app` and `frontend/src` runtime source. This is an inventory, not a claim that the global historical-naming criterion is complete.

## Classification rule

Historical names are not a single category. A match is allowed only when it is a physical schema/API compatibility definition, an explicitly named compatibility adapter, a migration/import path, or an immutable historical snapshot. All other runtime reads require a named owner and a containment plan.

| Category | Current examples | Disposition |
| --- | --- | --- |
| Physical database and API mirror | SQLAlchemy `special_project` / `related_special_project`, Pydantic schemas, project rename safety checks | Retain. These preserve existing data and public DTOs; new identity decisions must use `project_id`. |
| Central backend compatibility | `app/compatibility/project_roles.py` | Retain and test. The project-role fallback is already isolated; strict services and the Router no longer receive `allow_legacy`. |
| Migration/import or archival data | `excel_importer.py`, `ai_legacy_migration.py`, revision snapshots | Retain under explicit migration/import/snapshot ownership. Do not use as new business identity sources. |
| Controlled display resolution | `permissions.resolve_project_context`, Router serializers that resolve ID before project-name mirror | Retain temporarily, then audit by resource type. It is a runtime compatibility boundary but remains distributed across task, issue, achievement and meeting routes. |
| Frontend display and grouping | `frontend/src/domain/projectDisplay.ts`; `TaskManagementPage.tsx`; `exportTasksExcel.ts` | First containment subproject. Move historical-name reads and grouping fallback into `frontend/src/compatibility/projectNames.ts`. |
| Authentication migration | `legacy_password_login_enabled`, legacy password file users | Retain behind the existing explicit configuration gate; not a project-name concern. |

## Exact findings that determine next work

1. `special_project` and `related_special_project` are physical columns on multiple established records. Removing or renaming them now would break existing databases and public payloads, contrary to the stabilization design.
2. The backend already has `resolve_project_context`, which resolves `project_id` and names. This is the correct candidate boundary for a later resource-by-resource backend consolidation; this audit does not change it without characterisation tests.
3. The frontend has an existing ID-first resolver, but it is incorrectly placed as a general domain primitive and task grouping duplicates a `legacy:` key convention in two files. This is a safe, independently testable first step.
4. Historic name fields also exist in frontend DTO types because they are observable API fields. Type declarations are contract definitions, not authorization or identity logic; they remain until a separately versioned API migration is authorized.

## Allowed locations after the first subproject

- Database models, Alembic migrations, API schemas/types and import/migration code that preserve an existing external contract.
- `app/compatibility/` and `frontend/src/compatibility/` adapters, with direct tests.
- Historical snapshots and their tests.
- A documented, ID-first backend project-resolution adapter while resource-route consolidation is pending.

No new Router/page/export code may introduce direct name-based project identity checks or a new `legacy:` grouping convention.

## Sequenced follow-up

1. Implement the frontend containment plan next.
2. Characterize and consolidate backend task/issue/achievement/meeting project-name serialization around the existing ID-first resolution adapter, one resource family at a time.
3. Only after each runtime family is contained, decide whether a versioned database/API migration can retire physical mirrors. That decision requires PostgreSQL migration proof and data-backfill/rollback design.

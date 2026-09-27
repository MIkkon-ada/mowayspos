# V2 Role Based Workbench Implementation Plan

> This plan is executed directly by the current agent in the existing workspace. Existing user changes must be preserved; do not delegate work.

**Goal:** Make V2 home and navigation reflect the distinct daily work of company leaders, project managers, and project members, while keeping projects as the shared work context.

**Architecture:** Reuse authenticated user identity, visible project roles, dashboard governance data, and the existing personal task flow. Keep route permissions enforced by existing guards and backend APIs. Update home composition, labels, project selection cues, and role-oriented navigation without adding unconfirmed assignment or dispatch authority.

**Tech Stack:** React 19, TypeScript, React Router, Tailwind CSS, existing V2 APIs and domain helpers.

---

## Scope

This implementation round covers the role-aware workbench and navigation only. It will not add backend dispatch commands, new permission grants, new project health scoring, or rewrite the work progress spreadsheet whose files currently contain uncommitted user changes. The separate design proposal records those later phases.

## Files to inspect and likely modify

- `frontend-v2/src/pages/DashboardPage.tsx`: role detection, scope defaults, and home composition.
- `frontend-v2/src/features/dashboard/GovernanceDashboardContent.tsx`: leader overview, action list, project health and language hierarchy.
- `frontend-v2/src/layouts/ProjectLayout.tsx`: default route and project context behavior.
- `frontend-v2/src/components/Sidebar.tsx`: desktop navigation group labels/order and project entry visibility.
- `frontend-v2/src/components/MobileAppNavigation.tsx`: mobile parity with primary workbench/project/work destinations.
- `frontend-v2/src/pages/MyTasksPage.tsx`: member daily action emphasis and project context labels.
- `frontend-v2/src/pages/MemberProjectsPage.tsx`: project list as browse/switch destination, not universal landing page.
- `frontend-v2/src/features/dashboard/governanceDashboard.ts`: display aggregation and explanations; avoid inventing health rules.

Before edits, inspect existing tests and component contracts around these files. Do not modify `PlanTableViewV2.tsx`, `planTableColumns.ts`, `planTableExcelV2.css`, `TaskManagementPage.tsx`, or `exportPlanTableExcel.ts` in this round because they already contain user changes.

## Task 1: Define stable role-oriented home modes

- Use explicit global visibility flags (`is_ceo`, `can_view_all`, `is_tech_admin`) for the company-wide leader view; do not infer company-wide authority from a project-level coach role alone.
- For project leaders/PMs, use their visible project roles to build a project-focused overview.
- For members, make assigned work the primary home content and keep project context visible.
- For users with multiple roles, expose a clear view switch while retaining both the global and personal/project work destinations.
- Keep project selection deterministic: a single available project may open directly; multiple projects should use a summary/selector, never an arbitrary first project.

## Task 2: Rework the leader workbench around overview → action

- Place company-wide project health/attention summary before the governance action queue.
- Label the action queue in plain Chinese and show project, accountable person, due date or wait duration, and action kind where available.
- Provide a complete-list destination or count when the home only shows a short preview.
- Link each project or action to its existing project/confirmation/coordination route.
- Keep the current authority boundary: show existing decisions and coordination workflows; do not introduce direct reassignment or resource allocation.
- Do not represent completion rate as a validated health score. Show a neutral progress snapshot or clearly named heuristic until health rules are agreed and implemented consistently.

## Task 3: Make PM and member homes project-contextual

- For PMs, surface managed projects and their actionable work (late, blocked, due soon, awaiting confirmation) before generic module links.
- For members, surface assigned tasks with project and workstream context, direct task detail, and report action.
- Keep “我的项目” as project browse/switch; do not make it the boss landing page.
- Distinguish empty work from loading, partial API failure, and permission restriction.

## Task 4: Align desktop and mobile navigation

- Group navigation into workbench, projects, and collaboration/management destinations.
- Keep labels concise and Chinese; avoid duplicated top-level destinations where project context already offers the same operation.
- Keep route destinations and permission guards intact.
- Ensure mobile navigation retains the most common actions and visible active state.

## Task 5: Refine visual hierarchy and business language

- Reduce competing cards and decorative treatments on the workbench.
- Establish consistent page title, section heading, primary action, supporting data, and status treatment.
- Replace unnecessary English interface terms in governance content with agreed business Chinese; preserve exact entity distinctions.
- Use text with status colors and provide status reasons where data supports them.

## Verification

- Run the V2 production build (`npm run build`) to catch TypeScript and bundling errors.
- Do not run or add tests unless the user asks for tests/verification; inspect the existing test contracts and avoid breaking their public semantics.
- If the local V2 services are available, inspect the changed workbench at desktop and narrow viewport sizes and confirm navigation destinations remain valid.
- Report any deferred decision where accurate behavior depends on an unconfirmed business rule.

## Out of scope for this round

- Backend or database changes.
- Boss-issued dispatch commands, reassignment, or cross-project resource allocation.
- New health scoring/thresholds without an approved business definition.
- Broad rewrite of the work progress spreadsheet, which has active uncommitted user work.
- Committing or discarding any existing workspace changes.

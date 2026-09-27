# 负责人完善项目计划工作台改进实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. The user’s project instruction forbids subagents unless the user explicitly authorizes them; execute in the current session without delegation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the project owner’s plan completion page clearly communicate who is acting, what stage the project is in, what must be completed, and who reviews it next.

**Architecture:** Keep the existing V2 route, role checks, draft data model, owner submission API, enterprise coach review, and execution lifecycle intact. Improve the page’s state-specific copy, information density, project overview readability, and field guidance inside the current workbench; do not change permissions or backend workflow.

**Tech Stack:** React 19, TypeScript, React Router, Tailwind CSS, existing project APIs and lifecycle/permission helpers.

---

## Confirmed workflow and boundaries

1. A project manager/admin creates the project, configures its team and dispatches it.
2. The project owner (`owner`) completes the work plan: workstreams, key tasks, assignees/helpers, time ranges, and evaluation indicators.
3. The owner submits the draft. The project enters `pending_review` and goes to the enterprise coach (`project_ceo`) for review.
4. The coach approves the project into execution or returns it to the owner for changes. During execution, key-task assignees and helpers perform work and submit progress; project leadership follows up.

The screenshot is an example of a dispatched project with a sparse/placeholder plan. Its displayed project name, dates, people, and counts are sample data, not product requirements. Existing server-side authorization and lifecycle validation remain authoritative. This plan does not add or alter role grants, required submission fields, review behavior, or project status transitions.

## Files to inspect and likely modify

- `frontend-v2/src/features/settings/OwnerSubmitModal.tsx`: state-specific page heading, next-step explanation, plan editing structure, submission feedback, and validation focus.
- `frontend-v2/src/pages/ProjectOwnerSubmitPage.tsx`: route-level loading/error/permission state and successful-submit behavior.
- `frontend-v2/src/features/settings/ProjectsMgmtSection.tsx`: entry label and lifecycle copy, only if needed to keep entry and destination wording consistent.
- `frontend-v2/src/styles.css`: scoped owner-submit layout and responsive styles; avoid broad global styling changes.
- Existing owner-submit layout/readability/route tests under `frontend-v2/src/features/settings/` and `frontend-v2/tests/`: inspect current contracts before changing the page.

Do not change `bowei_ai_dashboard/app/routers/projects.py`, project lifecycle permissions, API payload semantics, or task execution pages unless implementation inspection reveals a concrete mismatch with the confirmed flow; if so, document it rather than broadening scope without approval.

## Task 1: Align page language with the lifecycle stage

- [ ] Inspect how `OwnerSubmitModal.tsx` derives `projectStatus` and `canEditProject`, and how `ProjectOwnerSubmitPage.tsx` handles successful submission.
- [ ] Render a clear owner-facing title for editable `dispatched` and `returned` states, and a distinct read-only/review-waiting explanation for non-editable states. Do not show an editable “fill/submit” framing when editing is unavailable.
- [ ] Explain the next handoff in one short sentence: the project owner submits the plan, then the enterprise coach reviews it; after approval the project enters execution.
- [ ] Make the primary button label describe the actual action, such as “提交计划，送企业教练审核” for an editable draft. Keep the existing backend transition and toast semantics unchanged.
- [ ] Ensure the project list entry “完善项目计划” and the page title/subtitle describe the same owner action. Preserve “修改项目计划” for returned plans if that distinction exists in the current entry logic.

## Task 2: Rebalance the workbench for desktop and narrow screens

- [ ] Inspect the current screenshot-scale layout rules in `OwnerSubmitModal.tsx` and the scoped owner-submit CSS in `styles.css`.
- [ ] Reduce excess vertical padding and minimum heights in the active workstream detail so the goal, acceptance criteria, process, schedule, and key-task table are visually connected and more of the editable plan is visible in a standard desktop viewport.
- [ ] Keep project overview as supporting context and the work-plan editor as the primary area. Let long project values wrap; do not clip date ranges or force users to scroll horizontally for the main task fields on common desktop widths.
- [ ] On narrow screens, preserve a usable stacked layout and allow the task table to scroll within its own region where required.
- [ ] Retain the current fixed footer and ensure page content can scroll fully above it without being obscured.

## Task 3: Clarify project context and plan field meanings

- [ ] Present project dates as a wrapping/compact range so both endpoints remain readable.
- [ ] Distinguish “项目目标” (overall project outcome) from “重点工作目标” (result expected from this workstream), “重点工作验收标准/关键成果” (workstream completion evidence), and “关键任务评价指标” (how the individual task will be judged).
- [ ] Add brief helper text or examples at the point of entry instead of relying only on ambiguous labels/placeholders.
- [ ] Keep owner, coordinator, enterprise coach, and member counts visibly distinct; show “未配置”/zero as factual context without inventing a submission blocker.
- [ ] Do not make project code, coordinator assignment, member count, workstream goal, or evaluation indicator newly mandatory. Keep the existing required-field rules: at least one named workstream, at least one named key task, and an assignee for every submitted key task, as enforced by the current UI/API.

## Task 4: Make incomplete work and submission errors actionable

- [ ] Summarize plan completion with visible counts for named workstreams and key tasks, plus tasks still missing an assignee; do not present the count as a readiness score.
- [ ] Preserve existing AI draft import/merge behavior and its confirmation step.
- [ ] When submission validation fails, move focus or scroll to the relevant field/row and provide a specific message without discarding the draft.
- [ ] Keep loading, people-list failure, permission restriction, and lifecycle conflict distinguishable from an empty plan.
- [ ] Confirm that a successful submission still enters `pending_review`, gives the owner clear confirmation that the enterprise coach is next, and prevents duplicate submissions while the AI audit retry is pending.

## Task 5: Verify the owner handoff page

- [ ] Review existing owner-submit route, layout, readability, AI integration, and project workflow test contracts; update only assertions that encode intentionally changed wording/layout.
- [ ] Build the V2 frontend to catch type and bundle regressions.
- [ ] Exercise the page in dispatched, returned, pending-review/read-only, loading, validation-error, and successful-submit states using available local services or focused fixtures.
- [ ] Check a desktop viewport and a narrow viewport for readable project dates, visible key-task fields, footer access, and no page-level horizontal overflow.
- [ ] Inspect every changed JSX direction control and use the project’s SVG icon components for arrows; do not use Unicode or text glyph arrows.
- [ ] Report any behavior that could not be verified because the corresponding role/account or backend state is unavailable.

## Out of scope

- Changing who creates/dispatches projects or who owns plan drafting, coach review, key-task execution, or progress reporting.
- Changing role permissions, lifecycle transitions, required submission data, review actions, notification rules, or audit semantics.
- Adding direct task reassignment, project scheduling, or execution features to this plan-entry page.
- Reworking unrelated project-management, work-progress, dashboard, or AI-import flows.
- Removing or rewriting the existing user changes in the shared worktree.

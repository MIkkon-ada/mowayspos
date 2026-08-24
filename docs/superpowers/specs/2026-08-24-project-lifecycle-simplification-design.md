# Project Lifecycle Simplification Design

## 1. Goal

Simplify the lifecycle shared by all project types. Remove “dispatch” and “kickoff” as independent lifecycle gates while preserving the real governance controls: project-plan submission, project-coach review, execution confirmation, close review, and archive.

The target is to reduce the number of pre-execution handoffs without weakening role boundaries or auditability.

## 2. Current Context

The current lifecycle contains these states:

```text
draft → dispatched → pending_review → pending_kickoff → active
       → pending_close → ended → archived
```

The current flow separates two notifications/actions from substantive approvals:

- `dispatch` changes a project from `draft` to `dispatched`, although its main business effect is notifying the owner.
- `approve` moves the project to `pending_kickoff`, and a separate kickoff action is needed before the project is treated as executing.

The project data model already separates company-level roles from project-level roles. Company CEO / super admin manage the project entry and team setup. The project-level `project_ceo` role owns project review; being a company CEO alone must not grant project-coach review rights.

## 3. Target Lifecycle

```text
draft → pending_review → active → pending_close → ended → archived
  ↑          ↓
  └──── returned
```

### State meanings

| State | Meaning | Primary next actor |
|---|---|---|
| `draft` | Project entry exists, required team is configured, owner may complete the plan | Project owner / PM |
| `pending_review` | Owner has submitted the project plan for review | Project coach |
| `returned` | Coach returned the plan with required changes | Project owner / PM |
| `active` | Coach approved the plan; execution is available | Project owner / PM and execution roles |
| `pending_close` | Owner submitted close materials | Project coach |
| `ended` | Coach approved the close request | Super admin for archive |
| `archived` | Project is read-only and retained as a historical snapshot | Read-only access |

`dispatched` and `pending_kickoff` should no longer be created by the new flow. Existing records in those states need compatibility handling during migration.

## 4. Role and Action Design

### Company-level roles

- **Company CEO**: create projects, configure the team while the project is in `draft`, and trigger owner notification through saving the team configuration.
- **Super admin**: technical/global fallback, full project administration, and archive operation.
- **Normal member**: no global project-management authority; access comes from project membership.

### Project-level roles

- **Project coach (`project_ceo`)**: review submitted plans, decide major project matters, and approve or reject close requests.
- **Project owner / PM (`owner`)**: complete and submit the project plan, organize kickoff work, assign key tasks, confirm reports, and drive closure.
- **Coordinator (`coordinator`)**: coordinate resources and provide feedback; no default final-confirmation authority.
- **Task assignee / member (`member`)**: execute key tasks and submit progress.
- **Helper**: provide task-level assistance and collaboration feedback.

The same person may hold multiple company-level and project-level identities, but each action must be authorized against the identity relevant to that action.

## 5. End-to-End Data Flow

### 5.1 Project setup

The company CEO or super admin creates the project and configures:

- project name and type;
- customer name when applicable;
- background;
- objectives / acceptance criteria;
- expected outcomes;
- project start and end dates;
- project coach, owner, coordinator, and members.

Saving team configuration must validate that at least one project coach and one owner exist. Once the owner is present, the system sends the owner a project-ready notification. This notification is an event, not a lifecycle transition.

### 5.2 Plan completion and submission

The owner can enter the project-plan workspace directly from `draft` or `returned`. The submission contains project profile fields and the work-progress draft:

- objectives and period;
- key-work titles and descriptions;
- expected result / completion standard;
- key-task titles;
- assignee and helper assignments;
- task plan dates and notes.

Successful submission changes `draft` or `returned` to `pending_review`.

### 5.3 Coach review

Only the project-level coach or super admin may review the project plan.

- **Return**: persist a review reason and change `pending_review` to `returned`.
- **Approve**: change `pending_review` directly to `active` and notify project members.

The company CEO role alone must not approve a project unless that person is also configured as the project coach.

### 5.4 Kickoff as an execution event

Kickoff is no longer a lifecycle gate. After approval, the owner may create the kickoff meeting and record:

- kickoff date;
- agenda and decisions;
- execution-plan baseline;
- initial risks, dependencies, and follow-up actions.

The kickoff record is auditable and visible in the project history, but missing kickoff data must not prevent the project from being `active` unless a future explicit policy adds that rule.

### 5.5 Execution loop

The execution loop remains:

```text
assign key task
→ assignee/helper execute
→ submit progress report
→ owner confirms or requests supplement
→ confirm into project records
→ update task, achievement, issue, risk, and decision state
```

Escalation remains role-specific:

- general coordination goes to the coordinator;
- major issues and decisions go to the project coach;
- the owner remains responsible for closing the loop.

### 5.6 Close and archive

The close flow remains a separate governed process. Close materials must include:

- summary;
- objective result;
- unfinished items with reason, owner, handover recipient, follow-up plan, and expected resolution;
- remaining risks with the same ownership and follow-up information;
- handover plan;
- retrospective.

Close submission must continue to block on unresolved confirmation flows, waiting coordinator or coach decisions, unresolved major decision issues, pending achievement review, pending member changes, or invalid close materials. Unfinished key tasks and ordinary open issues may remain warnings when they are explicitly covered by the handover and residual-risk material.

After coach approval, the project becomes `ended`. Super admin performs the technical archive transition to `archived`; archived projects are read-only.

## 6. Frontend Changes

### Project management list and detail

- Remove “下发给负责人” as the primary lifecycle action.
- In `draft`, show the owner-facing “完善项目计划” action when the current user is the project owner.
- Keep company CEO / super admin team setup and editing available only while the project is `draft`.
- Keep an optional non-blocking “提醒负责人” action only if operationally needed; it must not change lifecycle state.
- Treat kickoff as an execution workspace action rather than a lifecycle transition.

### Status and todo mapping

- `draft`: owner can complete the plan; company-level managers can edit setup.
- `pending_review`: project coach can review.
- `returned`: owner can revise and resubmit.
- `active`: execution workspace, meetings, reports, confirmations, issues, decisions, achievements, and close request.
- `pending_close`: close review workspace.
- `ended`: close archive view.
- `archived`: read-only project archive.

Existing `dispatched` records should render like `draft` for owner todo purposes, with a compatibility label such as “待负责人完善” until migrated. Existing `pending_kickoff` records should render like `active` while preserving their historical state in the audit log.

## 7. Backend and API Changes

- Change the normal owner-submit path to accept `draft` and `returned` as before, and make `pending_review` the first approval state.
- Change project approval to write `active` directly and emit an approval/kickoff notification.
- Keep the existing dispatch endpoint temporarily as a compatibility alias that validates team readiness and sends/re-sends the owner notification without creating a lifecycle gate. New frontend code must not depend on it.
- Keep audit events for project creation, team configuration, owner notification, owner submission, coach return, coach approval, kickoff meeting creation, close submission, close approval/rejection, and archive.
- Do not broaden company CEO permissions into project-coach review permissions.
- Preserve the existing close-freeze and archive protections.

## 8. Compatibility and Migration

The migration should be backward compatible:

1. Existing `dispatched` projects remain editable by the owner and are treated as `draft`/“待负责人完善” in the new UI.
2. Existing `pending_kickoff` projects are treated as `active` for execution access.
3. Historical lifecycle/audit records remain unchanged.
4. New writes must not create `dispatched` or `pending_kickoff` as lifecycle states.
5. A later data migration may normalize old rows after the compatibility release is verified.

## 9. Error Handling

- Missing project coach or owner: block team setup completion and explain the missing role.
- Owner submission with incomplete plan: keep the project in its current editable state and display field-level validation.
- Review by company CEO without project-coach membership: return `403`.
- Approval of a non-reviewable state: return a lifecycle conflict without changing data.
- Kickoff creation failure: leave the project `active`; only the kickoff event fails.
- Close blockers: return structured blocker codes so the UI can distinguish required fixes from warnings.

## 10. Verification Strategy

Backend tests should cover:

- team setup validation and owner notification;
- no new `dispatched` state after setup;
- owner submit from `draft` and `returned`;
- coach-only approval semantics;
- approval writes `active` directly;
- kickoff failure does not revert `active`;
- old `dispatched` and `pending_kickoff` compatibility behavior;
- close blockers and archive protections.

Frontend tests should cover:

- no primary dispatch action in the new project-management flow;
- owner todo appears in `draft` and `returned`;
- coach review appears only in `pending_review`;
- approval renders execution actions immediately;
- kickoff is shown as an execution event, not a lifecycle gate;
- status labels and detail actions for legacy states;
- role separation between company CEO and project coach.

## 11. Success Criteria

The simplification is successful when a newly configured project follows:

```text
create/configure → owner completes/submits → coach approves → active
```

with one notification event and one substantive approval before execution, while preserving the existing execution, close-review, audit, permission, and archive controls.

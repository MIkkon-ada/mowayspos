# Company CEO vs Project Coach Role Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate system-level `company_ceo` visibility from project-level `project_ceo` decision handling so project coach workflows only use the current project's real `project_ceo` members.

**Architecture:** Keep system-role access in `permissions.py` and `main.py` for global visibility, but remove every path that auto-injects `project_ceo` from `is_ceo`. Add a project-scoped notification helper in `notify.py` and use it only for project coach escalation/decision notifications. Preserve the legacy `WAITING_CEO_DECISION` constant name and annotate its current business meaning instead of renaming it.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, existing project permission helpers.

---

### Task 1: Remove CEO-to-project-coach fallback from role lookup and public project payloads

**Files:**
- Modify: `bowei_ai_dashboard/app/services/policy.py`
- Modify: `bowei_ai_dashboard/app/main.py`
- Modify: `bowei_ai_dashboard/app/routers/dashboard.py`

- [ ] **Step 1: Write the failing test**

```python
def test_public_project_roles_do_not_inject_project_ceo_for_company_ceo():
    roles = _public_project_roles(["owner"], is_ceo=True)
    assert "project_ceo" not in roles
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_role_boundary.py::test_public_project_roles_do_not_inject_project_ceo_for_company_ceo -v`
Expected: FAIL before the fallback removal.

- [ ] **Step 3: Write minimal implementation**

```python
def user_roles_in_project(context: dict, project_id: int | None, db: Session) -> set[str]:
    if context.get("is_tech_admin"):
        return {"super_admin"}
    person_id = context.get("person_id")
    if person_id and project_id:
        return set(get_all_project_roles(person_id, project_id, db))
    return set()
```

```python
def _public_project_roles(raw_roles: list[str]) -> list[str]:
    mapping = {
        "owner": "project_owner",
        "coordinator": "project_coordinator",
        "member": "project_member",
        "project_ceo": "project_ceo",
    }
    return list(dict.fromkeys(mapping.get(role, role) for role in raw_roles or []))
```

```python
def _effective_roles(context: dict, project_id: int, proj_name: str | None, db: Session) -> set[str]:
    roles = set(get_all_project_roles(person_id, project_id, db))
    if context.get("is_tech_admin"):
        return {"super_admin", "owner", "coordinator", "member", "project_ceo"}
    if proj_name and proj_name in context.get("ceo_projects", []):
        roles.add("project_ceo")
    return roles
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_role_boundary.py::test_public_project_roles_do_not_inject_project_ceo_for_company_ceo -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bowei_ai_dashboard/app/services/policy.py bowei_ai_dashboard/app/main.py bowei_ai_dashboard/app/routers/dashboard.py tests/test_role_boundary.py
git commit -m "fix: separate company ceo and project coach roles"
```

### Task 2: Split project coach notifications from company CEO notifications

**Files:**
- Modify: `bowei_ai_dashboard/app/services/notify.py`
- Modify: `bowei_ai_dashboard/app/routers/confirmations.py`
- Modify: `bowei_ai_dashboard/app/routers/issues.py`

- [ ] **Step 1: Write the failing test**

```python
def test_project_coach_person_ids_only_returns_current_project_project_ceo():
    ids = project_coach_person_ids(project_id=1, db=db)
    assert ids == [project_ceo_person_id]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_role_boundary.py::test_project_coach_person_ids_only_returns_current_project_project_ceo -v`
Expected: FAIL before helper addition.

- [ ] **Step 3: Write minimal implementation**

```python
def company_ceo_person_ids(db: Session) -> list[int]:
    return [p.id for p in db.query(models.Person).filter(models.Person.system_role == ROLE_CEO, models.Person.is_active == True).all()]

def project_coach_person_ids(project_id: int, db: Session) -> list[int]:
    members = (
        db.query(models.ProjectMember)
        .filter(models.ProjectMember.project_id == project_id, models.ProjectMember.role == "project_ceo")
        .all()
    )
    return [m.person_id for m in members if m.person_id]
```

```python
for coach_id in project_coach_person_ids(project_id, db):
    _notify(db, recipient_id=coach_id, ntype="escalate_ceo", ...)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_role_boundary.py::test_project_coach_person_ids_only_returns_current_project_project_ceo -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bowei_ai_dashboard/app/services/notify.py bowei_ai_dashboard/app/routers/confirmations.py bowei_ai_dashboard/app/routers/issues.py tests/test_role_boundary.py
git commit -m "fix: separate company ceo and project coach roles"
```

### Task 3: Keep legacy CEO label names but document decision semantics

**Files:**
- Modify: `bowei_ai_dashboard/app/permissions.py`
- Modify: `bowei_ai_dashboard/app/domain/submission_status.py`

- [ ] **Step 1: Write the failing test**

```python
def test_can_ceo_decide_by_project_requires_project_project_ceo():
    assert can_ceo_decide_by_project(ctx_company_ceo_not_member, project_id, db) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_role_boundary.py::test_can_ceo_decide_by_project_requires_project_project_ceo -v`
Expected: FAIL before project-specific guard removal.

- [ ] **Step 3: Write minimal implementation**

```python
def can_ceo_decide_by_project(ctx: dict, project_id: int | None, db) -> bool:
    if ctx["can_confirm_all"]:
        return True
    person_id = ctx.get("person_id")
    if project_id is None or person_id is None:
        return False
    roles = get_all_project_roles(person_id, project_id, db)
    return "project_ceo" in roles
```

```python
# WAITING_CEO_DECISION is the legacy constant name.
# Business meaning: waiting for the current project's enterprise coach to decide.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_role_boundary.py::test_can_ceo_decide_by_project_requires_project_project_ceo -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bowei_ai_dashboard/app/permissions.py bowei_ai_dashboard/app/domain/submission_status.py tests/test_role_boundary.py
git commit -m "fix: separate company ceo and project coach roles"
```

### Task 4: Add regression coverage for auth payload and notification recipients

**Files:**
- Create: `bowei_ai_dashboard/tests/test_role_boundary.py`

- [ ] **Step 1: Write the failing test**

```python
def test_auth_me_does_not_inject_project_ceo_for_company_ceo():
    payload = _auth_me_payload("company_ceo_user")
    assert "project_ceo" not in payload["projects"][0]["roles"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_role_boundary.py -v`
Expected: FAIL until the role injection is removed.

- [ ] **Step 3: Write minimal implementation**

```python
def test_project_coach_notification_targets_only_project_members():
    assert project_coach_person_ids(project_id, db) == [project_project_ceo_id]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_role_boundary.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bowei_ai_dashboard/tests/test_role_boundary.py
git commit -m "fix: separate company ceo and project coach roles"
```

---

### Validation

Run from `bowei_ai_dashboard`:

```bash
python -m compileall app
pytest
```

Expected: compileall succeeds; pytest passes with the new regression tests.

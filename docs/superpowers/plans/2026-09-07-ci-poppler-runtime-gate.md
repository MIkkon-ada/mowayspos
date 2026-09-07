# CI Poppler Runtime Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the GitHub production runtime gate the Poppler binary required by scanned-PDF renderer tests.

**Architecture:** The backend container already installs `poppler-utils`; the GitHub Actions runner currently executes pytest directly and does not. Add one dependency-install step in the existing gate workflow before Python tests. A static workflow test protects the ordering and dependency name without changing renderer behavior.

**Tech Stack:** GitHub Actions, Ubuntu `apt-get`, pytest, Python `pathlib`.

---

### Task 1: Guard the CI runtime dependency

**Files:**
- Create: `bowei_ai_dashboard/tests/test_cloud_p1b2a_gate_workflow.py`
- Modify: `.github/workflows/cloud-p1b2a-gate.yml`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path


def test_production_runtime_gate_installs_poppler_before_backend_pytest():
    workflow = (
        Path(__file__).resolve().parents[2]
        / ".github/workflows/cloud-p1b2a-gate.yml"
    ).read_text(encoding="utf-8")

    install_index = workflow.index("sudo apt-get install -y poppler-utils")
    pytest_index = workflow.index("python -m pytest tests -q --tb=no")

    assert install_index < pytest_index
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
cd bowei_ai_dashboard
.\.venv\Scripts\python.exe -m pytest -q tests/test_cloud_p1b2a_gate_workflow.py
```

Expected: failure because the workflow has no Poppler installation step.

- [ ] **Step 3: Add the runner dependency step**

Insert the following YAML step directly before `Backend full pytest with known structural baseline` in `.github/workflows/cloud-p1b2a-gate.yml`:

```yaml
      - name: Install scanned-PDF renderer dependency
        run: |
          sudo apt-get update
          sudo apt-get install -y poppler-utils
          pdftoppm -v
```

- [ ] **Step 4: Run the focused test to verify it passes**

Run:

```powershell
cd bowei_ai_dashboard
.\.venv\Scripts\python.exe -m pytest -q tests/test_cloud_p1b2a_gate_workflow.py
```

Expected: `1 passed`.

- [ ] **Step 5: Run relevant renderer and full backend verification**

Run:

```powershell
cd bowei_ai_dashboard
.\.venv\Scripts\python.exe -m pytest -q tests/test_project_init_pdf_renderer.py
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: renderer tests pass; the full suite has no unexpected failures.

- [ ] **Step 6: Commit and update the PR branch**

```powershell
git add .github/workflows/cloud-p1b2a-gate.yml bowei_ai_dashboard/tests/test_cloud_p1b2a_gate_workflow.py docs/superpowers/plans/2026-09-07-ci-poppler-runtime-gate.md
git commit -m "fix: install Poppler in runtime gate"
git push
```

Expected: PR #86 receives the commit and reruns `production-runtime-gate`.

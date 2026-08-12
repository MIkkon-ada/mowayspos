# Submission Understanding Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert complete work-report submissions into permission-scoped, task-level, business-ready drafts.

**Architecture:** The router resolves the authenticated member's permitted candidate tasks before invoking the agent. The service asks the model for task-grouped reports with verbatim evidence arrays and normalized business fields. Server code validates task IDs and evidence, preserves allowed summaries, then merges duplicate task cards.

**Tech Stack:** FastAPI, Python, pytest, OpenAI-compatible chat completion.

---

### Task 1: Accept grouped evidence and business summaries

**Files:**
- Modify: `bowei_ai_dashboard/app/services/work_report_agent.py`
- Test: `bowei_ai_dashboard/tests/test_cross_project_work_report_agent.py`

- [ ] Write a failing test where one model report contains two evidence clauses for one candidate task and rewritten `completed` / `next_steps` fields.
- [ ] Run the targeted pytest test and confirm it fails because evidence arrays are unsupported or summaries are discarded.
- [ ] Add evidence-array normalization, validate every clause against the transcript, and preserve non-empty model summaries for accepted reports.
- [ ] Run the targeted test and confirm it passes.

### Task 2: Make the prompt submission-first

**Files:**
- Modify: `bowei_ai_dashboard/app/services/work_report_agent.py`
- Test: `bowei_ai_dashboard/tests/test_cross_project_work_report_agent.py`

- [ ] Write a failing prompt-contract test asserting that the model is told to read the entire submission, group by real task, and return business-ready fields with evidence arrays.
- [ ] Run the targeted pytest test and confirm it fails.
- [ ] Replace fragment-first prompt instructions with submission-level analysis instructions and an updated JSON schema.
- [ ] Run the targeted test and confirm it passes.

### Task 3: Verify regressions

**Files:**
- Test: `bowei_ai_dashboard/tests/test_cross_project_work_report_agent.py`
- Test: `bowei_ai_dashboard/tests/test_cross_project_submission_batch.py`

- [ ] Run the work-report agent suite plus cross-project submission suite.
- [ ] Run the frontend production build to retain the existing application contract.

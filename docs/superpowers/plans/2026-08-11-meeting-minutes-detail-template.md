# Meeting Minutes Detail Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the generic meeting detail body with the reusable weekly-minutes template approved by the user.

**Architecture:** Keep `MeetingDetailWorkspace` as the page-level component and only change its tab content. Derive agenda, decision and action rows from existing meeting JSON safely; never manufacture missing meeting data.

**Tech Stack:** React, TypeScript, Tailwind utility classes, Node built-in test runner.

---

### Task 1: Lock the reusable detail information architecture

**Files:**
- Modify: `frontend/tests/meetingDetailWorkspace.test.mjs`

- [ ] **Step 1: Write the failing test**

```js
test('meeting detail follows the reusable minutes template', () => {
  assert.match(detail, /一、会议议程/)
  assert.match(detail, /二、会议小结与决议/)
  assert.match(detail, /整理人：/)
  assert.match(detail, /会议安排事项/)
  assert.match(detail, /本周进展\/说明/)
  assert.doesNotMatch(detail, /会议内容摘要/)
  assert.doesNotMatch(detail, /行动清单/)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/meetingDetailWorkspace.test.mjs`

Expected: failure because the current component contains the generic summary and action-list layout.

### Task 2: Render the minutes page and separate tracking tabs

**Files:**
- Modify: `frontend/src/features/meeting/MeetingDetailWorkspace.tsx`

- [ ] **Step 1: Replace the generic minutes content**

Render a single document panel containing agenda items, conclusion-led decision blocks, and a footer with preparer/copy recipients. Keep the header, actions and dedicated detail route unchanged.

- [ ] **Step 2: Render action tables only in their own tabs**

Render a six-column current-action table under `本周待办`, and a five-column prior-tracking table under `上周追踪`; show the existing dashed empty state if the mapped source has no entries.

- [ ] **Step 3: Run the targeted test**

Run: `node --test tests/meetingDetailWorkspace.test.mjs`

Expected: all tests pass.

### Task 3: Verify the page compiles and retains navigation behavior

**Files:**
- Verify: `frontend/src/pages/MeetingPage.tsx`
- Verify: `frontend/src/app/routes.tsx`

- [ ] **Step 1: Run all meeting-focused tests**

Run: `node --test tests/meetingProjectSelectionCard.test.mjs tests/meetingProjectListWorkspace.test.mjs tests/meetingDetailWorkspace.test.mjs`

Expected: all tests pass.

- [ ] **Step 2: Build production bundle**

Run: `npm run build`

Expected: TypeScript and Vite build complete successfully.

# Project People Tag Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the full-width selected-person rows in the project initiation/edit form with compact, wrapping name tags while preserving all existing selection and persistence behavior.

**Architecture:** Keep the current `ProjectInitModal` state, role mapping, and callbacks. Change only the selected-member rendering in the active workbench JSX to use a wrapping flex container and compact tag markup. Add a static regression test that scopes assertions to the active modal layout and verifies no generated avatar block is used for selected members.

**Tech Stack:** React, TypeScript, Tailwind utility classes, Node test runner, Vitest, Vite.

---

### Task 1: Add a failing layout regression test

**Files:**
- Create: `frontend/tests/projectPeopleTagLayout.test.mjs`
- Test target: `frontend/src/features/settings/ProjectInitModal.tsx`

- [ ] **Step 1: Write the failing test**

Add a test that reads the modal source, scopes to the first `project-init-workbench` return, and requires selected-member rendering to use a wrapping flex container, compact tag styles, and no avatar gradient block:

```js
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/features/settings/ProjectInitModal.tsx', import.meta.url), 'utf8')
const activeLayout = source.slice(source.indexOf('project-init-workbench'))

test('selected people render as wrapping name tags without generated avatars', () => {
  assert.match(activeLayout, /flex flex-wrap[^\n]*gap-/)
  assert.match(activeLayout, /rounded-md border[^\n]*bg-/)
  assert.match(activeLayout, /person\.name/)
  assert.doesNotMatch(activeLayout, /bg-gradient-to-br \$\{getAvatarColor\(person\.name\)\}/)
})
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run from `frontend`:

```powershell
node --test tests/projectPeopleTagLayout.test.mjs
```

Expected: FAIL because the current active layout renders each selected member as a full-width row and does not contain a wrapping tag container.

### Task 2: Implement the compact selected-member tags

**Files:**
- Modify: `frontend/src/features/settings/ProjectInitModal.tsx` in the active `project-init-workbench` team configuration section.

- [ ] **Step 1: Replace the selected member row renderer**

For each role, keep `selectedPeople`, `removeMember`, and `ROLE_LABELS` unchanged, but render selected members inside a wrapping flex container:

```tsx
{selectedPeople.length > 0 ? (
  <div className="flex min-h-10 flex-wrap items-start gap-1.5">
    {selectedPeople.map((person) => (
      <div key={person.id} className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-slate-50 px-2 py-1">
        <span className="text-xs font-medium text-slate-700">{person.name}</span>
        <button type="button" onClick={() => removeMember(role, person.id)} className="text-sm leading-none text-slate-400 hover:text-red-500" aria-label={`移除${person.name}`}>×</button>
      </div>
    ))}
  </div>
) : (
  <div className="flex h-10 items-center justify-center border border-dashed border-slate-300 text-xs text-slate-400">未配置</div>
)}
```

This removes the initial-character avatar from the selected-member display only. The existing picker, person IDs, toggle callback, and submit payload remain untouched.

- [ ] **Step 2: Run the focused regression test**

```powershell
node --test tests/projectPeopleTagLayout.test.mjs
```

Expected: PASS.

### Task 3: Run the full frontend verification

**Files:**
- Test: `frontend/tests/projectPeopleTagLayout.test.mjs`
- Production code: `frontend/src/features/settings/ProjectInitModal.tsx`

- [ ] **Step 1: Run all unit tests**

```powershell
npm run test:unit
```

Expected: all Vitest suites pass.

- [ ] **Step 2: Run the production build**

```powershell
npm run build
```

Expected: Vite build exits with code 0. Existing chunk-size warnings may remain informational.

- [ ] **Step 3: Check the browser preview**

Open the project initiation/edit page and verify one selected person, several selected people, automatic wrapping, and individual remove buttons. Confirm no backend request or form payload code changed.

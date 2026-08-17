# Owner Submit Project Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将负责人“完善项目方案”从遮罩弹窗迁移为项目详情下的正常子页面。

**Architecture:** 新的 `ProjectOwnerSubmitPage` 从路由参数加载项目，并把现有填报组件嵌入 `ProjectLayout` 的普通内容区域。`OwnerSubmitModal.tsx` 仅保留表单工作台和全部业务逻辑，删除遮罩容器；Dashboard、项目列表与项目详情改为统一导航到子路由。

**Tech Stack:** React、React Router、TypeScript、Tailwind CSS、Node test runner。

---

### Task 1: Route migration contract

**Files:**
- Create: `frontend/tests/projectOwnerSubmitRoute.test.mjs`
- Modify: `frontend/tests/ownerSubmitModalLayout.test.mjs`

- [ ] **Step 1: Write the failing tests**

```js
assert.match(routesSource, /path="projects\/:projectId\/owner-submit"/)
assert.doesNotMatch(workbenchSource, /fixed inset-0/)
assert.match(dashboardSource, /navigate\(`\/home\/projects\/\$\{project\.id\}\/owner-submit`\)/)
```

- [ ] **Step 2: Verify the tests fail before the migration**

Run: `node --test tests/projectOwnerSubmitRoute.test.mjs tests/ownerSubmitModalLayout.test.mjs`

Expected: FAIL because the route and page do not yet exist and the current form still owns a fixed overlay container.

### Task 2: Create the normal project subpage and route

**Files:**
- Create: `frontend/src/pages/ProjectOwnerSubmitPage.tsx`
- Modify: `frontend/src/app/routes.tsx`

- [ ] **Step 1: Add `ProjectOwnerSubmitPage`**

```tsx
const { projectId: rawProjectId } = useParams<{ projectId: string }>()
const projectId = Number(rawProjectId)

useEffect(() => {
  void getProject(projectId).then(setProject)
}, [projectId])

<OwnerSubmitWorkbench
  project={project}
  onClose={() => navigate(`/home/projects/${project.id}`)}
  onSuccess={() => navigate(`/home/projects/${project.id}`)}
/>
```

The page uses `flex min-h-0 flex-1` so the workbench has an internal scroll area inside `ProjectLayout` rather than an overlay.

- [ ] **Step 2: Add the guarded route before `projects/:projectId`**

```tsx
<Route
  path="projects/:projectId/owner-submit"
  element={<RequireCapability mode="project_view"><ProjectOwnerSubmitPage /></RequireCapability>}
/>
```

### Task 3: Reuse the workbench without a Modal shell

**Files:**
- Modify: `frontend/src/features/settings/OwnerSubmitModal.tsx`

- [ ] **Step 1: Export the semantic workbench component**

```tsx
export function OwnerSubmitWorkbench({ project, onClose, onSuccess }: Props) {
```

- [ ] **Step 2: Replace the overlay with a page-local workbench**

```tsx
<section className="owner-submit-workbench-shell flex min-h-0 w-full flex-1 flex-col overflow-hidden ...">
```

Remove the `fixed inset-0` backdrop and click-away close behavior. Keep the existing Header/Main/Footer, but make the header action return to project detail and continue to use `onClose` for footer cancel.

### Task 4: Convert all entry points to navigation

**Files:**
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/features/settings/ProjectsMgmtSection.tsx`
- Modify: `frontend/src/pages/ProjectDetailPage.tsx`

- [ ] **Step 1: Remove modal imports and local modal state**

```tsx
// Dashboard and ProjectsMgmtSection no longer render OwnerSubmitModal.
```

- [ ] **Step 2: Navigate each existing entry to the project subpage**

```tsx
navigate(`/home/projects/${project.id}/owner-submit`)
```

- [ ] **Step 3: Replace the project-detail TODO**

```tsx
onOwnerSubmit={() => navigate(`/home/projects/${project.id}/owner-submit`)}
```

### Task 5: Verify regression boundaries and real navigation

**Files:**
- Test: `frontend/tests/projectOwnerSubmitRoute.test.mjs`
- Test: `frontend/tests/ownerSubmitModalLayout.test.mjs`
- Test: `frontend/tests/ownerSubmitAiIntegration.test.mjs`
- Test: `frontend/tests/ownerSubmitAiPanelBehavior.test.mjs`

- [ ] **Step 1: Run focused tests**

Run:

```powershell
cd frontend
node --test tests/projectOwnerSubmitRoute.test.mjs tests/ownerSubmitModalLayout.test.mjs
node --test tests/ownerSubmitAiIntegration.test.mjs
node --test tests/ownerSubmitAiPanelBehavior.test.mjs
```

Expected: all tests pass.

- [ ] **Step 2: Run the complete frontend verification**

Run:

```powershell
npm run build
node --test tests/*.test.mjs
```

Expected: build and full Node suite pass.

- [ ] **Step 3: Manually verify real app navigation**

Check Dashboard, project list and project detail entries. Confirm each reaches `/home/projects/:projectId/owner-submit`, sidebar remains visible, there is no dimmed overlay, Cancel/return go to detail, and the workbench Main scrolls inside the normal page when content overflows.

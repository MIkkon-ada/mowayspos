# 执行闭环验收：提交 → 确认 → 入库 → 工作推进表可见

> N4-P0-C-EXECUTION-SUBMISSION-TO-WORK-PROGRESS-ACCEPTANCE

## 1. 当前闭环路径

```
成员/关键任务责任人 提交工作进展
        │
        ▼
POST /api/updates ────► UpdateSubmission（confirm_status = "待确认"）
        │                    related_task_id = NULL
        │                    ✅ 不直接写 Achievement / Issue / SubTask
        │
        ▼
  AI 确认中心 / 待确认 tab
        │
        ▼
Owner/PM 确认 ────────► POST /api/confirmations/{id}/confirm
        │
        │  设置 related_task_id = task.id
        │  更新 SubTask（notes 追加、source_submission_id）
        │  写入 Achievement（source_submission_id）
        │  写入 Issue（source_submission_id）
        │  confirm_status → "已入库"
        │
        ▼
工作推进表可读 ───────► GET /api/tasks/{task_id}/updates
                    （按 related_task_id 过滤，确认后可见）
                    
关键任务详情 ────────► GET /api/subtasks/{id}/detail
                    （返回 source_submission + related_achievements + related_issues）
```

## 2. 使用的接口

| 步骤 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 提交进展 | POST | `/api/updates` | 创建待确认 UpdateSubmission |
| 查看待确认 | GET | `/api/confirmations/pending?tab=待审核` | 确认中心待审核队列 |
| 确认入库 | POST | `/api/confirmations/{id}/confirm` | Owner 确认写入正式表 |
| 任务更新列表 | GET | `/api/tasks/{id}/updates` | 工作推进表读取已确认更新 |
| 关键任务详情 | GET | `/api/subtasks/{id}/detail` | 包含来源提交和关联成果/问题 |

## 3. 提交后进入什么状态

- `confirm_status = "待确认"`（`SS.S_NEW`）
- `related_task_id = NULL`（确认后才由 `confirm()` 设置）
- 提交数据存入 `human_result_json` / `ai_result_json`
- **不直接写** `Achievement` 表、`Issue` 表、`SubTask.notes`

## 4. 谁确认

- **项目负责人（owner / PM）**
- 超级管理员（tech_admin）
- 企业教练（project_ceo）不可确认
- 纯公司 CEO（company_ceo，无项目角色）不可确认

权限校验链：
1. `_require_confirmation_center` — 需有确认中心访问权
2. `_require_owner_style_actor` — 拦截纯 company_ceo
3. `_can_owner_style_action` → `P.can_confirm()` — 需是项目 owner

## 5. 确认后写入哪些表

| 表 | 写入内容 | 关联方式 |
|---|---------|---------|
| `UpdateSubmission` | `confirm_status = "已入库"`，`related_task_id`，`confirmed_by`，`confirmed_at` | 自身 |
| `SubTask` | `notes` 追加完成内容，`source_submission_id`，可能更新 `status` | `source_submission_id` |
| `Achievement` | 新建成果记录，含 `source_submission_id`，`project_id`，`confirmed_by` | `source_submission_id` |
| `Issue` | 新建问题记录，含 `source_submission_id`，`project_id`，`related_task_id` | `source_submission_id` |
| `OperationLog` | `confirmation_approve` + 可选 `confirmation_ai_write_task` | `target_type + target_id` |

**不改变的表：**
- `Project.status` — 保持 `active`
- `Project.is_active` — 保持 `True`
- 不会被改回 `draft` 或 `pending_review`

## 6. 工作推进表通过什么接口看到更新

- 执行视图的任务更新列表：`GET /api/tasks/{task_id}/updates`
  - 按 `related_task_id = task_id` 过滤 UpdateSubmission
  - 返回最近 10 条：`{id, submitter, transcript_text(前120字), created_at}`
- 关键任务详情：`GET /api/subtasks/{id}/detail`
  - 返回 `source_submission`（来源提交摘要）
  - 返回 `related_achievements`（最近 10 条关联成果）
  - 返回 `related_issues`（最近 10 条关联问题）

**关键规则**：未确认提交的 `related_task_id` 为 NULL，不会出现在 `GET /api/tasks/{id}/updates` 中。这是正确的业务口径——未确认内容不应进入工作推进表正式记录。

## 7. 本轮发现的问题

| # | 问题 | 严重度 | 状态 |
|---|------|--------|------|
| 1 | TaskManagementPage `handleProgressSubmit` 成功后提交提示文案不够清晰——未说明"负责人确认后才会显示在工作推进表" | P2 体验 | 已修复 |
| 2 | （无其他问题——闭环主体完整，无断点） | - | - |

## 8. 本轮修复的问题

### P2: 提交成功提示文案优化

**文件**：`frontend/src/pages/TaskManagementPage.tsx`

**改动前**：提交成功后仅切换 `progressSubmitState` 到 `done`，无明确说明。

**改动后**：提交成功后显示提示："已提交至 AI 确认中心，负责人确认后将显示在工作推进表。"

**理由**：用户提交后可能期望立即在工作推进表看到更新，但实际要等确认后。明确提示避免困惑。

## 9. 仍未做的内容

- 未修改数据库结构（无新增表/字段）
- 未引入 Workstream / 第四层任务
- 未开发客户侧
- 未引入过程支持 / 过程保障
- 未添加任务详情页
- 未修改项目生命周期
- 未修改角色权限口径
- 未重构确认中心
- 未重做 TaskManagementPage
- 前端 P2 体验项：`handleProgressSubmit` 提交成功后不刷新 `fetchTaskUpdates`（因为确认前查不到，业务正确）

## 10. 是否依赖真实 AI

**不依赖。** 后端测试通过构造 `human_result` 字段绕过 AI 提取器。前端提交时如不传 `human_result`，后端会调用规则引擎提取（`extract_update` with `require_llm=False`），不依赖外部 AI 服务。

---

## 附录：测试覆盖

### 后端测试 (`test_execution_submission_to_work_progress_flow.py`)

| 测试 | 覆盖内容 |
|------|---------|
| `test_flow1_submit_progress_creates_pending_submission` | 提交 → 待确认状态，related_task_id = NULL，不写 Achievement/Issue |
| `test_flow1_submit_without_human_result_does_not_call_real_ai` | human_result 绕过 AI，正确存储 |
| `test_flow1_non_active_project_rejects_submission` | 非 active 项目拒绝提交 |
| `test_flow2_owner_confirm_writes_to_tables_and_sets_related_task_id` | 确认 → 写 Achievement、Issue、SubTask，设置 related_task_id |
| `test_flow2_owner_confirm_does_not_change_project_lifecycle` | 确认不改变项目状态 |
| `test_flow2_company_ceo_cannot_confirm` | company_ceo 权限被拒 |
| `test_flow2_project_ceo_cannot_confirm` | project_ceo 权限被拒 |
| `test_flow3_task_updates_shows_confirmed_submission` | 确认后工作推进表可见，确认前不可见 |
| `test_flow3_subtask_detail_shows_source_submission_and_related_data` | 关键任务详情含 source_submission + achievements + issues |
| `test_flow3_full_roundtrip_closed_loop` | 端到端闭环验证 |
| `test_flow3_unconfirmed_submission_not_in_task_updates` | 未确认提交不出现在工作推进表 |

### 前端结构测试 (`test_execution_submission_frontend_structure.py`)

| 测试 | 覆盖内容 |
|------|---------|
| TaskManagementPage 有 createUpdate / handleProgressSubmit | 提交进展入口 |
| TaskManagementPage 有 fetchTaskUpdates / fetchSubtaskDetail | 读取汇报记录入口 |
| TaskManagementPage 有 progressSubmitState | 提交状态管理 |
| VoiceUpdatePage 有 createUpdate / extract | 语音提交入口 |
| 无 Workstream / 第四层任务 | 边界保护 |
| 无关键任务详情页路由 | 边界保护 |
| 无客户侧入口 | 边界保护 |
| 无过程支持 / 过程保障 | 边界保护 |
| api/updates.ts 存在 | API 层检查 |
| api/confirmations.ts 存在 | 确认 API 检查 |
| 计划表视图不变 | 计划表边界保护 |

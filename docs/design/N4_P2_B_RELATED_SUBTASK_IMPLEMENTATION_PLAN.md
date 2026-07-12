# N4-P2-B related_subtask_id 最小数据库增强实施评审与开发计划

> **状态**: 实施评审通过，建议进入开发  
> **日期**: 2026-07-13  
> **分支**: n4-p2-b-related-subtask-implementation-plan  
> **底线**: 本轮不改代码、不改数据库、不生成迁移，只做评审和计划输出

---

## 1. 背景

基于已合并的 [N4-P1-D 关键任务绑定口径设计文档](./N4_P1_D_KEY_TASK_BINDING_SCOPE_DESIGN.md) 中推荐的**方案 B：最小数据库增强方案**，进行实施可行性评审，输出分步开发计划。

当前系统三层结构已确立：
- **Project（项目）** → 顶层
- **Task（重点工作/Workstream）** → 中层
- **SubTask（关键任务/KeyTask）** → 底层

`related_task_id` 全局指向 `tasks.id` = 重点工作，三个核心表均无 `related_subtask_id` 字段。

---

## 2. 当前现状复述

### 2.1 数据库字段现状（已通过 PRAGMA 确认）

| 表 | related_task_id | 指向 | related_subtask_id | 
|----|-----------------|------|--------------------|
| `update_submissions` | INTEGER, FK→tasks.id | **重点工作** | **不存在** |
| `achievements` | INTEGER, FK→tasks.id | **重点工作** | **不存在** |
| `issues` | INTEGER, FK→tasks.id | **重点工作** | **不存在** |
| `achievement_submissions` | INTEGER, FK→tasks.id | 重点工作 | INTEGER, nullable — **存在但 schema 未暴露** |
| `subtasks` | — | — | id INTEGER PK |

### 2.2 后端 Schema 现状

| Schema | related_task_id | related_subtask_id |
|--------|-----------------|---------------------|
| `AchievementPayload` | `int \| None = None` | **无** |
| `IssuePayload` | `int \| None = None` | **无** |
| `AchievementSubmissionPayload` | `int` (必填) | **无** |

所有 Pydantic schema 均无 `related_subtask_id` 字段。即使前端传入也会被忽略。

### 2.3 后端 Router 写入链路现状

| 写入路径 | related_task_id 赋值 | related_subtask_id |
|----------|---------------------|-------------------|
| `updates.py create_update` | **不设置**（确认入库时才赋值） | **不设置** |
| `confirmations.py confirm` — task_new | `row.related_task_id = task.id` | **无** |
| `confirmations.py confirm` — subtask_update | `row.related_task_id = parent_task.id` | **无** |
| `confirmations.py confirm` — subtask_new | `row.related_task_id = parent_task.id` | **无** |
| `confirmations.py confirm` — suggest_new_subtask | `row.related_task_id = parent_task.id` | **无**（新 SubTask 已创建但未回写到成果） |
| `confirmations.py confirm` — subtask_progress | `row.related_task_id = parent.id` | **无** |
| achievements created via confirm | `fulfill_or_create_achievement(db, ..., task_id, ...)` — task_id = 重点工作 ID | **无** |
| issues created via confirm | `related_task_id = subtask.task_id` — subtask.task_id = 重点工作 ID | **无** |
| `achievements.py create_achievement` | `data.related_task_id` 直接传入 | **无** |
| `issues.py create_issue` | `data.related_task_id` 直接传入 | **无** |

### 2.4 核心确认入库分支（confirmations.py confirm）

`confirm()` 函数是系统中最复杂的写入路径，包含以下分支：

| 写入模式 | 条件 | 涉及的 related_task_id 写入 |
|----------|------|--------------------------|
| `subtask_status_update` | `result_type == subtask_status_update` | `row.related_task_id = parent_task.id` |
| `subtask_update` | `write_mode == subtask_update` 且 `target_subtask_id` | `row.related_task_id = parent_task.id` |
| `subtask_new` | `write_mode == subtask_new` 且 `target_task_id` | `row.related_task_id = parent_task.id` |
| `task_new` | `write_task == true` 且 `key_task` 有值 | `row.related_task_id = task.id` |
| `task_reports` | 多卡片逐一处理 | 见下文 |

`task_reports` 模式下的单卡片处理逻辑（`_write_single_task_report` 函数，confirmations.py:272-399）：

| 子模式 | matched_subtask_id 可用 | 成果写入 | 问题写入 |
|--------|----------------------|---------|---------|
| `suggest_new_subtask` | 否（新建 SubTask） | `ach = W.fulfill_or_create_achievement(db, ..., parent_task.id, ...)` | 不写问题 |
| `subtask_progress/completed` + matched_id | 是 | `ach = W.fulfill_or_create_achievement(db, ..., task_id, ...)` — task_id = 重点工作 ID | `related_task_id = subtask.task_id` — subtask.task_id = 重点工作 ID |

### 2.5 `fulfill_or_create_achievement` 签名

```python
# workflow.py:89
def fulfill_or_create_achievement(
    db: Session,
    item: dict,
    source_type: str,
    task_id: int | None,      # ← 当前只接收 Task/重点工作 ID
    project: str,
    *,
    submission_id: int | None = None,
) -> models.Achievement:
```

- 函数只接收 `task_id`（重点工作 ID），没有 `related_subtask_id` 参数
- 新建 Achievement 时 `achievement.related_task_id = clean.get("related_task_id") or task_id`
- 如果 item dict 中有 `related_subtask_id`，会被 `filtered_fields()` 过滤掉（因为 models.Achievement 无此字段）

### 2.6 SubTask 详情反向查询现状

`subtasks.py get_subtask_detail`（行 358-396）：
```python
achievements = db.query(models.Achievement).filter(
    models.Achievement.related_task_id == row.task_id  # row.task_id = 重点工作 ID
).all()
issues = db.query(models.Issue).filter(
    models.Issue.related_task_id == row.task_id  # row.task_id = 重点工作 ID
).all()
```

当前通过 `related_task_id == row.task_id` 查询，而 `row.task_id` 是指向重点工作（Task）的外键。因此只能查到关联到同一重点工作的所有成果/问题，无法精确到具体关键任务。

### 2.7 前端现状

| 页面 | 关键任务展示 | 表单状态 |
|------|-------------|---------|
| AchievementsPage | `keyTaskLabelForAchievement()` 读候选字段 → "未指定关键任务" | disabled dropdown，选项"未指定关键任务" |
| IssuesPage | `keyTaskLabelForIssue()` 读候选字段 → "未指定关键任务" | disabled dropdown，选项"未指定关键任务" |
| VoiceUpdatePage | `task_reports[].matched_subtask_id` JSON 中存在 | 正常可编辑 |
| ConfirmPage | 确认卡内显示关键任务名 | 正常可读 |
| TaskManagementPage | 无 related_subtask_id 使用 | — |

前端 API 类型定义：
- `frontend/src/api/achievements.ts` — `AchievementPayload` 无 `related_subtask_id`
- `frontend/src/api/issues.ts` — `createIssue payload` 无 `related_subtask_id`
- `frontend/src/types.ts` — `AchievementItem` 和 `IssueItem` 均有 `[key: string]: unknown` 作为兜底，`crud.to_dict()` 新增字段会自动映射

---

## 3. 最小数据库变更范围

### 3.1 需新增字段的表（3 张）

| 表 | 新增字段 | 类型 | FK | Nullable |
|----|---------|------|-----|----------|
| `update_submissions` | `related_subtask_id` | Integer | FK → subtasks.id | **YES** |
| `achievements` | `related_subtask_id` | Integer | FK → subtasks.id | **YES** |
| `issues` | `related_subtask_id` | Integer | FK → subtasks.id | **YES** |

### 3.2 不涉及的表

- `subtasks` — 不需要改（已有 `id` PK 作为被引用目标）
- `tasks` — 不需要改
- `projects` — 不需要改
- `achievement_submissions` — **已有此字段**，无需新增，仅需在 schema 中暴露

---

## 4. 字段设计

### 4.1 models.py 变更

```python
# UpdateSubmission（行 69 后新增）
related_subtask_id = Column(Integer, ForeignKey("subtasks.id"), nullable=True)

# Achievement（行 104 后新增）
related_subtask_id = Column(Integer, ForeignKey("subtasks.id"), nullable=True)

# Issue（行 159 后新增）
related_subtask_id = Column(Integer, ForeignKey("subtasks.id"), nullable=True)
```

三个字段均为 `nullable=True`：
- 历史数据默认 NULL，无需回填
- 项目级成果/问题可以不绑定关键任务
- 不做全链路强制绑定

### 4.2 外键策略

- `ForeignKey("subtasks.id")` — SQLAlchemy ORM 层面声明
- SQLite 默认不启用外键约束检查（需 `PRAGMA foreign_keys = ON`）
- 建议在应用层做数据一致性校验，不依赖 SQLite 外键

### 4.3 migration 文件

需要创建一个 Alembic migration（或手动 SQL）：
```sql
ALTER TABLE update_submissions ADD COLUMN related_subtask_id INTEGER REFERENCES subtasks(id);
ALTER TABLE achievements ADD COLUMN related_subtask_id INTEGER REFERENCES subtasks(id);
ALTER TABLE issues ADD COLUMN related_subtask_id INTEGER REFERENCES subtasks(id);
```

---

## 5. 后端 Schema 改动清单

### 5.1 schemas.py

| Schema | 变更 | 字段定义 |
|--------|------|---------|
| `AchievementPayload` | **新增** `related_subtask_id` | `int \| None = None` |
| `IssuePayload` | **新增** `related_subtask_id` | `int \| None = None` |
| `AchievementSubmissionPayload` | **新增** `related_subtask_id` | `int \| None = None`（表已有此列） |

### 5.2 注意

- `crud.to_dict()` 使用 `obj.__table__.columns` 遍历所有列，因此只要 models.py 中新增了字段，列表/详情 API 自动返回
- AchievementItem / IssueItem 前端类型已有 `[key: string]: unknown` 兜底，新增字段自动可访问
- **不需要新建专门的 Response schema**，当前 `crud.to_dict()` + `[key: string]: unknown` 模式已经支持 JSON 序列化

---

## 6. 后端 Router / Service 改动清单

### 6.1 updates.py — create_update

**PR4 范围**（本节先用 TODO 标记，避免 PR1 做太多）：

- 在 `models.UpdateSubmission(...)` 创建时，可选地从 `human_result.task_reports[0].matched_subtask_id` 提取并设置 `related_subtask_id`
- **数据一致性校验**：如果 `related_subtask_id` 设置了，验证该 SubTask 的 `task_id` 对应的 Task 的 `project_id` 与提交的 `project_id` 一致

### 6.2 confirmations.py — confirm

这是改动最密集的文件。以下按触发点列出：

#### 6.2.1 `task_reports` 模式 — `suggest_new_subtask` 分支（confirm:713-752）

当前：创建新 SubTask 后，成果写入时 `related_task_id = parent_task.id`

**需新增**：
1. `fulfill_or_create_achievement` 需支持 `related_subtask_id` 参数（见 6.3）
2. 成果写入时传入 `related_subtask_id = new_sub.id`

```python
# 伪代码变更
ach = W.fulfill_or_create_achievement(
    db, ach_dict, row.source_type, parent_task.id,
    ach_dict.get("special_project") or project,
    submission_id=row.id,
    related_subtask_id=new_sub.id,  # ← 新增
)
```

#### 6.2.2 `task_reports` 模式 — `subtask_progress/subtask_complete` 分支（confirm:794-833）

当前：`matched_subtask_id` 已存在但只用于更新 SubTask 状态，成果写入时 `task_id` = 重点工作 ID

**需新增**：
1. 成果写入时传入 `related_subtask_id = subtask.id`（已有 `matched_id`，即 SubTask ID）
2. 问题写入时设置 `issue.related_subtask_id = subtask.id`

```python
# 成果写入（confirm:801）
ach = W.fulfill_or_create_achievement(
    db, ach_dict, row.source_type, task_id,
    ach_dict.get("special_project") or project,
    submission_id=row.id,
    related_subtask_id=subtask.id,  # ← 新增
)

# 问题写入（confirm:819-833）
issue = models.Issue(
    ...
    related_task_id=subtask.task_id,
    related_subtask_id=subtask.id,  # ← 新增
)
```

#### 6.2.3 旧格式 `key_task_issues`（confirm:836-857 和 887-906）

当前：`key_task_issues` 条目没有 `related_task_id` 和 `related_subtask_id`

**需新增**（如果条目中携带了 task/subtask 上下文才写入）：
- 不强制，因为 `key_task_issues` 的定位可能是"整个汇报级别"的问题
- 如果未来需要精确绑定，可通过 `human_result` 的上下文推断

#### 6.2.4 单卡片确认路径（confirm_task_card, confirm:942-992）

调用 `_write_single_task_report()` → 该函数同样需要在成果/问题写入时设置 `related_subtask_id`

`_write_single_task_report` 函数内的改动点与 6.2.1 和 6.2.2 一致。

### 6.3 workflow.py — fulfill_or_create_achievement

**新增参数**：

```python
def fulfill_or_create_achievement(
    db: Session,
    item: dict,
    source_type: str,
    task_id: int | None,
    project: str,
    *,
    submission_id: int | None = None,
    related_subtask_id: int | None = None,  # ← 新增
) -> models.Achievement:
```

- 新建 Achievement 时：`achievement.related_subtask_id = item.get("related_subtask_id") or related_subtask_id`
- 更新已有 Achievement 时：仅在 `related_subtask_id` 不为 None 时更新

### 6.4 achievements.py — create_achievement / update_achievement

**create_achievement**（行 89-118）：
- 当前 `data = {k: v for k, v in payload.model_dump().items() if k != "project_id"}`
- 由于 schemas 新增了 `related_subtask_id`，这里自动包含（无需改代码）
- **需新增**：数据一致性校验 —— 如果传入了 `related_subtask_id`，验证该 SubTask 存在且其 `task_id` 与 `related_task_id` 一致

**update_achievement**（行 140-180）：
- 同上，payload 自动包含新字段
- 数据一致性校验同样需要

### 6.5 issues.py — create_issue / update_issue

与 achievements 同理：
- `create_issue` 自动接收 `related_subtask_id`
- `update_issue` 自动接收
- 需新增数据一致性校验

### 6.6 subtasks.py — get_subtask_detail

**当前查询**：
```python
achievements = db.query(models.Achievement).filter(
    models.Achievement.related_task_id == row.task_id  # 重点工作级别
).all()
```

**改进后**：
```python
# 同时支持 related_subtask_id 精确查询（有字段后自然可用）
achievements = db.query(models.Achievement).filter(
    models.Achievement.related_subtask_id == row.id  # 精确到具体关键任务
).all()
# 以及 fallback 到 related_task_id 的兜底查询
```

---

## 7. 前端页面改动清单

### 7.1 AchievementsPage.tsx

**PR2 范围**：

1. **登记弹窗**：启用关键任务下拉框
   - 移除 `disabled` 属性
   - 当用户选择重点工作（`related_task_id`）后，加载该工作下的关键任务列表（调用 `fetchSubTasks(taskId)`）
   - 下拉选项动态生成
   - `createAchievement` payload 中传入 `related_subtask_id`

2. **列表+详情展示**：增强 `keyTaskLabelForAchievement`
   - 当 `item.related_subtask_id` 存在时，从关键任务列表中查找名称
   - 需要传入 subtasks 列表或通过 ID 查找
   - 展示 "关键任务：{subtask.title}" 而非 "未指定关键任务"

3. **保持 `related_task_id` 读取逻辑不变**（任务选择器和展示）

### 7.2 IssuesPage.tsx

**PR2 范围**，与 AchievementsPage 对称：

1. **新增问题弹窗**：启用关键任务下拉框（可选项）
2. **卡片+详情展示**：增强 `keyTaskLabelForIssue`
3. **createIssue payload**：传入 `related_subtask_id`

### 7.3 VoiceUpdatePage / useVoiceSubmission.ts

**PR4 范围**：

- 当前 `task_reports` 已携带 `matched_subtask_id`（JSON 级别）
- 提交时 `human_result` 已包含这些信息
- 后端 `create_update` 可以从 `human_result.task_reports[0].matched_subtask_id` 提取并写入 `related_subtask_id`（PR4）

### 7.4 TaskManagementPage.tsx

**不需要改动**（本轮仅涉及成果/问题/汇报，不涉及工作推进表）

### 7.5 ConfirmPage.tsx

**本轮不改**（按任务要求：本轮不改 ConfirmPage）

### 7.6 前端 API 类型更新

`frontend/src/api/achievements.ts`：
```typescript
export type AchievementPayload = {
  // ... existing fields ...
  related_subtask_id?: number | null  // ← 新增
}
```

`frontend/src/api/issues.ts` 中 `createIssue` 的参数类型：
```typescript
export function createIssue(payload: {
  // ... existing fields ...
  related_subtask_id?: number | null  // ← 新增
}): Promise<IssueItem>
```

---

## 8. 确认入库链路改动清单

以改动点汇总：

| 触发点 | 文件 | 行范围 | 改动 |
|--------|------|--------|------|
| `fulfill_or_create_achievement` 签名 | workflow.py | 89-97 | 新增 `related_subtask_id` 参数 |
| 新建 Achievement 时设置字段 | workflow.py | 116-124 | `achievement.related_subtask_id = ...` |
| `task_reports` — suggest_new_subtask 成果写入 | confirmations.py | 737-746 | 传入 `related_subtask_id=new_sub.id` |
| `task_reports` — subtask_progress 成果写入 | confirmations.py | 801-810 | 传入 `related_subtask_id=subtask.id` |
| `task_reports` — subtask_progress 问题写入 | confirmations.py | 819-833 | `issue.related_subtask_id=subtask.id` |
| `_write_single_task_report` 成果写入 | confirmations.py | 313-317 | 传入 `related_subtask_id` |
| `_write_single_task_report` 问题写入 | confirmations.py | 383-394 | `issue.related_subtask_id=subtask.id` |

注意：
- **旧格式 `key_task_issues`**（confirm:836-857, 887-906）：暂不强制设置 `related_subtask_id`，因为这些问题是汇报级别的，不针对特定关键任务
- **`achievements` / `issues` 旧格式**（confirm:860-885）：暂不强制，因为这里没有 matched_subtask_id 上下文

---

## 9. 手动登记链路改动清单

| 触发点 | 文件 | 改动 |
|--------|------|------|
| 后端 `create_achievement` | achievements.py:89-118 | Schema 自动包含，新增数据一致性校验 |
| 后端 `update_achievement` | achievements.py:140-180 | 同上 |
| 后端 `create_issue` | issues.py:172-232 | 同上 |
| 后端 `update_issue` | issues.py:270-310 | 同上 |
| 前端登记弹窗 | AchievementsPage.tsx | 启用下拉框，加载 SubTask 列表，写入字段 |
| 前端新增问题弹窗 | IssuesPage.tsx | 同上 |

---

## 10. 数据一致性校验设计

### 10.1 校验规则

核心约束：**`related_subtask_id` 指向的 SubTask 必须属于 `related_task_id` 指向的 Task**。

即：`subtask.task_id == related_task_id`

建议在后端实现一个校验函数：

```python
def validate_subtask_consistency(db: Session, related_task_id: int | None, related_subtask_id: int | None) -> None:
    """如果 related_subtask_id 存在，验证一致性。"""
    if related_subtask_id is None:
        return  # nullable，允许不设置
    subtask = db.get(models.SubTask, related_subtask_id)
    if not subtask or subtask.is_deleted:
        raise HTTPException(400, f"关键任务 #{related_subtask_id} 不存在或已删除")
    if related_task_id is not None and subtask.task_id != related_task_id:
        raise HTTPException(
            400,
            f"关键任务 #{related_subtask_id} 不属于重点工作 #{related_task_id}，"
            f"该关键任务所属重点工作为 #{subtask.task_id}"
        )
    # 如果 related_task_id 未设置但 related_subtask_id 设置了，可从 subtask.task_id 自动推导
```

### 10.2 校验点

需要在以下位置调用此校验：

| 位置 | 触发条件 |
|------|---------|
| `achievements.py create_achievement` | payload 中包含 `related_subtask_id` |
| `achievements.py update_achievement` | payload 中包含 `related_subtask_id` |
| `issues.py create_issue` | payload 中包含 `related_subtask_id` |
| `issues.py update_issue` | payload 中包含 `related_subtask_id` |
| `confirmations.py confirm` 成果写入 | 传入 `related_subtask_id` |
| `confirmations.py confirm` 问题写入 | 传入 `related_subtask_id` |

### 10.3 project_id 交叉校验

更进一步的安全性校验：SubTask 的父 Task 的 `project_id` 应与当前操作的 `project_id` 一致。

但在手动登记场景中，这条校验可能过于严格（因为一个项目的成果理论上可以被另一个项目引用），所以**建议不在 V1 阶段做跨项目校验**，只在 `related_task_id ↔ related_subtask_id` 层面做约束。

---

## 11. 兼容策略

### 11.1 向后兼容

| 场景 | 兼容策略 |
|------|---------|
| 老前端不传 `related_subtask_id` | 字段默认 `None`，后端行为与当前完全一致 |
| 老数据 `related_subtask_id = NULL` | 前端展示 "未指定关键任务"（与 N4-P2-A 已实现的展示逻辑一致） |
| 老数据 `related_task_id = NULL` 但人工指定了 `related_subtask_id` | 允许，因为关键任务自身已隐含了重点工作 | 
| API 返回新增字段 | `crud.to_dict()` 自动序列化所有列，前端 `[key: string]: unknown` 兜底 |

### 11.2 渐进启用

| 阶段 | 功能 | related_subtask_id |
|------|------|-------------------|
| PR1 | 数据库字段 + Schema + API 只读返回 | API 返回，但尚无数据写入 |
| PR2 | 前端手动登记启用关键任务选择 | 手动登记开始写入 |
| PR3 | AI 确认入库链路写入 | 确认入库开始写入 |
| PR4 | 工作汇报创建时写入 | 全链路打通 |

---

## 12. 历史数据策略

### 12.1 不回填

**历史数据的 `related_subtask_id` 保持 NULL，不进行回填。**

原因：
1. 历史汇报的 `human_result_json.task_reports[].matched_subtask_id` 可能指向已删除/已变更的 SubTask
2. JSON 中的 SubTask ID 不保证与当前数据库中的 SubTask 一一对应
3. 回填可能引入数据不一致风险
4. NULL 值前端已处理为 "未指定关键任务"

### 12.2 展示行为

| 数据情况 | related_subtask_id | 前端展示 |
|---------|-------------------|---------|
| N4-P2-A 之前的数据 | NULL | "未指定关键任务" |
| 新数据（手动绑定） | 有效 ID | "关键任务：{subtask.title}" |
| 新数据（未绑定） | NULL | "未指定关键任务" |
| 新数据（AI 确认入库绑定） | 有效 ID | "关键任务：{subtask.title}" |

---

## 13. 测试计划

### 13.1 后端测试

**文件**: `bowei_ai_dashboard/tests/test_related_subtask_id.py`（新增）

覆盖场景：

| 编号 | 测试场景 | 预期 |
|------|---------|------|
| T1 | 手动登记成果时传入 `related_subtask_id` | 成果.related_subtask_id = 传入值，成果.related_task_id 不变 |
| T2 | 手动新增问题时传入 `related_subtask_id` | 问题.related_subtask_id = 传入值 |
| T3 | `related_subtask_id` 与 `related_task_id` 不一致 | 返回 400 错误 |
| T4 | `related_subtask_id` 指向不存在的 SubTask | 返回 400 错误 |
| T5 | `related_subtask_id` 指向已删除的 SubTask | 返回 400 错误 |
| T6 | AI 确认入库 — subtask_progress 卡片 | 成果和问题的 `related_subtask_id = subtask.id` |
| T7 | AI 确认入库 — suggest_new_subtask 卡片 | 成果的 `related_subtask_id = new_sub.id` |
| T8 | 历史 NULL 数据列表查询 | 列表正常返回，`related_subtask_id` 为 null |
| T9 | 不传 `related_subtask_id` 的手动登记 | 行为与当前一致，字段为 NULL |
| T10 | 仅传 `related_subtask_id` 不传 `related_task_id` | 应允许（`related_task_id` 可从 subtask.task_id 推导），但建议允许 NULL related_task_id |

### 13.2 前端测试

**文件**: `bowei_ai_dashboard/tests/test_related_subtask_frontend.py`（新增）

覆盖场景：

| 编号 | 测试场景 |
|------|---------|
| TF1 | AchievementsPage 关键任务下拉框非 disabled |
| TF2 | AchievementsPage 选择重点工作后加载关键任务列表 |
| TF3 | AchievementsPage createAchievement payload 包含 `related_subtask_id` |
| TF4 | IssuesPage 同理（TF1-TF3 的对应项） |
| TF5 | 关键任务展示使用 `related_subtask_id` 查找名称 |
| TF6 | `related_subtask_id` 为 null 时显示 "未指定关键任务" |

### 13.3 集成测试（可选，PR3 之后）

| 编号 | 场景 |
|------|------|
| TI1 | 端到端：工作汇报 → AI 提取 → 确认入库 → 成果/问题的 `related_subtask_id` 正确写入 |
| TI2 | 端到端：手动登记成果/问题绑定关键任务 → 列表/详情正确展示 |

---

## 14. 风险点

| 风险 | 级别 | 说明 | 缓解措施 |
|------|------|------|---------|
| **确认入库 confirm() 函数复杂度高** | **高** | `confirm()` 约 400 行，包含 5+ 种写入模式，多卡片循环，新增参数容易遗漏分支 | PR3 重点测试所有写入模式 |
| **`fulfill_or_create_achievement` 存在去重逻辑** | **中** | 函数有名称相似度匹配去重，新增 `related_subtask_id` 参数可能影响去重行为 | 新增参数仅用于新记录写入，不影响去重匹配逻辑 |
| **SubTask 可能被删除** | **中** | `related_subtask_id` 指向的 SubTask 可能被软删除 | 校验时检查 `is_deleted`，展示时处理 deleted case |
| **前端下拉框数据量** | **低** | 项目中关键任务可能很多，下拉框性能 | 正常项目关键任务数量有限（10-50 个），下拉框可满足 |
| **老前端兼容性** | **低** | 老前端不发送 `related_subtask_id`，行为完全不变 | `nullable=True` + 老 schema 不校验新字段 |

---

## 15. 不做事项

明确本次方案不做：

1. ❌ 不把 `related_task_id` 改成指向 SubTask
2. ❌ 不删除 `related_task_id`
3. ❌ 不强制所有成果/问题必须绑定关键任务（`nullable=True`）
4. ❌ 不修改三层结构（Project → Task → SubTask 不变）
5. ❌ 不新增 workstream 表
6. ❌ 不新增第四层
7. ❌ 不一次性重构确认中心 `confirm()` 函数
8. ❌ 不把历史 NULL 数据强行回填
9. ❌ 不改为"关键任务必填"
10. ❌ 不在本轮增加按关键任务筛选成果/问题

---

## 16. 推荐开发拆分

按照"最小 PR、渐进交付"原则，拆为 4 个独立 PR：

### PR1：数据库字段 + Schema + 只读返回（1-2d）

**目标**: 新增 `related_subtask_id` 字段到三张表 + Schema，API 自动返回新字段，但无任何写入逻辑。

| 文件 | 改动 |
|------|------|
| `bowei_ai_dashboard/app/models.py` | 三张表各新增 `related_subtask_id = Column(Integer, ForeignKey("subtasks.id"), nullable=True)` |
| `bowei_ai_dashboard/app/schemas.py` | `AchievementPayload` / `IssuePayload` / `AchievementSubmissionPayload` 各新增 `related_subtask_id: int \| None = None` |
| **migration** | 新增 migration 文件（Alembic 或手动 SQL） |

**验证**:
- `crud.to_dict()` 自动返回新字段（无需改代码）
- 前端不修改，老逻辑不受影响
- pytest 全部通过
- `npm run build` 通过（前端类型有 `[key: string]: unknown` 兜底）

### PR2：手动登记成果 / 问题支持关键任务绑定（2-3d）

**目标**: 前端启用关键任务下拉框，手动登记时可选择关键任务，后端接收并写入。

| 文件 | 改动 |
|------|------|
| `bowei_ai_dashboard/app/routers/achievements.py` | `create_achievement` / `update_achievement` 新增数据一致性校验 |
| `bowei_ai_dashboard/app/routers/issues.py` | `create_issue` / `update_issue` 新增数据一致性校验 |
| `frontend/src/pages/AchievementsPage.tsx` | 启用关键任务下拉框，加载 SubTask 列表，展示增强 |
| `frontend/src/pages/IssuesPage.tsx` | 同上 |
| `frontend/src/api/achievements.ts` | `AchievementPayload` 类型新增 `related_subtask_id` |
| `frontend/src/api/issues.ts` | `createIssue` payload 类型新增 `related_subtask_id` |
| `bowei_ai_dashboard/tests/test_related_subtask_id.py` | T1-T5, T8, T9, T10 |
| `bowei_ai_dashboard/tests/test_related_subtask_frontend.py` | TF1-TF6 |

### PR3：AI 确认入库链路写入 related_subtask_id（3-4d）

**目标**: 确认入库时，成果和问题自动写入 `related_subtask_id`。

| 文件 | 改动 |
|------|------|
| `bowei_ai_dashboard/app/services/workflow.py` | `fulfill_or_create_achievement` 新增 `related_subtask_id` 参数 |
| `bowei_ai_dashboard/app/routers/confirmations.py` | 所有 task_reports 写入点新增 `related_subtask_id` 传参和写入 |
| `bowei_ai_dashboard/tests/test_related_subtask_id.py` | T6, T7 |
| 可能涉及: `confirmations.py` 单卡片确认路径 | `_write_single_task_report` 同 confirm 路径 |
| 可能涉及: subtasks.py | `get_subtask_detail` 改为通过 `related_subtask_id` 精确查询 |

### PR4：工作汇报 related_subtask_id 写入 + SubTask 详情反向追溯（1-2d）

**目标**: 工作汇报创建时写入 `related_subtask_id`，SubTask 详情可精确查询关联成果/问题/汇报。

| 文件 | 改动 |
|------|------|
| `bowei_ai_dashboard/app/routers/updates.py` | `create_update` 时从 `human_result.task_reports[0].matched_subtask_id` 写入 |
| `bowei_ai_dashboard/app/routers/subtasks.py` | `get_subtask_detail` 改用 `related_subtask_id` 精确查询（或双路查询） |
| `bowei_ai_dashboard/tests/` | 补充端到端测试 |

---

## 17. 实施建议与决策点

### 17.1 建议进入开发

基于全面审计，**方案 B 可行，建议进入开发**。

理由：
1. **数据库变更极轻**：三张表各新增一个 `nullable Integer` 字段，无历史数据迁移负担
2. **Schema 变更极小**：三个 Payload 各加一行 Optional 字段
3. **写入链路清晰**：6 个写入点（手动登记 2 + 确认入库 4），每个点改动明确
4. **兼容性完美**：老前端/老数据/老接口完全不受影响
5. **前端改动可控**：N4-P2-A 已做好展示框架，只需启用下拉框 + 数据源

### 17.2 需要产品确认的决策点

| 决策 | 推荐值 | 说明 |
|------|--------|------|
| 手动登记时关键任务是否必填？ | **否**（可选项） | 项目级成果/问题不应强制绑定关键任务 |
| `related_subtask_id` 设置了但 `related_task_id` 为空时怎么办？ | **允许**，并自动从 subtask.task_id 推导 `related_task_id` | 关键任务自身已隐含重点工作 |
| 历史数据显示什么？ | "未指定关键任务" | N4-P2-A 已实现 |
| SQLite 外键是否强制开启？ | **不开启**，应用层校验 | SQLite 外键默认关闭，且可能影响性能 |

---

## 18. 与 N4-P2-A 的关系

N4-P2-A（关键任务关联展示优化）已合并到 main：
- `keyTaskLabelForAchievement()` / `keyTaskLabelForIssue()` 已实现向后兼容读取
- 当本方案数据库字段落地后，这些 helper 函数可以扩展为通过 `related_subtask_id` 查找真实名称
- 不需修改 helper 返回值格式，只需改变数据来源

---

## 19. 总结

| 维度 | 结论 |
|------|------|
| **方案可行性** | ✅ 可行，最小改动，零破坏性 |
| **需新增字段的表** | 3 张：`update_submissions`, `achievements`, `issues` |
| **每个字段是否 nullable** | ✅ 是 |
| **是否需要历史回填** | ❌ 不需要 |
| **是否需要外键** | 建议声明 `ForeignKey("subtasks.id")`，但不依赖 SQLite 外键检查 |
| **推荐开发拆分** | 4 个 PR（PR1 数据库只读 → PR2 手动登记 → PR3 AI 确认入库 → PR4 汇报+追溯） |
| **最大风险点** | `confirmations.py confirm()` 函数复杂度高（400+ 行，5 种写入模式），新参数容易遗漏分支 |
| **建议进入开发** | ✅ 是 |

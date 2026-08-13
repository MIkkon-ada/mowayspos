# 跨项目工作汇报批量提交回归修复设计

## 背景

工作汇报页面支持三种归属范围：

- `all`：我的全部工作；
- `project`：指定项目；
- `task`：指定关键任务。

后端已经提供 `POST /api/updates/batch`，用于把归属完整的任务卡按项目分组，并在一个事务中创建批次及各项目的 `UpdateSubmission` 子提交。当前前端 `useVoiceSubmission` 虽然导入了 `createUpdateBatch`，但所有范围最终都调用 `createUpdate`，导致真正的跨项目汇报不能按项目拆分。

## 修复目标

恢复已经确定的提交契约：

- `task` 范围继续调用 `createUpdate`；
- `all` 和 `project` 范围调用 `createUpdateBatch`；
- 批量提交前要求每张正式任务卡都有 `parent_task_id` 和 `matched_subtask_id`；
- 一次提交尝试复用同一个 `client_request_id`，成功后清除，失败重试时继续复用；
- 提交成功后继续进入现有历史提交体验，并以首条子提交 ID 作为定位入口；
- 不修改后端批量接口、数据库结构、确认中心权限或审核状态机。

## 数据流

### 指定关键任务

```text
task
→ 将进展卡绑定到所选关键任务
→ POST /api/updates
→ 一条 UpdateSubmission
```

### 我的全部工作 / 指定项目

```text
all 或 project
→ AI 提取任务卡
→ 用户确认每张卡的项目、重点工作和关键任务归属
→ POST /api/updates/batch
→ 服务端按项目分组
→ 一个批次 + 每项目一条 UpdateSubmission
→ 各项目负责人独立审核
```

## 错误处理

- 任一任务卡归属不完整时，前端阻止正式提交并提示用户补全归属。
- 批量请求失败时保留原文、提取结果、人工编辑和 `client_request_id`，避免重试产生重复批次。
- 批量请求成功后清除 `client_request_id`。
- 后端任一项目权限、生命周期或归属校验失败时继续使用现有事务整体回滚。

## 测试设计

先修改前端契约测试并确认其在当前实现上失败，再恢复生产代码：

1. `task` 范围只调用 `createUpdate`；
2. `all/project` 范围调用 `createUpdateBatch`；
3. 批量提交包含稳定的 `client_request_id`；
4. 归属不完整时不会调用正式提交接口；
5. 成功后首条子提交 ID 可用于历史记录定位；
6. 现有前端工作汇报测试全部通过；
7. 前端构建通过；
8. 后端跨项目批量提交测试继续通过。

## 非目标

- 不重新设计三级范围选择器；
- 不强制所有汇报预先选择单个关键任务；
- 不修改 AI 提取和任务匹配规则；
- 不修改批量历史聚合规则；
- 不修改确认中心及成果、问题写回逻辑；
- 不部署到 CVM。

# 通知中心分类设计

## 1. 目标

在保留现有通知中心使用习惯的基础上，增加可理解、可筛选的业务分类，让用户能快速区分“需要处理的事项”和“状态告知”。本次设计只覆盖通知中心展示与分类规则，不改变现有业务事件，也不扩大企业微信发送范围。

## 2. 现状

当前通知中心已有两种筛选维度：

- 处理状态：全部、待我处理、仅通知。
- 时间分组：今天、昨天、更早。

通知卡片已有按 `type` 显示图标和颜色的逻辑，但业务分类不完整，且“待我处理”列表包含部分历史类型。后端实际通知由 `services.notify.send()` 写入站内通知；当前只有执行安排提醒额外调用企业微信发送服务。

## 3. 设计方案

采用两层筛选：

### 3.1 第一层：业务分类

横向展示以下分类：

1. 全部
2. 项目与成员
3. 提交审批
4. 任务执行
5. 问题决策
6. 会议
7. 成果
8. 执行提醒

第一层只回答“这条通知属于什么业务”，不表示通知是否需要处理。

### 3.2 第二层：处理状态

保留现有三个状态筛选：

- 全部：显示当前业务分类下的所有通知。
- 待我处理：显示需要用户进入业务页面继续操作的通知，未读时显示“待处理”标签。
- 仅通知：显示结果、状态或信息告知类通知。

两个筛选维度可以组合，例如“提交审批 + 待我处理”。切换任意筛选时，分页从第一页重新加载或重新计算。

### 3.3 通知卡片

卡片保留现有结构，并补充统一分类标签：

- 左侧：未读蓝点和分类图标。
- 中部：标题、分类标签、摘要。
- 右侧：时间、处理状态、操作按钮。
- 需要处理的通知使用蓝色主按钮“去处理”。
- 仅通知使用灰色按钮“查看详情”。
- 执行提醒使用黄色/橙色提示色；问题决策使用红橙色；会议使用紫色；任务使用绿色；项目使用蓝色；成果使用青绿色。

分类标签和处理状态标签同时显示，避免用一个标签承担两种含义。

## 4. 类型映射

前端集中维护 `notificationTypeConfig`，将现有后端 `type` 映射为 `category`、`label`、`tone` 和 `requiresAction`。不修改数据库字段，保留未知类型的默认分类“其他通知”，保证历史通知仍能展示。

### 项目与成员

- `project_dispatch`
- `project_returned`
- `project_kickoff`
- `project_member_added`
- `project_member_removed`
- `project_close_requested`
- `project_close_request_updated`
- `project_close_cancelled`
- `project_close_approved`
- `project_close_rejected`

### 提交审批

- `submission_pending`
- `submission_confirmed`
- `submission_rejected`
- `submission_resubmitted`
- `submission_assigned`
- `submission_transferred_to_coordinator`
- `coordinator_feedback`
- `escalate_ceo`
- `ceo_decided`
- `confirmation_card_transferred_to_coordinator`
- `confirmation_card_coordinator_feedback`
- `confirmation_card_escalate_ceo`
- `confirmation_card_ceo_decided`

### 任务执行

- `subtask_assigned`
- `subtask_completed`
- `task_status_changed`

### 问题决策

- `issue_reported`
- `issue_needs_decision`
- `issue_opinion_submitted`
- `issue_opinion_rejected`
- `issue_resolved`
- `issue_closed`

### 会议

- `meeting_draft_created`
- `meeting_published`
- `meeting_action`

### 成果

- `achievement_submitted`
- `achievement_confirmed`
- `achievement_rejected`

### 执行提醒

- `execution_schedule_start`
- `execution_schedule_due_soon`
- `execution_schedule_overdue`

## 5. 待处理规则

“待我处理”不应简单等同于“未读”。未读只表示用户尚未查看；待处理表示业务上仍需要用户行动。

建议初始规则如下：

- 待确认、待审核、待决策、待反馈、被分配、被退回、执行提醒：`requiresAction = true`。
- 已确认、已解决、已关闭、已完成、已发布、成员变更、项目启动结果：`requiresAction = false`。
- 对同一 `type` 在不同状态下语义不一致的情况，以标题和业务状态为准，后续可由后端返回显式动作状态。

## 6. 企业微信边界

本次分类不自动改变企业微信推送范围。当前实现保持：

- 所有业务通知继续写入站内通知中心。
- 只有执行安排的开始、临期、逾期提醒发送企业微信。
- 没有绑定 `wecom_userid` 时，站内通知仍保留，企业微信不发送。
- 企业微信发送失败不阻断站内通知，并保留失败记录。

后续如果要让“待我处理”类通知统一推送企业微信，应另行增加渠道策略，例如 `channelPolicy: in_app | wecom | both`，不在本次 UI 分类改造中隐式扩展。

## 7. 验收标准

- 用户可以按业务分类查看通知。
- 用户可以在业务分类内继续筛选待处理或仅通知。
- 当前已有通知类型均有明确分类，未知类型仍可展示。
- “待我处理”不再依赖过时的类型列表。
- 时间分组、未读标记、全部标记已读、点击跳转保持不变。
- 不改变现有企业微信发送范围。
- 分类切换后计数、空状态和分页结果正确。

## 8. 非目标

- 不在本次工作中新增通知事件。
- 不在本次工作中修改企业微信模板或推送策略。
- 不新增通知数据库表或迁移。
- 不重做通知中心整体视觉风格。

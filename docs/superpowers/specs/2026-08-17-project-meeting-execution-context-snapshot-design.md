# 会议纪要 Agent：项目执行事实快照设计

**状态：已确认，待编写实施计划。**

## 目标

在创建项目会议纪要时，冻结项目截至该时刻的、可审计的执行事实，使会议纪要 Agent 能将 Word 中的会议表达与项目实际执行情况交叉核验。

本设计扩展既有 `ProjectMeetingRun.snapshot_json` 和只读工具；不改变既有单 Agent、会议事实（F/M/D/C）、冻结快照、人工审核、冲突校验或回填链路。

## 事实边界

项目执行事实只能作为 `project_baseline` 使用，不能替代本次 Word 的会议证据。

- 会议事实和可写回的新业务值仍必须由 Word 原文证据支撑。
- 执行事实可用于匹配、核验、一致性/冲突提示和负责人审核信息。
- AI 不得因历史汇报、当前状态或执行事件单独产生可直接回填的新值。
- 快照创建后不可变；运行、重试和审核均以同一份冻结快照为准。

## 会议窗口

`window_start` 为当前项目最近一条已发布会议纪要的 **实际召开日期** `meeting_date`。系统当前没有会议开始时刻，因此以 `Asia/Shanghai` 自然日切分：窗口从该会议日期的次日 `00:00:00` 开始。

- 非首次会议：窗口下界不包含 `window_start` 当日，亦即 `meeting_date + 1 day 00:00:00 Asia/Shanghai`。已确认工作汇报以 `confirmed_at` 落在窗口内为准；已确认执行事件以 `occurred_at` 落在窗口内为准；两者都不得晚于 `window_end`。
- 首次已发布会议：`window_start` 为项目 `start_date`。
- `window_end` 是本次快照生成的服务器时间。
- 没有项目启动日期时，保守退化为不装载窗口型执行事实，并记录诊断原因；不得猜测起点。

会议的“已发布”属性仅用于确定哪一场历史会议可作为切分点。工作汇报没有独立的实际发生时间，必须用 `confirmed_at` 作为其进入项目事实窗口的时间；执行事件具有不可变 `occurred_at`，必须用该字段反映事件发生时间。

## 快照结构

既有项目、成员、重点工作、关键任务、子计划、近期进展和历史会议字段继续保留。每个关键任务追加 `execution_context`：

```json
{
  "window": {
    "start": "2026-07-27",
    "end": "2026-08-17T16:40:00+08:00",
    "basis": "last_published_meeting_date"
  },
  "execution_context": {
    "current_task_baseline": {
      "id": 12,
      "title": "建立人机任务分配与协同机制",
      "assignee": "温会林",
      "status": "进行中",
      "plan_time": "7.3",
      "notes": ""
    },
    "current_execution_schedules": [],
    "confirmed_reports": [],
    "confirmed_events": []
  }
}
```

`current_execution_schedules` 保留现有执行安排的 ID、标题、负责人、日期、状态、进展说明和实际产出；它表示窗口结束时的当前基线，不等同于会议结论。

### 已确认个人工作汇报

`UpdateSubmission` 是一次个人提交的父记录，可以包含多张 `task_reports` 任务卡。`confirmed_reports` 只包含窗口内、父提交状态为 `confirmed`、且明确关联当前关键任务的 **任务卡**。每条记录至少包括：

- 父提交 ID、任务卡序号、关键任务 ID、提交人及人员 ID；
- 提交时间与确认时间；`confirmed_at` 是窗口筛选字段；
- 汇报内容、实际成果、下一步；
- 事实来源 `source_type=confirmed_report` 与确认状态。

工作汇报的每张任务卡必须含有效 `matched_subtask_id` 与匹配的 `parent_task_id`。提交/保存时必须校验：重点工作与关键任务存在、未删除、两者为父子关系且属于所填项目；任一任务卡不满足则拒绝整个提交。父 `UpdateSubmission` 不要求自身只能指向一个关键任务。历史提交中无法验证归属的任务卡不补猜、不传给 AI，并记入快照诊断信息。

### 已确认执行事件

`confirmed_events` 取窗口内、`authority=confirmed` 的 `KeyTaskExecutionEvent`。每条事件至少包括：

- 事件 ID、关键任务 ID、可选子计划 ID；
- `event_type`、`source_type`、`source_id`；
- 操作者、发生/确认/生效时间；
- `status_before`、`status_after`、进展摘要、下一步；
- `display_payload` 与 `affects_current_progress`。

它让 Agent 看到“自上次会议以来发生了什么”，而不仅是本次快照时的最终状态。

## 读取与 Agent 使用

不把所有执行事实直接拼进主提示词。继续使用冻结快照上的只读工具：

1. Agent 从 Word 提取有字段级原文证据的会议事实。
2. Agent 以事实为单位批量查询关键任务候选项。
3. 对匹配关键任务读取其 `execution_context`。
4. Agent 区分 `meeting_fact`、`project_baseline`、`confirmed_report` 与 `confirmed_event`，做一致性判断、风险提示或待确认事项。
5. 现有 Normalizer/Validator 继续验证 F/M/D/C、字段来源、快照边界与会议 Word 证据；执行事实不能单独支撑一个可写回字段。

现有 `get_recent_progress` 应返回窗口信息和确定性聚合后的执行事实；计划检索详情也应能返回目标关键任务的 `execution_context`。工具一律只读冻结 `snapshot_json`，不查询分析运行后的实时数据库。

## 与既有血缘和回填的关系

- `result_json`：不可变的 AI 原始 F/M/D/C 与原始 proposed changes。
- `snapshot_json`：项目、目标、父级、执行事实基线和项目边界。
- `lineage_json`：字段来源、血缘 schema、owner edit history、baseline state 和 parent baseline。
- `meeting_fact` 的字段值必须有本次 Word 字段级证据；`project_baseline` / `confirmed_report` / `confirmed_event` 只能用于继承、比对或解释，不能伪装成会议新增值。
- 负责人编辑、审批、CREATE/UPDATE stale/conflict 检查的既有规则不变。

## 错误处理与诊断

- 缺少可用历史会议时按项目启动日处理；缺少项目启动日时不臆造窗口。
- 缺少有效关键任务归属的历史任务卡不进入 Agent 输入，写入 `snapshot.diagnostics`。
- 异常或为空的汇报/事件字段保留为空值并标明来源，不作 LLM 补全。
- 快照中没有子计划、没有已确认汇报或没有执行事件是合法空结果，不是 Agent 错误。

## 非目标

- 不把待审核、退回、撤销的汇报或事件作为项目事实传入 AI。
- 不新建多 Agent 架构，不改变会议纪要页面展示字段。
- 不回填、修改或修复历史执行数据。
- 不把会议分析扩展到驾驶舱、工作汇报或其他业务模块。

## 验收测试

1. 已确认汇报仅按其关联关键任务归集，且仅取窗口内数据。
2. 已确认执行事件保留状态前后值、来源和时间；非 confirmed 事件不进入快照。
3. 首次正式会议从项目启动日起取数；后续会议从上次已发布会议的实际召开日期取数。
4. 任一任务卡无有效关键任务归属时，提交接口拒绝整个工作汇报；遗留异常任务卡不进入 Agent 输入并产生诊断。
5. 快照生成后，实时任务、汇报或子计划变化不会改变该次运行的 Agent 输入。
6. `get_plan_node_detail` 与 `get_recent_progress` 只返回冻结执行事实，不读取实时库。
7. Normalizer 拒绝仅凭 `project_baseline`、`confirmed_report` 或 `confirmed_event` 创建可回填字段值的输出。

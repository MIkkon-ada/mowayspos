# 工作汇报双栏模板设计

## 目标

将“工作汇报”页面改为参考稿的双栏工作台：左侧用于录入汇报，右侧用于查看 AI 提取结果。保留现有业务数据、AI 提取、人工编辑、附件上传、提交和历史记录逻辑；底部的草稿、提交及状态提示区域保持现状。

## 范围

本次只调整前端页面结构与视觉样式，涉及：

- `frontend/src/pages/VoiceUpdatePage.tsx` 的页面内容区组织；
- `frontend/src/features/voice-update/VoiceUpdateInputPanel.tsx` 的左栏卡片呈现；
- `frontend/src/features/voice-update/VoiceUpdateResultCard.tsx` 和 `VoiceUpdateTaskReportsSection.tsx` 的右栏分组呈现；
- `frontend/src/features/voice-update/voiceUpdateFlow.css` 的布局、卡片和响应式样式；
- `frontend/tests/workReportFlowPage.test.mjs` 的结构性回归测试。

不改动后端接口、AI 返回契约、任务归属校验、提交写入逻辑、历史抽屉与底部提交组件。

## 页面结构

1. 顶部保留“工作汇报”标题、现有汇报范围选择、任务选择和“历史提交”入口；仅按参考稿压缩为一行工作台头部，不替换其功能。
2. 主内容区在桌面端使用两栏布局：左栏为“提交工作汇报”，右栏为“AI 提取结果”。两栏是独立白色卡片，带统一边框、圆角、标题栏和内边距；栏宽沿用现有约 40/60 的信息比例。
3. 左栏保留文字、录音、上传音频、上传文档四种输入方式，原始汇报输入框、字数提示、引导语、模型选择及 AI 提取动作均保留，只调整为参考稿的卡片层级与间距。
4. 右栏在提取后按固定顺序显示：本次完成、下一步计划、问题与风险、取得的成果；每组为独立信息卡。原有任务归属、原文证据、可编辑字段、成果附件及任务状态建议仍可用，但作为对应卡片的展开/编辑内容，不被移除。
5. 没有提取结果时，右栏展示当前的可读空态；提取中、失败与重新提取仍使用既有状态和动作，不伪造任何示例业务文本。
6. 窄屏下两栏按左、右顺序堆叠，顶部选择项与底部操作区继续使用当前响应式行为。
7. 页面最底部的 `VoiceUpdateSubmitPanel` 不调整 DOM 位置、文案、按钮、状态或交互，仅与新主内容区保持现有分隔线关系。

## 数据与交互

右侧只消费现有 `taskReports`、`keyTaskIssues` 和既有 `result` 派生数据：

- “本次完成”绑定 `TaskReport.completed`；
- “下一步计划”绑定 `TaskReport.next_steps`；
- “问题与风险”绑定 `TaskReport.subtask_issues` 以及匹配的重点工作问题；
- “取得的成果”绑定 `TaskReport.achievements`，继续支持现有附件上传；
- “任务状态建议”、归属确认、原文证据和多任务切换保持现有状态与提交前校验。

参考图中的示例文字、任务名和勾选状态均不进入代码或默认数据。

## 验收与测试

- 工作汇报页面仍由 `/work/submit` 提供，四种输入模式、AI 提取、重新提取、人工编辑、附件上传和提交均保持可访问。
- 页面主体在桌面端为两栏独立卡片，在 899px 以下变为单栏堆叠。
- 右栏可识别四个既有数据分组，且没有任何截图示例数据硬编码。
- `VoiceUpdateSubmitPanel` 继续位于页面最底部，并保留现有底栏测试约束。
- 更新结构测试后，运行 `node --test tests/workReportFlowPage.test.mjs`、前端单元测试和生产构建。

# Agent Skill 阻断式澄清会话 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为会议 Skill 建立可暂停、可提问、可续跑的通用澄清会话机制，首期接入验收与回款周例会 Skill。

**Architecture:** 会议编排服务创建并持久化一次运行及其冻结输入；`preflighting` 仅返回结构化澄清题，不调用正式纪要生成。预检没有阻断问题时直接进入 `running`；有阻断问题时才进入 `waiting_for_answers`。缺材料使用补充文件动作并重跑预检，其他阻断题处置后才转为版本化的已确认事实并进入 `running`。

**Tech Stack:** FastAPI、SQLAlchemy/Alembic、Pydantic、React/TypeScript、现有会议分析模型与测试框架。

---

## 文件结构

- 新建 `bowei_ai_dashboard/app/services/meeting_skill_registry.py`：Skill 元数据、路由规则和预检接口。
- 新建 `bowei_ai_dashboard/app/services/meeting_skill_clarification.py`：问题构建、答案校验、答案版本、已确认事实、状态转换和续跑编排。
- 修改 `bowei_ai_dashboard/app/models.py`：为分析运行增加 Skill 与状态字段，并新增输入快照版本、澄清问题、追加式回答修订、已确认事实表。
- 新建 `bowei_ai_dashboard/migrations/versions/<revision>_add_meeting_skill_clarifications.py`：新增表及索引。
- 修改 `bowei_ai_dashboard/app/schemas.py`：运行、问题、答案、预检和续跑请求响应模型。
- 修改 `bowei_ai_dashboard/app/routers/meetings.py`：新增 Skill 预检、读取问题、提交答案、续跑接口；现有标准 Word 路径保持不变。
- 新建 `frontend/src/features/meeting/MeetingSkillClarification.tsx`：问题卡片和流程状态页。
- 修改 `frontend/src/api/meetings.ts`、`frontend/src/features/meeting/NewMeetingModal.tsx`：调用预检、回答和续跑接口。

### Task 1: Skill 注册表与预检契约

- [ ] 写后端失败测试：`tests/test_meeting_skill_registry.py`，验证 `weekly-meeting-minutes` 只有在验收/回款周例会类型下被路由，缺转写、明细表或上期纪要时返回 `question_kind="missing_material"` 的阻断预检项；补充材料后必须重新执行预检而不是提交普通问答答案。
- [ ] 运行 `python -m pytest tests/test_meeting_skill_registry.py -q`，确认失败原因是注册表不存在。
- [ ] 新建 `meeting_skill_registry.py`，定义 `MeetingSkillDefinition`、`SkillPreflightInput`、`ClarificationDraft` 和 `route_meeting_skill()`；注册 `weekly-meeting-minutes` 的材料门槛和问题代码。
- [ ] 重跑同一测试，确认通过。

### Task 2: 持久化运行与澄清题

- [ ] 写失败测试：`tests/test_meeting_skill_clarification.py`，创建预检运行后断言 `preflighting` 从不调用正式生成器；无阻断项时直接进入 `running`；有阻断项时才进入 `waiting_for_answers`，问题含结构化证据定位、候选项、`question_kind`、`blocking` 与 `required`，且没有正式纪要输出。
- [ ] 运行该测试，确认失败原因是模型/服务不存在。
- [ ] 增加 `MeetingSkillInputSnapshot`、`MeetingSkillClarification`、`MeetingSkillClarificationAnswerRevision`、`MeetingSkillResolvedFact` 模型；运行增加 `skill_name`、`skill_version`、`status`、`current_input_snapshot_id` 字段。补充材料时追加新的输入快照而不覆盖旧快照；问题保存 `question_kind`、`blocking` 与结构化证据；答案以递增修订号追加保存；已确认事实保存机器值、展示值、证据和所用答案版本。
- [ ] 创建 Alembic 迁移，只增加新表/列/索引，不触碰已有会议内容。
- [ ] 在 `meeting_skill_clarification.py` 实现 `start_preflight()`；创建问题后设置 `waiting_for_answers`。
- [ ] 重跑测试，确认通过。

### Task 3: 服务端回答门禁与续跑

- [ ] 写失败测试：存在未处置阻断题调用 `resume_run()` 返回冲突；`required=true + allow_omit=true` 的题在选择“不写入纪要”后视为已处置；记录员回答后追加新 `answer_revision` 而不覆盖旧值；续跑前生成 `ResolvedFact`。
- [ ] 运行测试，确认失败。
- [ ] 实现 `submit_answers()`：按题目类型校验选项、其他填空和“不写入”权限并追加答案修订；实现 `resolve_facts()`：将确认答案、唯一参考匹配和规则推导写入 `ResolvedFact`；实现 `resume_run()`：仅以未处置的 `blocking=true` 题作为门禁，冻结答案版本集合与事实集后调用该 Skill 的正式执行器。校验首期不变量：`blocking=true` 必须同时 `required=true`，`required=false` 不得阻断运行。
- [ ] 对普通成员、项目负责人、企业教练分别写权限测试，确认三者都能回答项目内运行，项目外用户被拒绝。
- [ ] 重跑该测试集，确认通过。

### Task 4: API 与通用会议流程接入

- [ ] 写路由测试，覆盖：创建预检、查询运行问题、提交答案、存在阻断题时续跑 409、答完后续跑成功；并覆盖直接调用草稿/Word/Excel/保存接口时仍因阻断题被服务端拒绝。
- [ ] 运行测试，确认失败。
- [ ] 在 `meetings.py` 增加：
  - `POST /api/meetings/skill-runs/preflight`
  - `GET /api/meetings/skill-runs/{run_id}`
  - `POST /api/meetings/skill-runs/{run_id}/answers`
  - `POST /api/meetings/skill-runs/{run_id}/resume`
- [ ] 保持 `extract-document-text` 的标准 Word 严格校验优先级；标准 Word 直接进入原样保留，不创建 Skill 运行。
- [ ] 重跑路由测试，确认通过。

### Task 5: 记录员问答界面

- [ ] 写前端静态/组件测试，验证 `MeetingSkillClarification` 能渲染证据、候选项、其他输入和“不写入”；`missing_material` 渲染“补充文件”操作而非普通问答控件；存在未处置阻断题时禁用“生成会议纪要”。
- [ ] 运行测试，确认失败。
- [ ] 新建 `MeetingSkillClarification.tsx`；用题目 `answer_mode` 渲染单选、多选、文本输入；`missing_material` 显示缺失说明和补充文件入口，补充后创建新的输入快照版本并重跑预检；显示候选依据和按来源可选的原文证据。
- [ ] 修改 `NewMeetingModal.tsx`：非标准输入点击预检而非直接分析；进入澄清状态时保存 `run_id`，将“必答”展示为“必须明确处置”，而非“必须填业务值”；答案齐全后调用续跑并进入既有确认页。
- [ ] 修改 `api/meetings.ts` 定义 API 类型和调用函数。
- [ ] 重跑前端测试与 `npm run build`，确认通过。

### Task 6: 端到端回归与人工验收

- [ ] 后端运行 `python -m pytest tests/test_meeting_skill_registry.py tests/test_meeting_skill_clarification.py tests/test_meeting_document_text.py -q`。
- [ ] 前端运行相关 Node 测试和 `npm run build`。
- [ ] 使用非标准周例会转写执行：预检 → 回答一个项目匹配问题 → 回答一个上期待办状态问题 → 续跑 → 确认页。
- [ ] 使用标准 Word 执行上传，确认其仍跳过 Skill 预检并保留 Word 原始结构。
- [ ] 在完成数据库备份并获得明确授权后，执行新增迁移；若未获授权，只交付迁移文件和验证结果。

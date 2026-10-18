# 退回工作汇报重新提取与核对实施计划

> **For agentic workers:** Execute inline in this session. Follow the repository instruction not to create or delegate subagents.

**Goal:** 让退回汇报经修订文字重新提取、人工核对后更新原记录并再次进入负责人审核。

**Architecture:** 退回详情跳转到现有 `/work/submit` 工作台并传原汇报 ID；工作台复用提取、卡片归属与校验状态，最终调用现有 resubmit API。后端要求新的结构化核对结果并用新文字、结果更新原记录，同时保留前后审计快照。

**Tech Stack:** React、TypeScript、Vitest、FastAPI、SQLAlchemy、pytest。

---

### Task 1: 复用工作汇报工作台完成退回汇报修订

**Files:**
- Modify: `frontend-v2/src/features/voice-update/VoiceUpdateDetailDrawer.tsx`
- Modify: `frontend-v2/src/pages/VoiceUpdatePage.tsx`
- Modify: `frontend-v2/src/features/voice-update/useVoiceExtraction.ts`
- Modify: `frontend-v2/src/features/voice-update/useVoiceSubmission.ts`
- Modify: `frontend-v2/src/features/voice-update/VoiceUpdateSubmitPanel.tsx`
- Test: `frontend-v2/src/features/voice-update/VoiceUpdateDetailDrawer.test.tsx` and focused workbench flow test

- [ ] 先新增一个前端流程用例：打开退回汇报，点“修改并重新提取”，带原 ID 和原文字进入工作台；修订后提取，核对结构化结果，最终只调用同 ID 的 resubmit 并发送新文字与完整 `human_result`，不调用 create、batch 或草稿创建接口。
- [ ] 运行该用例确认当前实现因抽屉直接重提、未重新提取而失败。
- [ ] 增加修订模式上下文：保留项目/任务范围、退回原因、原记录 ID 和按用户/原记录隔离的本地修订草稿；退出可恢复，成功后清理。
- [ ] 在提取失败时清空上次候选结构化结果并保持修订文字；提取成功才允许核对和重提。
- [ ] 复用现有结果核对、归属和必填校验；最终按钮改为“核对无误，重新提交”，只调用 resubmit，成功后刷新历史并显示原汇报待审核状态。
- [ ] 运行前端流程用例并确认通过；对提取失败与 resubmit 失败各补最小断言，确保文字保留且不能以旧结果重提。

### Task 2: 强制后端仅接受新的核对结果

**Files:**
- Modify: `bowei_ai_dashboard/app/schemas.py`
- Modify: `bowei_ai_dashboard/app/routers/confirmations.py`
- Test: `bowei_ai_dashboard/tests/test_submission_submitter_identity_flow.py`

- [ ] 先新增一个接口测试：带修订文字与完整 `human_result` 重提同一条已退回记录，断言 ID 不变、状态回待审核、新人工结果替换旧结果且审计日志保留修改前后数据。
- [ ] 先新增缺失/空 `human_result` 的拒绝断言，运行测试确认当前后端会错误接受旧结果。
- [ ] 将 resubmit 请求的 `human_result` 设为必填非空对象；在状态切换前拒绝缺失或空值，避免退回内容被旧卡片覆盖/冒充新结果。
- [ ] 用新结果覆盖原记录人工结果，补充说明并记录审计前后快照；保持原提交人权限、退回状态校验和通知行为。
- [ ] 运行该测试文件中与 resubmit 相关的定向用例，确认通过。

### Task 3: 汇总最少验证并记录验收边界

**Files:**
- Modify: `docs/acceptance/2026-10-18-current-branch-verification.md`

- [ ] 运行前端修订成功/失败流程用例及后端 resubmit 定向用例。
- [ ] 运行 `npm.cmd run build` 确认前端类型检查与构建结果。
- [ ] 运行 `git diff --check`；记录浏览器/AI 服务的真实链路是否可用，若服务未配置或不可达，明确保留该人工验收项未通过。
- [ ] 只在本次端到端行为和构建结果满足标准时，将对应验收表事项更新为通过；不把 mock 测试当作 AI 服务验收，也不签收未验证项目。

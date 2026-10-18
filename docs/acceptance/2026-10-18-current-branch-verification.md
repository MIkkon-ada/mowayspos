# 当前分支定向验收证据（2026-10-18）

## 版本与范围

- 分支：`codex/project-work-progress-wbs`
- 被测代码提交：`6b29a26`（退回汇报编辑后原记录重提）；本记录更新到该代码提交。
- 本记录只汇总当前工作区代码的定向验证，不替代验收表中的逐项签收，也不代表生产版本。

## 已取得的证据

| 范围 | 检查 | 结果 | 证据边界 |
| --- | --- | --- | --- |
| C10 工作推进表汇报状态 | 后端投影专项 | 6 passed | 覆盖已确认、待处理、空汇报、旧项目名称映射和跨项目错链；不覆盖真实账号浏览器操作 |
| C10 工作推进表展示 | `PlanTableViewV2` 专项 | 10 passed | 验证无汇报与待确认状态分开显示，待确认正文不显示为正式进展 |
| C10 前端交付 | TypeScript/Vite 构建、bundle 预算 | 通过 | ExcelJS 仍有非首屏大 chunk 警告；包体积门槛检查通过 |
| D01-D04、D08、E01、E04、G01-G02、H03 的部分 API 主链 | 多角色生命周期及汇报回写测试 | 14 passed | 隔离 SQLite 直接调用 API；覆盖下发、方案审核、成员提交、统筹/教练流转、PM 确认、问题与成果关联、结束申请与审批；D05 重提见下一行；不含问题独立处理状态闭环、会议全链路或真实浏览器会话 |
| D05 退回汇报修改重提 | 提交人身份与通知模块 + 原记录修订专项 | 28 passed；退回详情组件 1 passed | 同一提交记录可修改正文后重回待负责人审核；审计日志保留原文与修订文；前端提交原 ID 和修订正文；验证未提前创建问题/成果。**部分实现**：重提当前未基于新正文重新生成结构化 AI 结果；仍未覆盖真实浏览器双角色操作 |
| E01、E04 回写与附件绑定 | 汇报确认、资产回写和成果附件专项 | 5 passed | 验证问题/成果归属、跨项目错链拒绝、重复确认防重、附件转入成果；不含成果库真实下载、外部存储可读性和附件越权访问 |
| F01-F03、F05 会议文档和选择性回写 | 文档存取、分析确认、变更应用与启动会边界专项 | 10 passed | 当前代码保留 Word 表格行列及分页符；覆盖证据绑定、人工选择后写入、防重复、待审核项目保护与历史启动兼容；不含真实 AI 质量抽检、浏览器截图和多页真实文档覆盖率核对 |
| G04 归档权限和状态边界 | 两个归档相关测试模块筛选 | 11 passed，76 deselected | 验证非技术管理员受限、已结束项目才可归档等代码规则；不替代生产审计日志或真实账号操作 |
| H04 局部门禁 | 后端 touched-file 编译；上述前端定向测试、构建及体积检查 | 通过 | 本次没有重跑全量 V2、契约或后端测试套件 |

## 当前未通过整体验收的原因

1. 验收标准 HTML 的 60 项记录默认均为“本次未验收”。历史记录和定向测试结果没有自动改写为本次签收。
2. 当前浏览器没有有效的 MOWAYS 登录会话；之前接口返回 `401`。因此尚无独立 PM、企业教练、成员账号下的页面操作截图和真实对象 ID 对照。
3. E/F 等业务链路的完整闭环、H04 全量门禁，以及 H06 目标数据库迁移、恢复和部署冒烟仍需当前版本证据。

## 可复现的定向命令

在 `bowei_ai_dashboard` 执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_work_progress_latest_submission.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_full_role_lifecycle_audit.py tests/test_execution_submission_to_work_progress_flow.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_submission_submitter_identity_flow.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_confirmation_asset_writeback.py tests/test_achievement_attachments.py -k "w1_report_assets_write_once_with_subtask_attribution or cross_project_matched_subtask_is_rejected_without_asset_write or second_confirm_is_rejected_and_does_not_duplicate_assets or confirming_submission_moves_bound_attachment_to_achievement or submission_confirmation_creates_one_achievement" -q
.\.venv\Scripts\python.exe -m pytest tests/test_meeting_document_text.py tests/test_meeting_progress_review_api.py::test_analyze_persists_pending_evidence_bound_rows tests/test_meeting_progress_review_api.py::test_confirm_review_updates_subtask_and_marks_accepted -q
.\.venv\Scripts\python.exe -m pytest tests/test_project_meeting_minutes_service.py::test_meeting_document_storage_hashes_reads_and_rejects_unsafe_inputs tests/test_meeting_progress_review_api.py::test_analyze_persists_pending_evidence_bound_rows tests/test_meeting_progress_review_api.py::test_confirm_review_updates_subtask_and_marks_accepted tests/test_meeting_change_set_writeback.py::test_execution_requires_owner_explicit_selection_and_nonblocked_rows tests/test_meeting_change_set_writeback.py::test_patch_revalidates_and_selected_four_actions_execute_with_audit tests/test_meeting_change_set_writeback.py::test_stale_selected_target_rejects_entire_batch_without_partial_create tests/test_meeting_change_set_writeback.py::test_saved_meeting_requires_reviewed_selection_before_any_plan_write tests/test_kickoff_writeback.py::test_active_project_allows_normal_meeting_creation tests/test_kickoff_writeback.py::test_active_project_allows_kickoff_event tests/test_kickoff_writeback.py::test_legacy_pending_kickoff_project_allows_normal_meeting_creation -q
.\.venv\Scripts\python.exe -m pytest tests/test_project_close_lifecycle_guards.py tests/test_project_permission_characterization.py -k archive -q
.\.venv\Scripts\python.exe -m compileall -q app\routers\subtasks.py
.\.venv\Scripts\python.exe -m compileall -q app\services\meeting_document_text.py
```

在 `frontend-v2` 执行：

```powershell
npm.cmd run test:unit -- --run src/components/task-management/PlanTableViewV2.test.tsx
npm.cmd run test:unit -- --run src/features/voice-update/VoiceUpdateDetailDrawer.test.tsx
npm.cmd run build
npm.cmd run check:bundle:dist
```

**判定：推进表的待确认状态和部分角色 API 主链已有定向通过证据；项目整体尚未验收通过。**

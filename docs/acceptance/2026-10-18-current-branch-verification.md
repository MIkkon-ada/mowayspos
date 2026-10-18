# 当前分支定向验收证据（2026-10-18）

## 版本与范围

- 分支：`codex/project-work-progress-wbs`
- 当前代码提交：`2c74333`（工作推进表待确认汇报状态）
- 本记录只汇总当前工作区代码的定向验证，不替代验收表中的逐项签收，也不代表生产版本。

## 已取得的证据

| 范围 | 检查 | 结果 | 证据边界 |
| --- | --- | --- | --- |
| C10 工作推进表汇报状态 | 后端投影专项 | 6 passed | 覆盖已确认、待处理、空汇报、旧项目名称映射和跨项目错链；不覆盖真实账号浏览器操作 |
| C10 工作推进表展示 | `PlanTableViewV2` 专项 | 10 passed | 验证无汇报与待确认状态分开显示，待确认正文不显示为正式进展 |
| C10 前端交付 | TypeScript/Vite 构建、bundle 预算 | 通过 | ExcelJS 仍有非首屏大 chunk 警告；包体积门槛检查通过 |
| D01-D04、D08、G01-G02、H03 的部分 API 主链 | 多角色生命周期及汇报回写测试 | 14 passed | 隔离 SQLite 直接调用 API；覆盖下发、方案审核、成员提交、统筹/教练流转、PM 确认、结束申请与审批，不含退回重提、问题/会议全链路或真实浏览器会话 |
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
.\.venv\Scripts\python.exe -m pytest tests/test_project_close_lifecycle_guards.py tests/test_project_permission_characterization.py -k archive -q
.\.venv\Scripts\python.exe -m compileall -q app\routers\subtasks.py
```

在 `frontend-v2` 执行：

```powershell
npm.cmd run test:unit -- --run src/components/task-management/PlanTableViewV2.test.tsx
npm.cmd run build
npm.cmd run check:bundle:dist
```

**判定：推进表的待确认状态和部分角色 API 主链已有定向通过证据；项目整体尚未验收通过。**

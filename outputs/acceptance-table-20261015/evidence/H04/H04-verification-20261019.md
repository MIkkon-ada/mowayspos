# H04 V2 测试与构建门禁

- 验收时间：2026-10-19 15:04–15:11（Asia/Shanghai）
- 工作分支：`codex/project-work-progress-wbs`
- 验证对象：本地当前工作区；验证时基于提交 `1c54ed7` 加本轮未提交差异。

## 本轮命令与结果

| 命令 | 退出码 | 结果 |
| --- | ---: | --- |
| `frontend-v2: npm run test:all` | 0 | 63 个单元测试文件、193 项通过；契约测试 528 项通过（19 个套件） |
| `frontend-v2: npm run build` | 0 | TypeScript 检查及 Vite 生产构建通过，253 个模块转换 |
| `bowei_ai_dashboard: .venv/Scripts/python.exe -m pytest -q tests/test_owner_plan_draft.py tests/test_project_init_work_progress_draft.py tests/test_task_create_idempotency.py tests/test_task_batch_create_idempotency.py tests/test_manual_related_subtask_binding.py` | 0 | 82 项后端相关回归通过，20.94 秒 |

前端构建保留一条既有提示：`exceljs` 产物超过 500 kB；构建退出码为 0，没有 TypeScript 或打包错误。

## 验收范围

本次覆盖本地 V2 前端单元、前端契约、TypeScript/生产构建，以及立项草稿、立项推进表草稿、任务创建幂等和跨项目关联保护相关后端回归。未执行完整后端全量测试；未连接生产 PostgreSQL，未验证部署环境、生产迁移、备份恢复或线上冒烟。上述未覆盖项不计作本次通过证据。

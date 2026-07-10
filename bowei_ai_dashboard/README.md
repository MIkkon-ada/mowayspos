# 博维 AI 升级项目驾驶舱 - 后端说明

这是后端主项目，负责 FastAPI API、认证、数据库和业务逻辑。

## 当前定位

- 后端只提供 API
- 前端是独立的 `frontend/` 项目
- 业务口径以三份外部主文档为准：
  - `博维 AI 驾驶舱项目三层结构与字段口径编写计划.docx`
  - `博维 AI 驾驶舱项目生命周期与权限动作口径.docx`
  - `博维AI驾驶舱的角色与权限口径.docx`

## 业务摘要

当前项目的主线可以概括为：

```text
项目
  └─ 重点工作
      └─ 关键任务
```

关键角色边界：

- 公司 CEO：创建项目入口、配置人员、全局查看
- 企业教练：项目内最高把关角色，负责方向、重大事项和结束复盘把关
- 项目负责人 / PM：日常推进、启动会、任务派发、汇报确认、入库和闭环
- 项目统筹人：协调与建议，不默认拥有最终确认权
- 关键任务责任人：执行任务并提交汇报
- 关键任务协助人：辅助执行并反馈进展

## 数据库与迁移

当前默认仍可使用本地 SQLite 文件 `bowei_ai_dashboard.db` 启动和开发。正式上线前的数据库方案仍需结合后续决策。

如果本地已有旧数据库，建议先按顺序执行迁移脚本，再启动服务：

```bash
python migrate_sqlite_schema.py --report-only
python migrate_project_extended_columns.py --report-only
python migrate_project_members.py --report-only
```

确认报告无重大异常后，再按实际环境决定是否执行 `--execute`。不要把 `--execute` 当作默认启动步骤。

> 说明：如果你需要执行某个 SQL Schema 文件，请按你的实际仓库位置替换路径，不要直接照抄占位路径。

## 启动方式

本地开发推荐使用仓库根目录下的 `start-backend-dev.bat`，它会创建本地虚拟环境并启动后端开发服务。

如果你只想手动启动后端，也可以直接执行：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8008
```

如果 `DATABASE_URL` 未设置，项目会默认使用本地 SQLite 文件 `bowei_ai_dashboard.db`。

## 数据与接口

后端启动时会注册项目、重点工作、关键任务、成果、问题、会议、进展提交和 AI 确认中心等 API。

当前系统以 `project_id` 作为项目主标识，页面和接口之间通过映射层兼容旧字段名；业务展示上优先使用“重点工作”“关键任务”“责任人”“协助人”等新口径。

主要接口包括：

- `GET /api/dashboard/overview`
- `POST /api/updates/extract`
- `GET /api/confirmations/pending`
- `GET /api/confirmations/{id}`
- `POST /api/confirmations/{id}/save`
- `POST /api/confirmations/{id}/confirm`
- `POST /api/confirmations/{id}/reject`
- `POST /api/confirmations/{id}/mark-unrecognized`
- `GET/POST/PUT/DELETE /api/tasks`
- `GET/POST/PUT/DELETE /api/achievements`
- `GET/POST/PUT/DELETE /api/issues`
- `GET/POST/PUT/DELETE /api/people`

## 说明

- 如果你要看页面，请打开 `frontend/`
- 如果你要改接口，请看 `app/routers/`
- 如果你要改数据库结构，请看 `app/models.py`
- 上线前仍需补齐数据库治理、权限复测和部署方案，不要把当前状态视为正式生产完成

## SQLite Backup / Restore SOP

SQLite trial backup and restore guidance lives in [docs/DB_BACKUP_RESTORE_SOP.md](docs/DB_BACKUP_RESTORE_SOP.md).

## 上线验收

离线上线验收清单与 UAT 执行计划分别见 [docs/LAUNCH_ACCEPTANCE_CHECKLIST.md](docs/LAUNCH_ACCEPTANCE_CHECKLIST.md) 和 [docs/UAT_TEST_PLAN.md](docs/UAT_TEST_PLAN.md).

## 服务器准备

服务器预检、环境准备和 L4-2 运行态验证清单见 [docs/SERVER_PROVISIONING_CHECKLIST.md](docs/SERVER_PROVISIONING_CHECKLIST.md) 与 [docs/L4_SERVER_VALIDATION_CHECKLIST.md](docs/L4_SERVER_VALIDATION_CHECKLIST.md).

## 部署接线 SOP

同域前后端部署、Nginx 接线和 systemd service 说明见 [docs/DEPLOYMENT_SOP.md](docs/DEPLOYMENT_SOP.md).

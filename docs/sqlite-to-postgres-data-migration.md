# SQLite → PostgreSQL 数据迁移工具

本工具用于一次性、显式地把已经审计的 Moways SQLite 业务数据迁移到一个已完成 Alembic 建表、且业务表为空的 PostgreSQL 数据库。工具默认 fail closed，不会创建表、升级 schema、合并两套数据或覆盖目标记录。

## 安全边界

- SQLite 源文件必须使用绝对路径，并始终通过 `file:...?...mode=ro` 只读打开。
- PostgreSQL 地址只从环境变量 `DATABASE_URL` 读取，不能作为命令行参数传入，避免凭证进入 shell history。
- `--dry-run` 与 `--apply` 互斥，必须显式选择一个模式。
- 目标必须是 PostgreSQL，并且必须已经位于仓库当前唯一 Alembic head。
- 除 `alembic_version` 外，目标业务表必须为空；任一业务记录存在都会拒绝 apply。
- 工具不得执行 Alembic、`create_all`、downgrade、delete、upsert 或覆盖操作。
- 整次 apply 在单一 PostgreSQL transaction 中完成；任一表失败都会整体 rollback。
- 不使用 `SET session_replication_role = replica`，也不关闭外键约束。
- `auth_sessions` 和 `login_attempts` 明确排除：Session、登录 IP、失败次数及锁定记录属于环境性安全数据。
- 日志和 JSON 报告不包含密码哈希、Session 哈希、API Key、正文、完整数据库 URL 或其他凭证。

## 迁移前盘点与备份

1. 使用只读连接执行 `PRAGMA integrity_check`，结果必须为 `ok`。
2. 记录源文件 SHA-256、Alembic revision、表级行数、字段/约束及孤儿引用。
3. 使用 SQLite online backup API 创建一致性备份；不得用普通文件复制替代，以免遗漏 WAL。
4. 对备份再次执行完整性检查，并核对关键表行数。
5. 备份必须位于 Git 仓库外或被忽略的本地归档目录，不得上传 GitHub 或腾讯云。

## ????????????

????????????????? profile ????? Alembic head ?? `projects` ????

- `project_type`
- `client_name`
- `background`
- `objectives`
- `expected_outcomes`
- `lifecycle_status`
- `kickoff_date`
- `kickoff_by`
- `initiated_by`

`status` ???????????`lifecycle_status` ????????????????????? `status` ???`status` ????? `is_active` ?? `active` ? `archived`??????? `status` ??? `is_active`?

????????????? archive-only ?????? PostgreSQL?????????????????????????? SQLite ????????????????????????????

- `achievements.is_desensitized`
- `issues.feedback_required`
- `people.employee_code`?????? username?
- `people.permission_scope`????????? RBAC?
- `people.title`??????? `role`?
- `update_submissions.workflow_status`???????

`update_submissions.ceo_decision_required` ? derived canonical ???????????????????????????? `confirmation_status=pending_ceo_decision`???????? `derived_and_verified`???????? PostgreSQL ??????????? dry-run/apply?

????????????????? source-only ????? fail closed??????????? schema ??????????

> ?????????????? downgrade ????? revision???????? profile ???????????????????????

## Dry-run

先为本地隔离 PostgreSQL 创建当前 schema。工具本身不得执行 Alembic；schema 准备必须由独立、已审批的步骤完成。

PowerShell 示例：

```powershell
$env:DATABASE_URL = "postgresql+psycopg://<user>:<password>@127.0.0.1:<port>/<database>"
python bowei_ai_dashboard/scripts/migrate_sqlite_to_postgres.py `
  --source-sqlite "D:\absolute\path\source.db" `
  --dry-run `
  --report-json "$env:TEMP\moways-sqlite-migration-dry-run.json"
```

dry-run 只做读取和验证，不写目标库。报告包含：

- source SHA-256、revision、表级行数；
- target revision 和迁移前行数；
- 依据目标外键生成的拓扑顺序；
- 计划迁移表、明确排除表及原因；
- source/target/ORM schema 差异；
- 孤儿外键、唯一冲突、字段映射和 blocking errors；
- 预计行数和 `apply_allowed`。

只有源库完整、schema 可映射、目标为当前 head 且为空，并且所有阻断计数为零时，`apply_allowed` 才能为 `true`。

## Apply

只有经过审查的 dry-run 报告允许进入 apply。再次使用同一只读源文件和一个仍为空的 PostgreSQL 目标：

```powershell
$env:DATABASE_URL = "postgresql+psycopg://<user>:<password>@127.0.0.1:<port>/<database>"
python bowei_ai_dashboard/scripts/migrate_sqlite_to_postgres.py `
  --source-sqlite "D:\absolute\path\source.db" `
  --apply `
  --report-json "$env:TEMP\moways-sqlite-migration-apply.json"
```

apply 会重新加锁并复核目标为空和 revision 一致，然后：

1. 按实际 PostgreSQL 外键及已审计逻辑引用生成拓扑顺序；
2. 保留所有原始主键，验证 Boolean、DateTime、JSON 和数值类型；
3. 在单一 PostgreSQL transaction 内逐表插入；
4. 使用 `pg_get_serial_sequence` 校准 integer/serial 主键序列；
5. 核对每张迁移表的 source/target 行数、技术管理员和排除表；
6. 任一步失败则回滚全部业务数据。

第二次 apply 会因为目标已非空而拒绝。不要通过清空表、删除数据目录或绕过检查来重试；保留报告和数据库日志，先查明失败原因。

## 本轮真实源库限制

对识别出的真实本地 SQLite 只允许执行 `--dry-run`，不得执行真实 `--apply`。本地验证只能连接本轮创建的隔离 PostgreSQL 16 临时容器，不得 SSH、连接腾讯云、读取 `production.env`、上传源数据库或操作线上容器。

## 验证清单

- 源文件 SHA 与修改时间在 dry-run 前后不变；
- PostgreSQL 目标在 dry-run 前后业务行数均为零；
- apply 后每张迁移表行数一致，主键与密码哈希原样保留；
- `auth_sessions=0`、`login_attempts=0`；
- 至少一个 `is_tech_admin=true`；
- `/api/setup/status` 返回 `initialized=true`；
- 所有序列已校准，新增测试记录不会与历史 ID 冲突；
- 模拟插入失败时所有表回滚；
- 再次 apply 被拒绝；
- 临时容器结束后只删除本轮资源，不执行任何 Docker prune。

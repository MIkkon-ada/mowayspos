# Public Release Audit

Date: 2026-07-10

Repository: `https://github.com/MIkkon-ada/mowayspos`

Branch: `main`

Current commit: `d5b89b8` (`initial import`)

## 1. Git 状态

- `git status` 结果：working tree clean
- 当前分支：`main`
- 远端：`origin -> https://github.com/MIkkon-ada/mowayspos.git`
- 远端可用性：已配置并跟踪 `origin/main`

## 2. Git 已跟踪文件检查

检查方式：`git ls-files`

结果：

- 没有跟踪到 `.env`、`.env.*`
- 没有跟踪到 `passwords.json`
- 没有跟踪到 `llm_configs.json`
- 没有跟踪到 `*.db`、`*.sqlite`、`*.sqlite3`、`*.db-wal`、`*.db-shm`
- 没有跟踪到 `*.bak`、`*.backup`、`*.dump`
- 没有跟踪到 `*.log`
- 没有跟踪到 `node_modules/`、`dist/`、`build/`
- 没有跟踪到 `.venv/`、`venv/`
- 没有跟踪到 `_audit_temp/`
- 没有跟踪到 `project-init-preview.html`
- 没有跟踪到任何已知真实账号、密码、token、API key、私钥、cookie、session 文件

## 3. Git 历史敏感文件检查

检查方式：`git log --all --name-only --pretty=format: | sort -u`

结果：

- 当前仓库只有一个提交：`initial import`
- 历史中未出现以下敏感文件名或扩展名：
  - `.env`
  - `passwords.json`
  - `llm_configs.json`
  - `.db` / `.sqlite` / `.sqlite3`
  - `.db-wal` / `.db-shm`
  - `.bak`
  - `.log`
  - `secrets.json`
  - `private`
  - `key`
  - `pem`
  - `token`
  - `session`
  - `cookie`
- 历史里唯一出现 `key` 字样的文件名是 `bowei_ai_dashboard/scripts/migrate_system_role_keys.py`，这是正常迁移脚本，不是敏感文件

结论：未发现需要清理 Git 历史的敏感提交。

## 4. 源码内容敏感信息扫描

检查方式：递归扫描源码、文档与配置，排除 `node_modules/`、`dist/`、`build/`、`.git/`、`venv/`、`.venv/`

搜索关键词包括：

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `SECRET_KEY`
- `DATABASE_URL`
- `password`
- `passwd`
- `token`
- `api_key`
- `apikey`
- `access_key`
- `private_key`
- `BEGIN RSA PRIVATE KEY`
- `BEGIN OPENSSH PRIVATE KEY`
- `sk-`
- `xoxb-`
- `ghp_`
- `github_pat_`
- `Bearer `
- `cookie`
- `session`

结果：

- 未发现真实密钥、真实密码、真实 token、真实 session、真实私钥
- 命中的内容主要是正常业务字段、变量名、登录表单字段、配置占位符和会话逻辑
- 典型正常字段包括 `password`、`api_key`、`token`、`session`、`cookie`
- 这份报告本身包含了用于扫描的关键词列表，因此正则会命中本报告里的示例字符串；这些命中不代表源码里存在真实秘密
- `docker-compose.prod.yml` 中出现了 `DATABASE_URL` 和默认数据库口令占位值 `postgres`，属于默认配置，不是从仓库中泄露出的真实私密信息

结论：未发现 P0 级密钥泄露。

## 5. 数据库和本地产物检查

结果：

- 本地存在但未跟踪、且已被 `.gitignore` 排除的文件/目录：
  - `bowei_ai_dashboard/bowei.db`
  - `bowei_ai_dashboard/bowei_ai_dashboard.db`
  - `bowei_ai_dashboard/bowei_ai_dashboard.db-shm`
  - `bowei_ai_dashboard/bowei_ai_dashboard.db-wal`
  - `bowei_ai_dashboard/bowei_ai_dashboard.db.bak_n8p1p1a`
  - `bowei_ai_dashboard/_audit_temp/`
  - `Reference document/`
  - `project-init-preview.html`
  - `frontend/dist/`
  - `frontend/node_modules/`
  - `frontend/*.tsbuildinfo`
  - `frontend/vite.config.js`
  - `frontend/vite.config.d.ts`
- 这些内容未进入 Git 跟踪，也未进入 Git 历史

结论：本地运行产物存在，但没有进入可公开仓库内容。

## 6. README / 文档隐私检查

结果：

- 未发现真实人员账号、密码、手机号、身份证、地址、客户隐私数据
- 未发现真实 API key 或私钥
- 文档中出现的本地地址、cookie 名称、会话名和调试说明属于正常开发信息
- 业务流程文档包含内部流程口径，但不包含敏感个人信息

结论：当前文档不构成公开阻断。

## 7. `.gitignore` 检查

检查结果：

- 已包含 `.env`、`.env.*`、`!.env.example`、`!.env.production.example`
- 已包含 `passwords.json`、`llm_configs.json`
- 已包含 `*.db`、`*.sqlite`、`*.sqlite3`、`*.db-wal`、`*.db-shm`
- 已包含 `*.bak`、`*.log`
- 已包含 `node_modules/`、`dist/`、`build/`
- 已包含 `.venv/`、`venv/`
- 已包含 `project-init-preview.html`
- 已包含 `_audit_temp/`、`Reference document/`、`_backup_before_*/`

本次补充：

- `*.backup`
- `*.dump`
- `*backup_before*/`
- `**/__pycache__/`

结论：`.gitignore` 已足够用于公开前的隐私隔离。

## 8. 风险等级

结论：可以公开

依据：

- 没有发现真实密钥、真实数据库、真实密码、真实 token
- Git 历史没有出现敏感文件
- 敏感本地产物均未被跟踪，且已被 `.gitignore` 排除
- 文档没有个人隐私泄露

## 9. 需要保留的注意事项

- 公开前建议再做一次人工浏览，确认 `docker-compose.prod.yml` 的默认数据库口令占位值符合你的公开标准
- 如果未来新增本地数据库、导出、临时审计目录或配置文件，需要继续走 `.gitignore` 管理

## 10. 最终判断

A. 可以改 public

说明：

- 当前仓库适合从 private 改成 public
- 不需要清理 Git 历史
- 不需要重建公开仓库

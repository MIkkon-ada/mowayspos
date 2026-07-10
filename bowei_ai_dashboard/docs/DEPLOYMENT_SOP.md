# 部署接线 SOP

本文档描述当前项目的同域部署方式。目标是让前端 `frontend/dist` 由 Nginx 托管，后端 FastAPI 仅提供 `/api/*`，并保持 `/api/health`、登录、会话和 SPA 路由稳定可用。

## 1. 部署目标

- 前端采用同域部署
- Nginx 负责托管 `frontend/dist`
- Nginx 将 `/api/*` 反向代理到本机 FastAPI
- 后端继续使用 `uvicorn app.main:app`
- Cookie 保持同域，不额外开启跨域配置

## 2. 推荐目录

- 后端：`/opt/bowei_ai_dashboard`
- 前端构建产物：`/opt/bowei_frontend/dist`
- 后端环境文件：`/etc/bowei-ai-dashboard.env`

## 3. 前端构建与发布

在前端仓库执行：

```bash
cd frontend
npm install
npm run build
```

然后将 `frontend/dist/` 发布到服务器上的 `/opt/bowei_frontend/dist/`。

发布前应确认：

- `dist/index.html` 存在
- `dist/assets/` 下的静态资源带 hash
- 构建过程成功退出

## 4. 后端部署

在后端仓库服务器目录下：

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

创建或更新 `/etc/bowei-ai-dashboard.env`，至少包含：

- `APP_ENV=production`
- `DATABASE_URL=...`
- `SESSION_COOKIE_SECURE=true`
- `SESSION_COOKIE_SAMESITE=lax`
- `SESSION_TTL_DAYS=7`
- `LOG_LEVEL=INFO`
- `BOWEI_ADMIN_USERNAME=...` 或 `BOWEI_AUTH_USERS_JSON=...`
- `BOWEI_ADMIN_PASSWORD_HASH=...`
- `LLM_API_KEY=...`
- `LLM_BASE_URL=...`
- `LLM_MODEL=...`

启动服务：

```bash
systemctl daemon-reload
systemctl enable --now bowei
```

## 5. Nginx 接线

建议以 `scripts/nginx.conf` 作为模板，完成以下行为：

- `/` 返回 `frontend/dist/index.html`
- `/assets/*` 直接服务 `frontend/dist/assets/*`
- `/login`、`/projects`、`/project/*`、`/admin/*` 使用 SPA fallback 到 `index.html`
- `/api/*` 反代到 `http://127.0.0.1:8008`
- `/api/health` 仍走后端

缓存建议：

- `assets/` 可长缓存
- `index.html` 不强缓存

## 6. 启动顺序

推荐顺序：

1. 部署后端虚拟环境
2. 配置 `/etc/bowei-ai-dashboard.env`
3. 启动后端服务
4. 部署前端 `dist`
5. 更新 Nginx 配置
6. `nginx -t`
7. `systemctl reload nginx`

## 7. 验证清单

部署完成后验证：

```bash
GET /api/health
GET /
GET /login
GET /projects
GET /project/2
GET /project/2/tasks
GET /admin/projects
```

登录流程应继续验证：

- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`

浏览器刷新深链时不应出现 404。

## 8. 回滚建议

如果需要回滚：

1. 停止后端服务
2. 回滚前端 `dist`
3. 恢复上一版 Nginx 配置
4. 使用 `docs/DB_BACKUP_RESTORE_SOP.md` 恢复数据库备份
5. 重新启动后端并验证 `/api/health`

## 9. 风险提示

- 当前方案仍基于 SQLite 试运行
- 不建议多机多实例同时写同一个 SQLite 文件
- 生产环境必须确保 HTTPS 与 `SESSION_COOKIE_SECURE=true` 配套
- 如果未来切跨域部署，需要重新评估 CORS、Cookie 和 credentials 策略

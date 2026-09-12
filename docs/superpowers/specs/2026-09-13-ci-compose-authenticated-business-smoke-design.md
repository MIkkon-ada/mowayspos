# CI Compose 认证业务冒烟设计

## 目标

在现有 PostgreSQL 16、后端和前端 nginx Compose 门禁中，增加一个确定性的认证业务冒烟。它必须验证真实数据库迁移后的首次初始化、登录会话、反向代理、代表性项目读取与命名业务列表，以及至少一条普通用户的拒绝路径。

## 约束

- CI 的生产环境禁用开发 seed，不能通过 `BOWEI_DEV_MODE` 或新测试后门获得数据。
- 不联系 AI、企业微信、文件上传或外部网络服务。
- 不降低 `SESSION_COOKIE_SECURE=true`；客户端从登录响应中读取 cookie 值，并在后续 HTTP 请求显式设置 `Cookie` 头。
- 不更改生产 API、数据库 schema、镜像端口、Compose 拓扑或运行权限。

## 方案

新增 `bowei_ai_dashboard/scripts/ci_compose_business_smoke.py`，只使用 Python 标准库。它运行在已启动的 backend 容器内，却将所有 HTTP 请求发送到 `http://frontend`，故请求必经 nginx 代理。

1. 断言 `/api/setup/status` 为未初始化；调用 `/api/setup/init` 创建 CI 专用技术管理员；再次读取状态确认初始化。
2. 以管理员登录，验证 `/api/auth/me`，并由管理员 API 创建一个不具备技术管理员角色的普通账号。
3. 管理员创建一个最小草稿项目，验证项目详情、能力、任务、工作汇报、确认中心、会议、问题和成果列表均能通过 nginx 以认证会话访问。
4. 普通账号登录，并尝试创建项目；必须收到 `403`，证明认证不等于项目管理授权。

测试数据只存在于 CI 创建的临时 PostgreSQL 数据卷，Cleanup 会移除该卷。固定用户名、密码和项目名均为无敏感 CI 测试值；脚本不得打印密码或 cookie。

## CI 集成

在现有 `Complete Compose smoke and port isolation` 中，frontend 健康后执行：

```bash
"${dc[@]}" exec -T backend python scripts/ci_compose_business_smoke.py --base-url http://frontend
```

脚本打印每个已验证的 `METHOD path status`，失败时输出不含认证材料的诊断并以非零退出。该步骤不重新构建镜像，也不创建新的 host port。

## 验收

- 本地单元测试覆盖 HTTP 客户端的状态、JSON 和 cookie 处理；源码契约测试固定 CI 调用位置和禁用开发 seed 的原则。
- 该脚本针对临时本地 HTTP server 的成功/拒绝序列通过。
- CI 配置在 nginx 健康后、端口断言前运行脚本，且不含 `continue-on-error`。
- 全量后端、前端测试和构建基线继续通过。
- Docker 不可用时，本地只报告无法执行 Compose，不把远程 PostgreSQL 冒烟标为已证明。

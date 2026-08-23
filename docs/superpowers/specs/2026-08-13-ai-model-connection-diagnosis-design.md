# AI 模型连接诊断与迁移设计

## 目标

让 AI 模型配置能够在已迁移的数据库上保存并测试 DeepSeek 的官方模型别名，同时在失败时显示安全、可行动的原因，而不是笼统归咎于模型名或密钥。

## 已确认事实

- DeepSeek OpenAI 兼容地址为 `https://api.deepseek.com`。
- `deepseek-v4-flash` 与 `deepseek-v4-pro` 是官方支持的模型别名。
- 当前受保护 SQLite 数据库缺少 `ai_models` 等 AI 配置表，连接测试在调用上游前就可能失败。
- 当前测试路由捕获所有异常并返回同一条“连接失败”，前端因此无法展示真实类别。

## 方案

1. 先使用 SQLite 备份 API 生成带时间戳的数据库备份，然后执行 `alembic upgrade heads`，只新增缺失架构，不重置或删除已有数据。
2. 测试端点仅将 `AIUpstreamError.code` 和安全的固定中文消息返回给前端；不返回上游响应、请求头、API Key 或异常堆栈。数据库配置异常与未配置凭证也返回明确的非敏感消息。
3. 前端按照服务端返回的安全消息展示结果，并把 DeepSeek 提示更新为官方 `deepseek-v4-flash、deepseek-v4-pro`。

## 验收

- `ai_models`、`ai_model_credentials`、`ai_capability_policies` 和 `ai_invocation_logs` 表存在。
- 连接测试对认证、模型/请求、限流、超时、网络和未知失败分别返回可读的安全提示。
- 页面不再把所有失败笼统提示为“检查模型名称、Base URL 和 API Key”。
- 不记录或回传密钥；现有 AI 配置和服务测试均通过。

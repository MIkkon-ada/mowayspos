# AI 能力配置升级验收与发布清单

## 发布前

1. 对数据库及历史 AI 配置文件做加密离线备份；备份不进入 Git、镜像或共享日志。
2. 在受保护的生产环境文件中设置有效的 AI_CONFIG_ENCRYPTION_KEY，并确认不会在共享的 docker compose config 输出中泄露。
3. 运行 python -m alembic upgrade head，确认 ai_models、ai_model_credentials、ai_capability_policies 和 ai_invocation_logs 均已存在。
4. 仅在一次性迁移窗口挂载历史配置文件，将其路径设为 AI_LEGACY_MIGRATION_FILE，由技术管理员执行迁移接口；核验迁移报告不含 API Key，并列出四项能力策略状态。
5. 迁移完成后，恢复 AI_CAPABILITY_CENTER_MODE=database，移除一次性迁移文件挂载和 AI_LEGACY_MIGRATION_FILE。

## 管理端验收

1. 创建并测试一个对话模型和一个 ASR 模型；浏览器接口响应只能显示 credential_configured，不得返回凭证。
2. 为 meeting.analysis、task.extraction、project.init.analysis、speech.realtime 分别绑定类型兼容且启用的模型。
3. 分别执行一次会议分析、任务提取、项目初始化分析、文件转写和实时转写。
4. 检查调用日志：能力键、策略版本、模型编号、尝试次数、状态和耗时应完整；日志不得含提示词、音频、完整响应或密钥。
5. 在可控的重试场景中禁用或使主对话模型超时，确认已配置备用模型接管；随后恢复主模型。

## 发布后核验

1. 确认不存在 /api/llm-config 路由、旧设置卡片或旧前端配置客户端。
2. 确认正常生产容器没有历史 JSON 配置挂载，且容器启动时校验数据库模式、加密密钥和四张 AI 配置表。
3. 在发布单记录：发布时间、迁移报告编号及每项能力首次成功调用的日志编号。

## 紧急回滚

只允许两种回滚方式：恢复已验证的数据库备份，或部署上一版镜像并临时设置
AI_CAPABILITY_CENTER_MODE=legacy-rollback、AI_LEGACY_ROLLBACK_ACKNOWLEDGED=true
以及 AI_LEGACY_ROLLBACK_CONFIG_PATH 指向离线历史文件。确认系统写入
ai_capability_legacy_rollback 操作日志后，立即限制该临时文件的访问范围。

不得将密钥复制到源代码、命令历史或工单正文中。

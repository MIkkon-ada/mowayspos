# 项目初始化 AI 受控自动降级设计

## 目标

项目初始化的文件分析默认调用 DashScope `qwen-plus`。当上游出现可恢复故障时，系统自动改用已配置的 DeepSeek 聊天模型，提升分析完成率；同时保留足够的、安全的调用审计信息，使用户和管理员能够明确知道实际调用路径。

## 范围

仅改动 `project.init.analysis` 能力的聊天模型调用与其展示、测试。不会修改其他 AI 能力的策略，也不会存储 API Key、附件正文或完整提示词。

## 调用策略

1. 首选模型为当前 DashScope `migrated-dashscope-chat`。
2. 备用模型为 `migrated-deepseek-chat`。
3. 每个候选模型在一次分析中至多调用一次。禁用 OpenAI SDK 的隐式重试，防止一次用户操作产生不可见的重复上游请求。
4. 仅在以下错误时自动尝试备用模型：
   - `AI_UPSTREAM_TIMEOUT`
   - `AI_UPSTREAM_CONNECTION`
   - `AI_UPSTREAM_RATE_LIMIT`
   - `AI_UPSTREAM_5XX`
5. `AI_UPSTREAM_AUTH`、`AI_UPSTREAM_BAD_REQUEST`、模型输出验证失败及本地解析错误不切换备用模型，直接完成失败记录。

## 错误归类与审计

适配器需将 OpenAI SDK 的 `APITimeoutError` 映射为 `AI_UPSTREAM_TIMEOUT`，将其连接类错误映射为 `AI_UPSTREAM_CONNECTION`。保留既有 HTTP 状态码分类。

每次调用写入独立的调用日志，记录能力、策略版本、模型、尝试顺序、是否备用、耗时和安全错误码。分析运行结果聚合实际尝试的模型顺序与最终模型，不记录异常原文或敏感请求内容。

## 界面行为

项目负责人查看分析运行时，能够看到：

- 配置的模型策略（DashScope → DeepSeek）；
- 本次尝试顺序及每一步状态；
- 成功时的实际最终模型；
- 全部失败时的安全错误说明与重新分析入口。

历史运行没有策略快照时显示“历史记录未保存策略”，不误导为系统未配置策略。

## 验证

新增或更新自动化测试覆盖：

- DashScope 超时后只调用一次，再调用 DeepSeek 并成功；
- 认证与请求参数错误不会调用 DeepSeek；
- SDK 超时异常被归类为 `AI_UPSTREAM_TIMEOUT`；
- SDK 客户端显式禁用隐式重试；
- 前端在成功、自动切换成功、全部失败和历史记录场景显示正确的模型信息。

## 非目标

本次不更改密钥，不调用真实供应商 API 做诊断，不调整超时秒数，也不改变附件解析或草稿合并规则。

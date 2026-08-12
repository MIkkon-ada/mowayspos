# AI 模型管理页面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 WeKnora 式模型卡片和右侧抽屉替换当前 AI 配置页，并移除页面中的业务能力绑定。

**Architecture:** 继续使用现有 `/api/ai-config/models`、凭证和测试接口。前端拆成模型管理容器、模型卡片、模型抽屉和服务商元数据四个小模块；业务策略接口不再由该页面调用。

**Tech Stack:** React 19、TypeScript、Tailwind、现有 FastAPI AI 配置接口、pytest 源代码契约测试、Vite。

---

### Task 1: 锁定模型管理界面契约

**Files:**
- Replace: `bowei_ai_dashboard/tests/test_ai_configuration_wizard_frontend.py`

- [ ] 写入失败测试，要求“全部/对话模型/语音模型”、模型卡片、添加模型、右侧抽屉、服务商、模型名称、显示名称、Base URL、API Key、测试连接、保存，并禁止业务能力绑定文案。
- [ ] 运行 `python -m pytest tests/test_ai_configuration_wizard_frontend.py -q`，确认因新组件不存在而失败。

### Task 2: 实现服务商元数据和模型卡片

**Files:**
- Create: `frontend/src/features/settings/aiModelProviders.ts`
- Create: `frontend/src/features/settings/AIModelCard.tsx`

- [ ] 用测试锁定 DeepSeek、DashScope、GLM、Anthropic、自定义 OpenAI 兼容接口和默认 Base URL。
- [ ] 实现服务商选择元数据、稳定的模型 code 生成和模型卡片状态展示。
- [ ] 运行聚焦测试并确认通过。

### Task 3: 实现新增/编辑模型抽屉

**Files:**
- Create: `frontend/src/features/settings/AIModelDrawer.tsx`

- [ ] 用测试锁定抽屉字段、密码输入、测试连接、取消、保存和编辑时不回显密钥。
- [ ] 实现新增时创建模型并保存凭证；编辑时更新模型，只有输入新密钥才替换凭证。
- [ ] 新增模型在测试连接时先保存配置，再使用临时密钥测试；测试结果不强制阻止保存。
- [ ] 运行聚焦测试和 `npm run build`。

### Task 4: 重写模型管理容器并移除错误向导

**Files:**
- Modify: `frontend/src/features/settings/AIConfigurationSection.tsx`
- Delete: `frontend/src/features/settings/AIFirstRunWizard.tsx`
- Delete: `frontend/src/features/settings/AIConfigurationOverview.tsx`
- Delete: `frontend/src/features/settings/aiConfigurationFlow.ts`

- [ ] 实现模型加载、三个标签筛选、卡片网格、添加卡片、编辑抽屉、错误重试。
- [ ] 确认该页面不导入能力策略 API，也不出现业务能力名称。
- [ ] 运行界面契约测试和前端生产构建。

### Task 5: 回归与提交

**Files:**
- Test: `bowei_ai_dashboard/tests/test_ai_configuration_wizard_frontend.py`
- Test: `bowei_ai_dashboard/tests/test_ai_config_api.py`
- Test: `bowei_ai_dashboard/tests/test_ai_config_repository.py`

- [ ] 运行 `python -m pytest tests/test_ai_configuration_wizard_frontend.py tests/test_ai_config_api.py tests/test_ai_config_repository.py -q`。
- [ ] 运行 `npm run build`。
- [ ] 检查 `git diff --check` 和工作区，保留用户的工作汇报计划文档不动。
- [ ] 本地提交模型管理页面改造，不推送、不合并 `main`。

### Task 6: 删除虚设的全局置信度设置

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/api/platformSettings.ts`
- Modify: `bowei_ai_dashboard/app/routers/platform_settings.py`
- Test: `bowei_ai_dashboard/tests/test_ai_configuration_wizard_frontend.py`

- [ ] 写入失败测试，要求 AI 设置页不出现“AI 建议置信度”和滑杆状态，平台设置前后端不再声明全局 `confidence`。
- [ ] 运行 `python -m pytest tests/test_ai_configuration_wizard_frontend.py -q`，确认测试先因旧配置仍存在而失败。
- [ ] 删除页面状态、加载逻辑、保存参数、界面卡片、前端类型和后端默认值。
- [ ] 保留项目匹配、任务提取等结果对象自身的 `confidence` 字段。
- [ ] 重新运行前端契约测试和生产构建。

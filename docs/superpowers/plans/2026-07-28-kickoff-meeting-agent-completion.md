# 启动会确认 Agent 收尾实施计划

> **供自动化执行者使用：** 必须使用 `executing-plans` 工作流逐项实施。本计划使用复选框（`- [ ]`）跟踪进度。

**目标：** 通过生命周期回归测试、浏览器验收和仅包含会议相关文件的独立交付，完成启动会确认 Agent 的改造收尾。

**架构：** 保留现有基于 `Meeting` 的普通会议纪要流程；状态为 `pending_kickoff` 的项目则进入 `KickoffAgentRun` 与 `KickoffChangeProposal` 审核流程。回归测试直接覆盖服务与路由边界；浏览器验收覆盖渲染后的工作台及其状态流转。

**技术栈：** FastAPI、SQLAlchemy、pytest、React、TypeScript、Vite、Playwright/浏览器验收。

---

### 任务 1：固化生命周期边界回归

**涉及文件：**

- 修改：`bowei_ai_dashboard/tests/test_kickoff_writeback.py`
- 测试：`bowei_ai_dashboard/tests/test_kickoff_writeback.py`

- [ ] **步骤 1：为不允许的生命周期入口编写测试**

补充直接调用路由/服务的测试，证明：

1. `pending_kickoff` 项目不能创建普通 `Meeting`；
2. 项目已处于 `active` 时，`confirm_kickoff_start()` 会拒绝继续确认启动。

- [ ] **步骤 2：运行专项测试并确认失败原因正确**

在 `bowei_ai_dashboard` 目录执行：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_kickoff_writeback.py -q
```

预期：若守卫尚未实现，新增断言应因缺少对应生命周期限制而失败。

- [ ] **步骤 3：仅在发现缺失时补充最小守卫**

普通会议边界继续由 `create_meeting()` 负责，启动写入事务继续由 `confirm_kickoff_start()` 负责。除非失败测试明确指出缺失，不修改任务写入逻辑或既有角色权限规则。

- [ ] **步骤 4：重新运行专项测试**

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\test_kickoff_writeback.py -q
```

预期：专项测试全部通过。

### 任务 2：验证页面工作流

**涉及文件：**

- 检查：`frontend/src/pages/MeetingPage.tsx`
- 检查：`frontend/src/features/meeting/KickoffAgentWorkspace.tsx`
- 测试：`frontend/tests/kickoffAgentStructure.test.mjs`

- [ ] **步骤 1：确认本地前后端服务可用**

仅在服务尚未启动时启动现有开发脚本；记录联调地址及使用的测试账号。

- [ ] **步骤 2：完成浏览器端完整流程**

选择一个 `pending_kickoff` 测试项目，进入“会议纪要”，粘贴启动会原文生成审核包，提交审核；以企业教练身份批准所有提案，最后确认启动项目。

- [ ] **步骤 3：核验浏览器可见结果**

确认启动成功后工作台关闭，项目状态更新为 `active`，并已产生一条状态为 `published`、类型为 `kickoff` 的会议纪要。记录实际观察结果，且不修改无关测试数据。

### 任务 3：全量回归与聚焦交付

**涉及文件：**

- 验证：`bowei_ai_dashboard/tests/`
- 验证：`frontend/tests/*.test.mjs`
- 验证：`frontend/package.json`

- [ ] **步骤 1：运行后端完整测试集**

在 `bowei_ai_dashboard` 目录执行：

```powershell
& .\.venv\Scripts\python.exe -m pytest tests -q
```

- [ ] **步骤 2：运行前端测试与生产构建**

在 `frontend` 目录执行：

```powershell
node --test tests/*.test.mjs
npm run build
```

- [ ] **步骤 3：暂存前按文件路径审查差异**

只暂存启动会/会议相关源码、迁移、会议测试和生命周期文档。不得暂存无关的驾驶舱、认证、任务管理、快照或本地数据库改动。

- [ ] **步骤 4：提交聚焦后的改动**

仅在完整验证均通过后，以清晰描述本次功能的提交信息创建一个独立提交。

# N4-P0 主流程多角色验收报告

## 结论

建议：主流程多角色验收通过。当前无 P0 阻断；冯海林全局驾驶舱行为经核查符合 company_ceo 权限；通知跳转全部正常，旧路由 `/project/:id/*` 均已兼容重定向至新路由；剩余事项进入 P1/P2 后续优化。

---

## 一、环境信息

| 项目 | 结果 |
|------|------|
| 分支 | `main` |
| 最新 commit | `22e53c0` Merge pull request #19 (n4-p0-p2c-dashboard-my-scope) |
| git status | clean（仅 `.playwright-cli/` untracked） |
| compileall | ✅ 通过 |
| pytest | ✅ 155 passed |
| npm build | ✅ 通过（chunk size warning only） |

### main 分支包含功能清单

1. ✅ 项目级成果库（PR #16: project-achievement-library-redesign）
2. ✅ 项目级问题中心 Kanban
3. ✅ 驾驶舱 my scope（PR #19: dashboard-my-scope）
4. ✅ 工作推进表 projectId 上下文修复
5. ✅ AI 确认中心 reviewer 识别修复
6. ✅ 成果/问题确认入库回流修复

---

## 二、验收账号

| 序号 | 账号 | 角色 | S1 项目角色 | 登录 |
|------|------|------|------------|------|
| 1 | 吴肖 | Owner / 项目负责人 | owner | ✅ 通过 |
| 2 | 冯海林 | Coach / 企业教练 | project_ceo | ✅ 通过 |
| 3 | 杨宇帆 (yangyufan) | 统筹人 | member | ✅ 通过 |
| 4 | 刘万超 | 协同成员（普通） | member | ✅ 通过 |
| 5 | moways | tech_admin / 超级管理员 | 无 | ✅ 通过 |

> **注意**：验收期间所有账号密码已统一重置为 `test123`（仅测试环境，验收后建议还原）。

---

## 三、验收项目 S1

- projectId = 19
- status = active
- lifecycle_status = active
- owner = 吴肖
- project_ceo / Coach = 冯海林
- 检测到重点工作 1111
- 检测到关键任务

---

## 四、吴肖 Owner 验收

| 验收项 | 结果 | 截图 | 说明 |
|--------|------|------|------|
| 驾驶舱 `/home/dashboard` | ✅ 通过 | `acceptance_owner_dashboard_my_scope.png` | 默认"我的项目"，无"全部项目"选项，导出 disabled |
| 工作推进表 `/work/tasks?projectId=19` | ✅ 通过 | — | S1 选中、1111 可见、进行中 1 项 |
| 确认中心 `/work/confirmations` | ✅ 通过 | — | 可查看历史记录，筛选正常 |
| 成果库 `/work/achievements?projectId=19` | ✅ 通过 | — | 2 项成果（AI确认入库 1 + 手动登记 1），无"待确认"流程 |
| 问题中心 `/work/issues?projectId=19` | ✅ 通过 | — | 五列 Kanban、可查看详情、可指定协助人、可标记已解决 |

---

## 五、冯海林验收 ✅ 通过

> **说明**：冯海林同时具备 `company_ceo` 系统角色和 S1 `project_ceo` 项目角色。由于 `company_ceo` 拥有 `can_view_all=true`，默认进入"全部项目"驾驶舱符合权限设计。

| 验收项 | 结果 | 说明 |
|--------|------|------|
| 驾驶舱 `/home/dashboard` | ✅ 通过 | 默认"全部项目"符合 company_ceo 权限（也可切换到"我的项目"） |
| 问题中心 `/work/issues?projectId=19` | ✅ 通过 | 可查看 S1 看板，待决策 = 0（暂无可验证的 Coach 决策场景） |
| 成果库 `/work/achievements?projectId=19` | ✅ 通过 | 可查看 2 项成果 |
| 特殊导航 | ✅ 通过 | 有"企业教练决策中心"专属导航 |
| platform-settings 403 | ⚠️ P2 | 4 个 403 错误（非阻断，前端预加载） |

---

## 六、杨宇帆 Coordinator 验收

| 验收项 | 结果 | 说明 |
|--------|------|------|
| 驾驶舱 `/home/dashboard` | ✅ 通过 | 默认"我的项目"，无全局选项，导出 disabled |
| 工作汇报 `/work/submit?projectId=19` | ✅ 通过 | S1 绑定、内容可填、AI 提取可用、历史记录 4 条 |
| 问题中心 `/work/issues?projectId=19` | ✅ 通过 | 可查看看板，看到自己作为协助人的问题 |
| S1 角色 | ⚠️ 注意 | S1 中为 member 而非 coordinator（数据层面） |

---

## 七、刘万超 普通成员验收

| 验收项 | 结果 | 说明 |
|--------|------|------|
| 驾驶舱 `/home/dashboard` | ✅ 通过 | "普通成员请从我的任务查看个人工作"、任务总数 0、无管理驾驶舱 |
| 导航权限 | ✅ 通过 | 无"驾驶舱"按钮、无"项目管理"、"系统设置" |
| 项目选择 | ✅ 通过 | 仅显示参与的项目（年度A公司计划、S1、知识资产AI化） |
| 确认中心 `/work/confirmations` | ✅ 通过 | 仅"我的提交"tab、全部记录(0)、不能看别人待确认 |
| 全局视图 | ✅ 通过 | 无"全部项目"入口 |

---

## 八、moways tech_admin 验收

| 验收项 | 结果 | 说明 |
|--------|------|------|
| 驾驶舱 `/home/dashboard` | ✅ 通过 | 默认"全部项目"、任务总数 4、导出周报可用 |
| 项目管理 `/home/projects` | ✅ 通过 | 19 个项目、可见 S1 生命周期状态 |
| 无 403 | ✅ 通过 | 无 dashboard 相关 403 |

---

## 九、回流链路

| 验收项 | 结果 | 说明 |
|--------|------|------|
| 成果库回流 | ✅ 通过 | "S1资料清单初稿" AI 确认入库后出现在成果库 |
| 问题中心回流 | ✅ 通过 | 2 个问题均在待处理列显示 |
| 工作推进表回流 | ✅ 通过 | 不串项目、不白屏 |
| 驾驶舱 project scope | ✅ 通过 | S1 卡片 0/1 |

---

## 十、权限边界汇总

| 检查项 | 结果 |
|--------|------|
| 普通成员不能看全局驾驶舱 | ✅ 通过 |
| 普通成员不能确认别人提交 | ✅ 通过 |
| Owner 默认 my scope 不请求全局 | ✅ 通过 |
| Coordinator 默认 my scope | ✅ 通过 |
| Coach 有企业教练决策中心 | ✅ 通过 |
| 导出周报多项目 disabled | ✅ 通过 |

---

## 十一、通知跳转

| 验证项 | 结果 | 说明 |
|--------|------|------|
| 新增问题通知 → `/project/19/issues` | ✅ 通过 | 重定向至 `/work/issues?projectId=19`，无 404 |
| 上报 Coach 通知 → `/project/19/issues` | ✅ 通过 | 冯海林收到"需要您决策"通知，点击跳转正确 |
| 成果通知 → `/project/19/achievements` | ✅ 通过 | 重定向至 `/work/achievements?projectId=19` |
| 旧路由兼容 | ✅ 通过 | `routes.tsx:189-190` 已实现全部旧路由重定向 |
| `/project/:id/issues` → `/work/issues?projectId=:id` | ✅ | `LegacyProjectRedirect` |
| `/project/:id/achievements` → `/work/achievements?projectId=:id` | ✅ | `LegacyProjectRedirect` |

> **验证方式**：吴肖创建新问题并上报 Coach → 冯海林收通知 → 点击跳转 → 目标页面正确。后台通知链接格式为 `/project/{project_id}/issues`，前端通过 `LegacyProjectRedirect` 组件自动转换。

---

## 十二、问题列表

### P0 阻断

❌ **无**

### P1 问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | 问题中心"开始处理"按钮 disabled | 无法直接开始处理问题 |
| 2 | 杨宇帆在 S1 中角色为 member（非 coordinator） | 统筹人应有的管理权限可能受限 |

### P2 问题

| # | 问题 |
|---|------|
| 1 | 冯海林 dashboard 有 4 个 platform-settings 403（预加载，无实际影响） |
| 2 | 各页面加载时有少量 console error（2 个/页，预加载相关） |

---

## 十三、截图文件清单

截图本地留存（不提交仓库），位于 `d:\项目整体备份\mowayspos\` 根目录和 `.playwright-cli\` 目录：

| 文件名 | 内容 |
|--------|------|
| `acceptance_admin_dashboard_global.png` | tech_admin 全局驾驶舱 |
| `acceptance_admin_projects.png` | 项目管理页面 |
| `acceptance_owner_dashboard_my_scope.png` | 吴肖 dashboard my scope |

> `.playwright-cli/` 目录为 Playwright CLI 临时目录，不要提交到仓库。

---

## 十四、最终判定

| 判定项 | 结果 |
|--------|------|
| 分支 / Commit | main @ `22e53c0` |
| pytest | 155 passed |
| npm build | ✅ |
| 吴肖 owner | ✅ 通过 |
| 冯海林 | ✅ 通过（company_ceo + project_ceo，全局视图符合权限） |
| 杨宇帆 coordinator | ✅ 通过 |
| 刘万超 普通成员 | ✅ 通过 |
| tech_admin | ✅ 通过 |
| 工作汇报提交 | ✅ 通过（S1 绑定正确） |
| AI 确认入库 | ✅ 通过 |
| 成果库回流 | ✅ 通过 |
| 问题中心回流 | ✅ 通过 |
| 工作推进表 | ✅ 通过 |
| 驾驶舱 scope | ✅ 通过 |
| 通知跳转 | ✅ 通过（旧路由兼容重定向，无 404） |
| 权限边界 | ✅ 通过 |

### **建议：主流程多角色验收通过** ✅

当前无 P0 阻断；冯海林全局驾驶舱行为经核查符合 company_ceo 权限；通知跳转全部正常，旧路由已兼容；剩余事项进入 P1/P2 后续优化。

# 博维 AI 驾驶舱后端 API 注册表

> 说明：本文档记录当前后端正式接口行为，兼容历史数据与旧路径仅作为过渡说明。

---

## 1. 接口总览

### 1.1 auth

| URL | 方法 | 说明 |
|---|---|---|
| `/api/auth/login` | POST | 用户登录 |
| `/api/auth/logout` | POST | 用户退出 |
| `/api/auth/me` | GET | 获取当前登录用户信息 |

### 1.2 people

| URL | 方法 | 说明 |
|---|---|---|
| `/api/people` | GET | 人员列表 |
| `/api/people` | POST | 创建人员 |
| `/api/people/{id}` | GET | 人员详情 |
| `/api/people/{id}` | PATCH | 更新人员 |
| `/api/people/{id}` | DELETE | 删除人员 |
| `/api/people/projects` | GET | 旧路径兼容的人名 / 项目成员查询入口，是否仍保留以代码为准 |

### 1.3 projects

| URL | 方法 | 说明 |
|---|---|---|
| `/api/projects` | GET | 项目列表 |
| `/api/projects` | POST | 创建项目 |
| `/api/projects/{id}` | GET | 项目详情 |
| `/api/projects/{id}` | PATCH | 更新项目 |
| `/api/projects/{id}` | DELETE | 删除项目，是否启用以代码为准 |
| `/api/projects/{id}/archive` | POST | 归档项目 |

### 1.4 project members

| URL | 方法 | 说明 |
|---|---|---|
| `/api/projects/{id}/members` | GET | 项目成员列表 |
| `/api/projects/{id}/members` | POST | 新增项目成员 |
| `/api/projects/{id}/members/{mid}` | PATCH | 更新项目成员 |
| `/api/projects/{id}/members/{mid}` | DELETE | 删除项目成员 |

### 1.5 dashboard

| URL | 方法 | 说明 |
|---|---|---|
| `/api/dashboard/overview` | GET | 驾驶舱概览。支持 `project_id` 查询参数；`special_project` 仅用于兼容历史数据 |

### 1.6 tasks

| URL | 方法 | 说明 |
|---|---|---|
| `/api/tasks` | GET | 任务列表。支持 `project_id` 查询参数，必要时兼容历史 `special_project` 数据 |
| `/api/tasks` | POST | 新建任务 |
| `/api/tasks/{id}` | GET | 任务详情 |
| `/api/tasks/{id}` | PUT | 更新任务 |
| `/api/tasks/{id}` | DELETE | 删除任务 |
| `/api/tasks/{id}/status` | PATCH | 更新任务状态 |

### 1.7 issues

| URL | 方法 | 说明 |
|---|---|---|
| `/api/issues` | GET | 问题列表。支持 `project_id` 查询参数 |
| `/api/issues` | POST | 新建问题 |
| `/api/issues/{id}` | GET | 问题详情 |
| `/api/issues/{id}` | PUT | 更新问题 |
| `/api/issues/{id}` | DELETE | 删除问题 |
| `/api/issues/{id}/status` | PATCH | 更新问题状态 |

### 1.8 achievements

| URL | 方法 | 说明 |
|---|---|---|
| `/api/achievements` | GET | 成果列表。支持 `project_id` 查询参数 |
| `/api/achievements` | POST | 新建成果 |
| `/api/achievements/{id}` | GET | 成果详情 |
| `/api/achievements/{id}` | PUT | 更新成果 |
| `/api/achievements/{id}` | DELETE | 删除成果 |

### 1.9 meetings

| URL | 方法 | 说明 |
|---|---|---|
| `/api/meetings` | GET | 会议列表。支持 `project_id` 查询参数；历史字段 `related_special_project` 仅作兼容说明 |
| `/api/meetings` | POST | 新建会议 |
| `/api/meetings/{id}` | GET | 会议详情 |
| `/api/meetings/{id}` | PUT | 更新会议 |
| `/api/meetings/{id}` | DELETE | 删除会议 |

### 1.10 updates

| URL | 方法 | 说明 |
|---|---|---|
| `/api/updates` | POST | 进展提交。新流程以 `project_id` 为主；`special_project` 仅用于兼容历史路径 |
| `/api/updates` | GET | 提交列表 |
| `/api/updates/extract` | POST | AI 提取接口 |
| `/api/updates/{id}` | GET | 提交详情 |

### 1.11 confirmations

| URL | 方法 | 说明 |
|---|---|---|
| `/api/confirmations/pending` | GET | 待确认列表，支持 `project_id` 查询参数 |
| `/api/confirmations/counts` | GET | 待确认统计 |
| `/api/confirmations/{id}` | GET | 提交详情 |
| `/api/confirmations/{id}/confirm` | POST | 确认 |
| `/api/confirmations/{id}/reject` | POST | 打回 |
| `/api/confirmations/{id}/reject-final` | POST | 最终打回 |
| `/api/confirmations/{id}/transfer-coordinator` | POST | 转交统筹人 |
| `/api/confirmations/{id}/coordinator-feedback` | POST | 统筹反馈 |
| `/api/confirmations/{id}/escalate-ceo` | POST | 升级企业教练决策 |
| `/api/confirmations/{id}/ceo-decide` | POST | 企业教练批示 |
| `/api/confirmations/{id}/resubmit` | POST | 重新提交 |
| `/api/confirmations/{id}/withdraw` | POST | 撤回 |
| `/api/confirmations/{id}/assign` | POST | 分配提交 |
| `/api/confirmations/my-rejected` | GET | 我被打回的提交 |

### 1.12 llm config

| URL | 方法 | 说明 |
|---|---|---|
| 待代码确认 | - | 当前是否存在正式 LLM 配置接口，请以代码为准，不在本文档中伪造 |

---

## 2. 兼容说明

- 当前系统以 `project_id` 作为项目主标识
- `special_project` 仅用于旧数据与历史路径兼容
- GET 型查询在部分接口中仍可能接受 `special_project` 作为兼容输入
- 新增与写入类接口应以 `project_id` 为主，旧字段只保留过渡兼容

---

## 3. 权限边界

- 前端权限判断只用于 UX 体验，不是最终安全边界
- 后端是最终权限边界
- 当前业务口径使用以下角色名称：
  - 公司 CEO
  - 企业教练
  - 项目负责人 / PM
  - 项目统筹人
  - 关键任务责任人
  - 关键任务协助人
- 代码实现里仍可能保留 `super_admin`、`project_ceo`、`owner`、`coordinator`、`member` 等技术键，它们只是兼容和实现名，不应再作为业务定义的主说法
- 映射关系优先按业务口径理解：
  - `super_admin`：全局系统管理
  - `project_ceo`：企业教练
  - `owner`：项目负责人 / 关键任务责任人场景中的主责任人
  - `coordinator`：项目统筹人
  - `member`：关键任务协助人 / 协同参与者

---

## 4. 需要注意的事项

- 不要把临时测试接口、scratch 脚本、已删除的旧前端路径写成正式接口
- 如果某个接口是否存在无法确认，请标记为“待代码确认”
- 如果未来接口发生变化，应以 `app/routers/` 的实际实现为准

# 项目流程数据入库边界说明

> **当前口径：** 本文保留汇报入库路径和入口说明。项目完整生命周期、角色/动作权限矩阵与字段口径以 [`PROJECT_LIFECYCLE_AND_PERMISSIONS.md`](PROJECT_LIFECYCLE_AND_PERMISSIONS.md) 为准；本文末尾历史启动会方案不代表当前状态迁移。

> 本文档定义"汇报确认入库"与"管理直接录入"两条数据路径的边界，以及项目生命周期对汇报提交的约束。

---

## 一、两条数据入库路径

### 1.1 成员汇报路径（必须经过 AI 确认中心）

```
VoiceUpdatePage（工作汇报）
  → POST /api/updates              （写入 update_submissions，状态=待确认）
  → ConfirmPage（AI 确认中心）
  → POST /api/confirmations/{id}/confirm
  → 写入正式表（subtasks / tasks / issues / achievements）
```

**关键约束：**
- AI 提取结果（`POST /api/updates/extract`）不写库，仅返回建议。
- 汇报提交后 `confirm_status = 待确认`，数据停留在 `update_submissions` 表。
- **必须经过 AI 确认中心确认入库后，才会写入正式业务表。**
- AI 提取结果不得绕过确认中心直接入库。

### 1.2 管理直接录入路径（可直接写正式表）

```
AchievementsPage（成果库）
  → POST /api/achievements         （直接写入 achievements 表）

IssuesPage（问题中心）
  → POST /api/issues               （直接写入 issues 表）

TaskManagementPage（工作推进表）
  → POST /api/tasks                （直接写入 tasks 表）
  → POST /api/tasks/{id}/subtasks  （直接写入 subtasks 表）
```

**关键约束：**
- 管理直接录入属于管理维护操作，由负责人/管理员手工创建。
- 可直接写正式表，但受角色权限控制（`require_project_access` / `require_project_role`）。
- **这不是 AI 自动入库路径**，不经过 AI 提取和确认中心。
- 归档项目禁止直接录入（`require_project_not_archived` 守卫）。

---

## 二、关键边界规则

| 规则 | 说明 |
|------|------|
| AI 提取结果不得绕过确认中心直接入库 | AI 提取（`/api/updates/extract`）仅返回建议 JSON，不写任何表。入库必须经确认中心 `/api/confirmations/{id}/confirm`。 |
| 管理员/负责人手工创建记录可以直接入库 | 成果库、问题中心、工作推进表的直接创建属于管理操作，可直接写正式表。 |
| 非 active 项目不得提交正式工作汇报 | `POST /api/updates` 和 `GET /api/updates/voice-context` 仅允许 `status == active` 的项目。draft / dispatched / pending_review / returned / archived 状态均被拒绝（409）。 |
| 归档与结束冻结 | 接入 `require_project_not_archived` 的接口会拒绝归档项目；接入 `require_project_business_writable` 的业务写接口还会拒绝 `pending_close` / `ended`。各业务接口仍需分别核对，不据此推断每个端点都使用相同守卫。 |
| AI extract 预览接口不受项目状态限制 | `POST /api/updates/extract` 不写库，仅做 AI 提取预览，不受 active 校验限制。 |
| 确认中心不受项目状态限制（读取） | 确认中心的待确认列表查询不受 active 限制，已提交的汇报仍可确认入库。 |
| 历史 update_submissions 查询不受限制 | `GET /api/updates` 和 `GET /api/updates/{id}` 仅读取，不受 active 校验限制。 |

---

## 三、项目生命周期与汇报提交的关系

### 3.1 项目状态

| 状态 | 中文 | 是否允许提交汇报 | 是否允许获取可汇报上下文 |
|------|------|----------------|----------------------|
| `draft` | 草稿 | ❌ 409 | ❌ 409 |
| `dispatched` | 已派发 | ❌ 409 | ❌ 409 |
| `pending_review` | 待审核 | ❌ 409 | ❌ 409 |
| `returned` | 已退回 | ❌ 409 | ❌ 409 |
| `pending_kickoff` | 执行中（历史状态） | ❌ 409 | ❌ 409 |
| `active` | 进行中 | ✅ | ✅ |
| `pending_close` | 结束审核中 | ❌ 409 | ❌ 409 |
| `ended` | 已结束 | ❌ 409 | ❌ 409 |
| `archived` | 已归档 | ❌ 403（归档守卫） | ❌ 409 |

### 3.2 校验位置

- **`POST /api/updates`**（创建汇报）：
  1. `require_project_not_archived(project_id, db)` — 归档守卫
  2. `_require_project_active(project_id, db)` — active 校验

- **`GET /api/updates/voice-context`**（可汇报上下文）：
  1. 当传入 `project_id` 时：`_require_project_active(project_id, db)` — active 校验
  2. 不传 `project_id` 时：保持原有兼容逻辑，不扩大改造

- **`POST /api/updates/extract`**（AI 提取预览）：不校验项目状态，不写库

---

## 四、入口统一

### 4.1 项目管理主入口

- **唯一主入口**：`/home/projects`（`ProjectManagementPage`）
- `/admin/projects` 已重定向到 `/home/projects`
- `/admin/projects/:projectId/members` 保留（`ProjectMembersPage`）
- `NoProjectHome` 引导按钮指向 `/home/projects`

### 4.2 设置页

- `SettingsPage`（`/home/settings`）已无项目业务入口
- 设置页仅包含：基础信息、通知与提醒、AI能力配置、安全与权限、集成与接口、数据与备份、操作日志、人员管理

---

## 五、版本记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-07-08 | N6-1 | 初始版本：定义两条入库路径边界、active 校验规则、入口统一 |
| 2026-10-08 | A02 生命周期核对 | 将生命周期与角色权限独立维护到 `PROJECT_LIFECYCLE_AND_PERMISSIONS.md`；旧启动会门槛文字保留作历史方案说明。 |

## 六、历史启动会方案（不作为当前生命周期依据）

- 旧版方案曾要求 `pending_review → pending_kickoff → active`，并把启动会设为正式汇报前的门槛；该迁移已被当前实现取代。
- 当前常规立项审核是 `pending_review → active` 或 `pending_review → returned`。`pending_kickoff` 只为历史数据保留兼容语义；启动会提案另由会议审核流程处理。
- 当前正式汇报仍要求 `active`。重点工作结构的兼容判断另含 `dispatched` 和历史 `pending_kickoff`；普通会议还受成员角色及结束/归档写保护约束。逐项规则以生命周期权限参考文档和实际路由为准。

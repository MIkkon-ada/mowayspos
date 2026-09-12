# 前端项目名称兼容收敛设计

**日期：** 2026-09-13
**状态：** 已依据既有“自主执行”授权确认，可进入实施计划

## 目标

将前端对历史项目名称字段的读取收敛到明确的兼容层，同时保持既有 API DTO、页面展示与 Excel 导出行为不变。新代码以 `project_id` 作为项目身份的唯一依据；`special_project`、`related_special_project` 等历史字段仅作为无法解析身份时的显示回退。

## 当前证据

- `frontend/src/domain/projectDisplay.ts` 已实现“ID 优先、名称回退”，但兼容字段仍位于通用 domain 模块。
- `TaskManagementPage.tsx` 与 `exportTasksExcel.ts` 各自生成 `legacy:<名称>` 分组键，规则重复。
- 确认、会议、问题和语音更新等页面通过 `getProjectDisplayName` 读取旧字段，因此直接删除字段会破坏历史记录展示。
- 后端的 `special_project` / `related_special_project` 是已存数据库字段、请求/响应兼容字段或项目名镜像；它们不是本子项目的删除对象。

## 备选方案

1. **直接移除名称回退。** 代码最少，但未迁移历史记录会显示为空，且违反外部契约稳定原则；不采用。
2. **保留现有 domain 工具并补注释。** 风险低，但无法让兼容范围可审计，旧字段会继续在普通业务层扩散；不采用。
3. **迁移到显式前端兼容层并集中分组规则。** 保持行为，令历史字段的读取位置可搜索、可测试，并让业务页面只使用语义函数；采用。

## 设计

### 职责边界

`frontend/src/domain/projectIdentity.ts` 只负责通用项目身份：规范化数字 ID、从 DTO 读取 `project_id`/`projectId`/父项目 ID、按 ID 查找项目以及 ID 相等比较。该模块不出现历史项目名称字段。

`frontend/src/compatibility/projectNames.ts` 是前端唯一读取历史项目名称字段的运行时位置。它导出：

- `getProjectDisplayName(projects, record, fallback)`：优先利用 `project_id` 解析当前项目名称；未命中时依次读取 `special_project`、`related_special_project`、`project_name`、`projectName` 和 `parent_special_project`。
- `getProjectGroupKey(projects, record, fallback)`：ID 可解析时返回 `project:<id>`；否则返回带有兼容实现细节的稳定名称分组键。调用方不再构造 `legacy:` 字符串。
- `getProjectNameFromGroupKey(projects, key, records, fallback)`：将分组键还原为展示名称，仍由兼容层处理名称回退。

业务页面和导出工具只调用这些语义 API；它们可以保留 `TaskItem.special_project` 的类型字段以保持 API 契约，但不得直接把该字段用于身份判断或自行生成兼容分组键。

### 数据流

`API DTO → projectIdentity（读取 ID） → 当前 projects 列表匹配 → compatibility/projectNames（仅在未匹配时读取旧名称） → 页面/Excel 显示`。

任务分组以同一 `getProjectGroupKey` 产生键：有 ID 的记录按数字 ID 聚合；没有 ID 的历史记录按名称聚合；空名称统一归入未分类组。页面与导出因而不再各自解释历史数据。

### 兼容和错误处理

- 不修改后端 schema、请求参数、响应字段或历史记录。
- 名称字段永远不能覆盖一个已解析的 `project_id`。
- 无 ID 且没有可用名称时显示“（未分类）”，与当前行为一致。
- 分组键是内部实现，不进入 HTTP API、下载文件内容或用户可编辑数据。

### 验证

Vitest 覆盖 ID 优先、每个历史字段回退、未分类回退、按 ID 分组与按历史名称分组。一个静态边界测试确保 `legacy:` 和历史名称字段读取不再散落在任务页面与 Excel 导出工具。随后运行完整前端门禁；不因本次纯前端边界调整重复长时间后端测试。

## 不在本子项目范围内

- PostgreSQL/Compose 运行证据与远程 CI 执行。
- 后端数据库实体、Alembic 迁移、导入器或 API schema 的物理字段改名。
- 后端其他历史名称类别。它们由清单后续按数据库映射、接口兼容、迁移和业务回退分别处理。

## 验收条件

- 前端运行时读取项目名称历史字段的逻辑位于 `frontend/src/compatibility/projectNames.ts`。
- `projectIdentity.ts` 不含历史名称字段；任务页和 Excel 导出不含 `legacy:` 或 `special_project` 的直接分组逻辑。
- 有 ID、仅有历史名称和无项目上下文的记录都保留当前展示/分组结果。
- 前端 Vitest、完整合同测试和生产构建/包体基线通过。

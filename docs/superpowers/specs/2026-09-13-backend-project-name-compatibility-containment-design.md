# 后端项目名称兼容收敛设计

**日期：** 2026-09-13

## 目标

将后端对 `special_project`、`related_special_project` 等历史项目名称的运行时解析，收敛到 `app.compatibility`；保持既有 HTTP 参数、DTO 字段、数据库镜像字段及解析结果完全兼容。

## 当前证据

- `app/services/project_resolution.py` 已是唯一的共享解析实现，被任务、问题、成果、会议及其他资源调用。
- 解析器的安全顺序已正确：传入 `project_id` 时只按 ID 取项目并立即返回；只有缺少 ID 时才检查历史名称、JSON 提示和可选父任务。
- 四个目标 Router 的行级读取/显示逻辑均委托此解析器，但名称兼容实现仍位于普通 services 目录，不符合全局治理边界。
- `special_project`、`related_special_project` 仍是数据库列和已发布 API 字段，不能在本次重命名或删除。

## 方案

将解析器实现移动到 `app/compatibility/project_names.py`。该模块保留 `resolve_project_context` 与 `resolve_project_id` 的签名、返回字典和警告文案。它是唯一读取历史名称键、递归 JSON 名称提示及父任务历史名称的运行时模块。

先用行为测试固定以下不变量：有效 `project_id` 优先于冲突名称；仅名称能解析；无效 ID 不静默回退到名称；多个名称冲突要求人工复核；父任务回退仅在显式允许时发生。再用源码边界测试固定：四个目标 Router 以及 `permissions.py`、`crud.py` 不得定义历史名称键集合或本地名称查找；它们只能导入兼容模块的解析函数。

为避免一次性更改大量调用方，第一提交可让旧服务模块临时无逻辑地重导出兼容函数。随后将所有当前导入 `services.project_resolution` 的生产调用方迁至兼容模块，并在搜索为零后删除临时文件。此过程不改变函数签名，不改变 query 参数，也不改变物理字段写入。

## 边界

本子项目不包含：字段/表迁移、历史数据回填、API 版本升级、项目名称改名策略、Docker/PostgreSQL 运行验证。它只移动兼容解释的所有权并以测试保证解析行为不变。

## 验收

- 名称键和名称查找只存在于 `app.compatibility.project_names`、模型/schema、迁移/导入或明确的测试中。
- 四类资源的读取、列表过滤和写入镜像继续使用 ID 优先的原有结果。
- 聚焦兼容测试、四类资源回归及完整后端 pytest 通过；在 Docker 可用或远程 CI 后，继续补 PostgreSQL/Compose 证据。

# 工作推进表多维工作台第一阶段实施计划

> 执行方式：当前主智能体按 executing-plans 直接实施，遵守用户禁止委派的要求；复用现有隔离工作区与功能分支。

**Goal:** 将桌面工作推进表升级为可编辑、可批量粘贴、可分组和保存个人视图的表格工作台。

**Architecture:** 保留项目—重点工作—关键任务模型、服务端权限、汇报确认和归档规则。VTable 负责单元格交互，独立模型负责列、视图、草稿校验；批量修改通过新增原子接口提交，使用更新时间防止覆盖他人修改。个人视图按账号和项目保存到当前浏览器，手机继续使用原任务卡片。

**Tech Stack:** React 19 / TypeScript / VTable 1.26.8 / FastAPI / SQLAlchemy。

## 1. 编辑边界与接口

Files: `bowei_ai_dashboard/app/routers/subtasks.py`, `app/schemas.py`, `tests/test_work_progress_grid_edits.py`。

- [x] 先写并运行定向用例：授权 PM 可批量改标题和日期；第二行冲突时第一行也不写入；成员、归档项目和跨项目记录拒绝修改；拒绝修改状态及确认进展。
- [x] 新增 `PATCH /api/projects/{project_id}/work-progress/edits`，请求示例：
  ```json
  {"edits":[{"id":20,"expected_updated_at":"2026-10-19T09:00:00","changes":{"title":"完成需求核对"}}]}
  ```
- [x] 只更新显式字段；最多 200 行；重复行拒绝；所有记录先核对权限、成员归属、日期和版本，再在同一事务更新并记录审计。日期修改同时保持结构化日期和展示日期一致。已完成任务先走现有重新打开流程。
- [x] 执行 `.venv/Scripts/python.exe -m pytest tests/test_work_progress_grid_edits.py -q`，预期全部通过。

## 2. 视图和编辑模型

Files: `frontend-v2/src/components/task-management/workProgressGridModel.ts`, `workProgressGridModel.test.ts`, `frontend-v2/src/api/subtasks.ts`。

- [x] 先验证：只读字段粘贴被拒绝、负责人必须属于项目、日期格式有效、同一行多个改动合并、视图数据只接受已知字段。
- [x] 定义列为关键任务、负责人、开始日期、截止日期、状态、最新进展、下一步、预期成果、目标、博维角色、验收标准和备注。状态、已确认进展和下一步保持来源只读；其余字段仅管理角色且项目进行中可改。
- [x] 批量修改先暂存草稿；保存失败保留输入。个人视图保存列顺序/显隐、冻结列数、分组、当前筛选，按项目和账号隔离。
- [x] 执行 `npm run test:unit -- src/components/task-management/workProgressGridModel.test.ts`。

## 3. 桌面工作台

Files: 新建 `WorkProgressGrid.tsx`, `WorkProgressGridWorkspace.tsx`, `workProgressGrid.css`；修改 `TaskManagementPage.tsx`。

- [x] 使用 frontend-design：灰白底、细边框、蓝色选择态、紧凑工具栏，避免新增大面积装饰。
- [x] 接入 VTable，提供列宽拖动、框选复制、双击编辑、区域粘贴、冻结首列；重点工作/负责人/状态分组可切换。保留来源信息及待确认提示。
- [x] 工具栏提供个人视图保存/删除、列配置和移动列、冻结列数；草稿区显示待保存行数及保存/放弃操作。标题单击选择，工具栏“打开详情”或标题图标进入原任务详情，验收标准仍可查看。
- [x] 页面复用现有筛选及任务详情；编辑成功重新获取该项目的任务和关键任务投影。小屏继续原卡片。

## 4. 验证与交付

- [x] 定向单元用例和前端生产构建，不跑与本次无关的全套测试。
- [x] 在 6006 隔离环境展示实际页面：归档只读、个人视图刷新保留；独立进行中演练项目验证编辑、批量粘贴、重新加载及详情。无需再调用 AI、不修改业务库。
- [x] 保存截图和本次范围记录，检查 diff 后仅提交本次文件并推送现有功能分支。
- [x] 本阶段不声明整个项目验收通过；跨端共享视图、自定义字段建模、公式、多人实时协同、看板、时间线及企业微信原表映射属于后续范围。

# 项目详情页下发动作修复设计

## 目标

使项目详情页“下发给负责人”按钮调用既有的项目下发接口，并在完成后更新页面状态。

## 范围

仅修改 `frontend/src/pages/ProjectDetailPage.tsx`。不改变后端 `/api/projects/{id}/dispatch` 的角色校验、项目状态机或通知内容。

## 方案

详情页引入已有的 `dispatchProject` API 和通知工具。点击按钮时设置提交中状态，调用 `dispatchProject(project.id)`；成功后重新读取项目详情以显示 `dispatched` 状态，并显示成功提示；失败时显示接口返回的信息。请求进行中时禁用重复操作。

## 验收

1. 点击按钮会发起 `POST /api/projects/{id}/dispatch`。
2. 成功后项目不再显示草稿状态，页面提示已下发。
3. 失败时显示具体错误，不再静默无响应。
4. 自动化回归检查覆盖详情页不能保留空的 `onDispatch` 回调。

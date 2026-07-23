# Dashboard 本地浏览器验收报告

**时间**: 2026-07-20 18:02:46
**分支**: fix-dashboard-loading-and-static-assets
**Commit**: 54a6878e234cfe5c2649d2c131c2dc3905f06686
**前端**: http://127.0.0.1:6001
**后端**: http://127.0.0.1:8008
**用户**: moways

---

## 验收结果

| 场景 | 结果 | 详情 |
|------|------|------|
| 正常数据态 | **PASS** | 任务总数可见，统计卡片正常，无闪动 |
| 首次慢加载 | **PASS** | 骨架→数据切换一次完成，无闪烁 |
| 已有数据刷新 | **PASS** | 旧数据保留，更新中指示器可见，完成后恢复 |
| 刷新失败保留旧数据 | **PASS** | 500 响应后旧数据保留，错误横幅显示「更新失败，当前显示上次成功加载的数据。」 |
| 错误恢复 | **PASS** | 恢复正常请求后错误横幅消失，页面正常 |
| favicon | **PASS** | href=data:, 无 favicon.ico 请求 |
| Console | **PASS** | 0 console errors, 0 page errors, 无 Maximum update depth |

---

## 场景详述

### A — 正常数据态

- 登录后导航至 `/home/dashboard`
- 任务总数、统计卡片、本月重点面板正常显示
- 无闪动或循环渲染

### B — 首次慢加载

- 通过 `page.reload()` 获得干净 React mount
- overview 请求延迟 2000ms（Playwright route 拦截）
- 延迟期间：骨架（skeleton-shimmer）可见，正式数据不可见
- 请求完成后：骨架消失，正式数据正常渲染
- 验证：从 loading 到 dataReady 仅发生一次完整切换

### C — 已有数据刷新

- 在已有数据状态下切换月份
- overview 请求延迟 2000ms
- 延迟期间：旧数据保留，「更新中...」指示器可见，全页骨架不可见
- 请求完成后：「更新中...」消失，正式数据正常显示

### D — 已有数据刷新失败 & 恢复

- 拦截 overview 返回 500
- 切换月份触发刷新
- 刷新失败后：
  - 旧数据保留（任务总数等仍可见）
  - 错误横幅显示：「更新失败，当前显示上次成功加载的数据。」
  - 全页骨架不可见
  - 无虚假零值
- 恢复请求后：错误横幅消失，新数据正常加载

### E — favicon & 控制台

- favicon 为 `data:,`（data URI 占位，不请求 /favicon.ico）
- 0 console errors
- 0 page errors
- 无 Maximum update depth 错误
- 无持续重定向
- 无 overview 请求死循环

---

## Console 状态

- console errors: 0
- console warnings: 0
- page errors: 0

---

## 持续闪烁检查

- 5 秒内 overview 请求无循环
- 页面渲染稳定，无从 loading→dataReady→loading 的反复切换

---

## 截图

| 场景 | 文件 |
|------|------|
| 正常数据态 | 01-data-ready.png |
| 首次慢加载-骨架 | 02-initial-loading.png |
| 首次慢加载-完成 | 03-initial-loaded.png |
| 刷新中 | 04-refreshing.png |
| 刷新完成 | 05-refresh-complete.png |
| 刷新失败 | 06-refresh-error.png |
| 错误恢复 | 07-error-recovered.png |

---

## Plywright Trace

`playwright-trace.zip` — 可在 `npx playwright show-trace` 中查看完整交互过程

---

## Git 状态

- 工作区 clean
- `.tmp-dashboard-acceptance/` 为 untracked，未 git add
- 无 amend、无 push、无 PR

# 博维 AI 驾驶舱 V2 前端

本目录是与旧版 `frontend/` 并行运行的独立 V2 前端。V2 复用现有后端接口，不修改后端代码。

## 启动方式

推荐从仓库根目录运行：

```powershell
.\start-frontend-v2-dev.bat
```

启动器会检查 `6005` 和 `8011` 端口，先等待后端 `/api/health` 返回 `ok`，再等待 Vite 页面返回 `200`，最后打开浏览器。

停止服务：

```powershell
.\stop-frontend-v2-dev.bat
```

也可以手动启动：先启动后端 `http://127.0.0.1:8011`，再在本目录运行 `npm install` 和 `npm run dev`，最后打开 `http://127.0.0.1:6005`。

不要混用 `localhost` 和 `127.0.0.1`，因为后端 `bowei_session` 是 host-only Cookie。

## 命令

```bash
npm install
npm run dev
npm run build
npm run test:unit
npm run test:contracts
npm run test:all
```

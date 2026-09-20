# 博维 AI 驾驶舱 V2 前端

本目录是与旧版 `frontend/` 并行运行的独立 V2 前端。V2 复用现有后端接口，不修改后端代码。

## 启动顺序

1. 启动后端 `http://127.0.0.1:8011`。
2. 在本目录运行 `npm install`（首次运行）。
3. 运行 `npm run dev`。
4. 打开 `http://127.0.0.1:6005`。

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

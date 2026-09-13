# 本地独立前端

本目录是独立的 Vite + React + TypeScript 前端，不会改动旧的 `app/static` 前端。
## 启动顺序

1. 先启动后端 `http://127.0.0.1:8011`。2. 再打开 `http://127.0.0.1:6004` 使用本地前端。3. 不要混用 `localhost` 和 `127.0.0.1`，因为后端 `bowei_session` 是 host-only cookie。
## 开发配置
- Vite dev server host: `127.0.0.1`
- Vite dev server port: `6004`
- API proxy target: `http://127.0.0.1:8011`

## 命令

```bash
npm install
npm run dev
npm run build
```

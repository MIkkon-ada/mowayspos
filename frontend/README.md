# 本地独立前端

本目录是独立的 Vite + React + TypeScript 前端，不会改动旧的 `app/static` 前端。
## 启动顺序

1. 先打开 `http://127.0.0.1:8008` 登录旧系统。2. 再打开 `http://127.0.0.1:6001` 使用本地前端。3. 不要混用 `localhost` 和 `127.0.0.1`，因为后端 `bowei_session` 是 host-only cookie。
## 开发配置
- Vite dev server host: `127.0.0.1`
- Vite dev server port: `6001`
- API proxy target: `http://127.0.0.1:8008`

## 命令

```bash
npm install
npm run dev
npm run build
```

# 前端构建体积基线与按需依赖治理设计

## 目标

为前端生产构建建立可复现、可在本地和 CI 中失败关闭的性能基线。门禁必须验证首屏入口的资源预算、主要懒加载页面的大小，以及 ExcelJS 这类低频大型依赖不会进入初始加载闭包。

本次不重写页面、不替换 Excel 导出库，也不把网络、设备或远程服务波动当成性能回归。

## 已确认事实

2026-09-13 的生产构建产物为：

- 入口 JavaScript：`index-*.js`，302,987 B（构建输出 gzip 94.48 kB）。
- 入口 CSS：`index-*.css`，97,388 B（构建输出 gzip 17.22 kB）。
- 最大页面 chunk：`MeetingPage-*.js`，95,588 B（gzip 24.54 kB）。
- ExcelJS：`exceljs.min-*.js`，940,194 B（gzip 271.33 kB）。

`exportPlanTableExcel.ts` 与 `exportTasksExcel.ts` 均使用 `await import('exceljs')`。因此 ExcelJS 是用户触发导出后才需要的依赖，不能被入口预算计入，也不能因为其绝对大小而直接阻止构建。

## 方案选择

比较三种方案：

1. 只保留 Vite 的 500 kB 警告。实现成本最低，但不度量入口闭包，无法阻止 ExcelJS 意外回流到首屏。
2. 使用 Lighthouse / 真实浏览器阈值。能覆盖更多运行时指标，但在本地与 CI 中会受 CPU、浏览器缓存、网络字体和容器环境波动影响；当前没有稳定的端到端部署目标。
3. 解析 Vite manifest 和已生成资源，建立确定性 bundle 基线。推荐：能准确区分入口与动态 chunk，直接验证本次最重要的初始加载隔离，并可在现有 `npm run build` / CI 流程中稳定运行。

选择方案 3。

## 架构

### 构建清单

在 `vite.config.ts` 启用 `build.manifest`，让每次生产构建生成 `dist/.vite/manifest.json`。manifest 是唯一用于计算资源依赖图的输入；脚本不得依赖带哈希的文件名或 Vite 控制台文本。

### 基线文件

新增 `frontend/performance/bundle-baseline.json`，保存逻辑资源预算，而非某次哈希文件名：

- `initial_js`：入口及其静态 imports 的 JavaScript 总 raw/gzip 上限；
- `initial_css`：入口关联 CSS 总 raw/gzip 上限；
- `largest_route_js`：单个异步页面 chunk 的 raw/gzip 上限；
- `exceljs_dynamic_js`：ExcelJS chunk 的 raw/gzip 上限，并标记必须不属于入口闭包。

上限以当前真实产物加适度、明确的工程余量确定：初始 JS 340,000 B / 110,000 B gzip，初始 CSS 110,000 B / 24,000 B gzip，页面 chunk 110,000 B / 32,000 B gzip，ExcelJS 动态 chunk 1,000,000 B / 300,000 B gzip。

### 校验脚本

新增 `frontend/scripts/check-bundle-baseline.mjs`。该脚本：

1. 读取 manifest，定位唯一标记为 `isEntry` 的应用入口记录；
2. 递归追踪该记录的静态 `imports`，以去重后的资源集合计算入口 JS/CSS raw 与 gzip 字节数；
3. 将 manifest 中非入口、非 ExcelJS 的页面 JavaScript chunk 逐个与页面预算比较；
4. 定位 ExcelJS 输出资源，验证其大小预算，并断言它不在入口静态 imports 闭包；
5. 打印稳定、可审阅的指标表；任一缺失资源、未知入口、预算超限或隔离失败均退出非零。

gzip 值必须通过 Node `zlib.gzipSync` 对实际文件计算，不能解析 Vite 的人类可读控制台输出。

### 命令与 CI

新增两个 npm 命令：

- `check:bundle:dist`：仅分析已生成的 `dist`；供本地快速复验与 CI 使用。
- `test:bundle`：先执行 `npm run build`，再执行 `npm run check:bundle:dist`；供开发者一次性运行。

现有 CI 在 `Frontend build` 成功后执行 `npm run check:bundle:dist`。这样构建失败、预算失败和资源隔离失败都会阻止合并，且不会重复构建。

## 测试策略

- 单元式脚本测试使用临时 manifest 与临时资源目录，覆盖入口静态闭包去重、CSS 计数、超预算、ExcelJS 混入入口和缺失 ExcelJS 五种情况。
- 源码契约测试固定两个导出模块继续以动态 import 加载 `exceljs`，防止未来改为静态 import。
- 集成验证运行 `npm run test:bundle`，再运行完整前端测试和生产构建。

## 兼容性与非目标

- 不修改 API、前端路由、导出文件格式、导出交互或 ExcelJS 版本。
- 不将 ExcelJS 的独立 chunk-size 警告简单隐藏或提高 Vite 警告阈值。
- 不声称 bundle 指标等价于真实用户 LCP、INP 或下载耗时；它们是当前部署前可稳定验证的首屏资源与按需依赖指标。真实浏览器性能采样应在有稳定预发布地址后另立计划。
- 当新增业务页面合理超出预算时，必须先更新基线文件和说明，再允许 CI 通过；禁止静默放宽脚本默认值。

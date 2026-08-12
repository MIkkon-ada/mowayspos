# 成果文件上传功能开发计划

## 1. 需求背景

### 当前状态
- 提交工作汇报时，成果（achievements）只能填写名称和粘贴外部链接
- 无法直接上传本地文件（如文档、图片等）
- 用户反馈希望支持文件上传，方便成果归档和查看

### 目标
- 支持在提交汇报时为每个成果上传关联文件
- 文件可在线预览或下载
- 与现有成果流程无缝集成

---

## 2. 功能范围

### MVP 版本（v1.0）
- ✅ 支持上传单个/多个文件
- ✅ 支持常见格式：PDF、Word、Excel、PPT、图片
- ✅ 文件大小限制：单文件 ≤ 50MB
- ✅ 上传进度显示
- ✅ 已上传文件列表展示
- ✅ 删除已上传文件
- ✅ 保留原有链接输入功能

### 后续版本（v2.0）
- 图片在线预览
- 云存储迁移（OSS/COS/S3）
- 文件版本管理
- 批量下载

---

## 3. 技术方案

### 3.1 存储方案（MVP）

```
本地存储方案：
├── uploads/
│   └── achievements/
│       ├── {year}/{month}/{day}/
│       │   ├── {uuid}_{original_filename}
│       │   └── ...
│   └── ...
```

**优点**：
- 实现简单，无需额外服务
- 适合 Docker 部署场景
- 可通过 nginx 直接提供静态访问

**缺点**：
- 多实例部署时需共享存储
- 无 CDN 加速

### 3.2 数据库设计

**复用现有字段**：
```sql
-- achievements 表已有 file_link 字段
ALTER TABLE achievements 
ADD COLUMN IF NOT EXISTS file_path VARCHAR(500);  -- 本地存储路径
ALTER TABLE achievements 
ADD COLUMN IF NOT EXISTS file_name VARCHAR(255);  -- 原始文件名
ALTER TABLE achievements 
ADD COLUMN IF NOT EXISTS file_size BIGINT;        -- 文件大小（字节）
ALTER TABLE achievements 
ADD COLUMN IF NOT EXISTS file_type VARCHAR(50);    -- 文件类型（pdf/docx/xlsx...）
```

### 3.3 API 设计

#### 上传文件
```
POST /api/achievements/upload
Content-Type: multipart/form-data

Request:
  - file: File              # 文件对象
  - achievement_name: string # 关联的成果名称（可选）

Response (200):
{
  "success": true,
  "data": {
    "file_url": "/uploads/achievements/2026/7/23/uuid_filename.pdf",
    "file_path": "/app/uploads/achievements/2026/7/23/uuid_filename.pdf",
    "file_name": "项目方案.pdf",
    "file_size": 2048576,
    "file_type": "pdf",
    "download_url": "/api/achievements/download/{id}"
  }
}

Error (400):
{
  "success": false,
  "error": "文件大小超过限制（最大 50MB）"
}
```

#### 删除文件
```
DELETE /api/achievements/files/{file_id}

Response (200):
{
  "success": true,
  "message": "文件删除成功"
}
```

#### 下载文件
```
GET /api/achievements/download/{achievement_id}

Response: 文件流（Content-Disposition: attachment）
```

---

## 4. 开发任务清单

### Phase 1: 后端基础（预计 3-4 小时）

#### Task 1.1: 数据库迁移脚本 [30min]
- [ ] 创建 `migrations/add_achievement_file_fields.sql`
- [ ] 添加 `file_path`, `file_name`, `file_size`, `file_type` 字段
- [ ] 编写回滚脚本

#### Task 1.2: 文件上传工具类 [1h]
- [ ] 创建 `bowei_ai_dashboard/app/utils/file_upload.py`
- [ ] 实现文件校验（类型、大小）
- [ ] 实现按日期分目录存储
- [ ] 实现 UUID 文件名生成（防冲突）
- [ ] 配置常量定义（`UPLOAD_DIR`, `MAX_FILE_SIZE`, `ALLOWED_EXTENSIONS`）

#### Task 1.3: 上传 API 接口 [1.5h]
- [ ] 创建 `bowei_ai_dashboard/app/routers/achievement_files.py`
- [ ] 实现 `POST /upload` 接口
- [ ] 实现 `DELETE /files/{file_id}` 接口
- [ ] 实现 `GET /download/{id}` 接口
- [ ] 添加权限校验（登录用户）

#### Task 1.4: 路由注册与配置 [30min]
- [ ] 在 `main.py` 中注册新路由
- [ ] 添加 nginx 静态文件配置
- [ ] 更新 `.env.example` 添加上传相关配置

---

### Phase 2: 前端实现（预计 3-4 小时）

#### Task 2.1: 上传组件开发 [2h]
- [ ] 创建 `frontend/src/components/AchievementFileUpload.tsx`
- [ ] 实现拖拽上传区域
- [ ] 实现点击选择文件
- [ ] 实现上传进度条
- [ ] 实现已上传文件列表（带删除按钮）
- [ ] 文件类型图标显示（PDF/Word/Excel/PPT/Image）

#### Task 2.2: 集成到成果编辑区 [1h]
- [ ] 修改 `VoiceUpdateEditableFieldsSection.tsx`
  - 在成果链接输入框旁添加"上传文件"按钮
  - 显示已上传文件列表
  - 将上传结果写入 `file_link` 字段
- [ ] 修改 `VoiceUpdateTaskReportsSection.tsx`
  - 在任务卡成果区域同样添加上传功能
  - 展示已关联的文件

#### Task 2.3: 确认中心展示优化 [1h]
- [ ] 修改 `ConfirmPage.tsx`
  - 成果卡片显示文件附件图标
  - 点击可下载/预览
- [ ] 添加文件下载/预览的 API 调用函数

---

### Phase 3: 测试与优化（预计 2 小时）

#### Task 3.1: 功能测试 [1h]
- [ ] 测试上传 PDF 文件
- [ ] 测试上传 Word/Excel/PPT
- [ ] 测试上传图片
- [ ] 测试超大文件拒绝（>50MB）
- [ ] 测试非法文件类型拒绝（.exe 等）
- [ ] 测试中文文件名处理
- [ ] 测试特殊字符文件名
- [ ] 测试删除已上传文件
- [ ] 测试下载文件

#### Task 3.2: 边界情况处理 [30min]
- [ ] 网络中断时的上传状态
- [ ] 并发上传同一文件
- [ ] 文件名超长处理
- [ ] 磁盘空间不足提示

#### Task 3.3: UI/UX 打磨 [30min]
- [ ] 上传中的 loading 动画
- [ ] 错误提示友好化
- [ ] 移动端适配检查
- [ ] 暗色模式兼容性

---

### Phase 4: 部署与文档（预计 1 小时）

#### Task 4.1: 部署配置 [30min]
- [ ] 更新 `docker-compose.yml` 添加 volume 挂载
  ```yaml
  volumes:
    - ./uploads:/app/uploads  # 持久化上传文件
  ```
- [ ] 更新 `nginx.conf` 添加静态文件路由
- [ ] 更新 `.gitignore` 排除 `uploads/` 目录

#### Task 4.2: 文档更新 [30min]
- [ ] 更新 README.md 使用说明
- [ ] 编写接口文档（OpenAPI/Swagger）
- [ ] 记录配置项说明

---

## 5. 文件变更清单

### 新增文件
```
bowei_ai_dashboard/
├── app/utils/file_upload.py          # 文件上传工具类
├── app/routers/achievement_files.py  # 文件上传 API
└── migrations/
    └── add_achievement_file_fields.sql

frontend/src/
└── components/
    └── AchievementFileUpload.tsx     # 上传组件

docs/
└── achievement-file-upload-plan.md   # 本文档
```

### 修改文件
```
bowei_ai_dashboard/
├── app/main.py                       # 注册新路由
├── app/models.py                     # Achievement 模型添加字段
└── config.py                         # 添加上传相关配置

frontend/src/features/voice-update/
├── VoiceUpdateEditableFieldsSection.tsx  # 集成上传组件
└── VoiceUpdateTaskReportsSection.tsx     # 集成上传组件

frontend/src/pages/
└── ConfirmPage.tsx                   # 展示文件附件

docker-compose.yml                    # 添加 volume
nginx.conf                            # 静态文件路由
.gitignore                            # 忽略 uploads/
```

---

## 6. 时间线

| 阶段 | 任务 | 预计时间 | 累计时间 |
|------|------|---------|---------|
| **Phase 1** | 后端基础 | 3-4h | 3-4h |
| **Phase 2** | 前端实现 | 3-4h | 6-8h |
| **Phase 3** | 测试优化 | 2h | 8-10h |
| **Phase 4** | 部署文档 | 1h | 9-11h |

**总计：9-11 小时（约 1.5 个工作日）**

建议分两天完成：
- **Day 1**: Phase 1 + Phase 2（核心功能开发）
- **Day 2**: Phase 3 + Phase 4（测试上线）

---

## 7. 验收标准

### 功能验收
- [ ] 用户可在成果处上传文件（拖拽/点击）
- [ ] 上传后文件显示在成果列表中
- [ ] 已上传文件可删除
- [ ] 提交汇报时文件信息一并保存
- [ ] 确认中心可查看/下载成果文件
- [ ] 超大文件/非法格式被正确拒绝

### 性能验收
- [ ] 10MB 以内文件上传 < 5秒
- [ ] 50MB 文件上传 < 30秒
- [ ] 页面无卡顿

### 安全验收
- [ ] 未登录用户无法上传
- [ ] 文件类型严格校验
- [ ] 路径遍历攻击防护
- [ ] 文件名特殊字符转义

---

## 8. 风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| 磁盘空间不足 | 无法上传 | 定期清理 + 监控告警 |
| 并发上传性能差 | 用户体验差 | 异步队列 + 进度反馈 |
| 文件安全漏洞 | 安全风险 | 严格的类型/大小校验 |
| Docker 重启丢数据 | 数据丢失 | Volume 持久化 |

---

## 9. 后续扩展方向

1. **云存储集成**：迁移到阿里云 OSS / 腾讯云 COS
2. **在线预览**：集成 PDF.js / Office Online Viewer
3. **图片压缩**：自动压缩大尺寸图片
4. **病毒扫描**：上传文件安全检测
5. **版本管理**：同一成果多版本文件对比

---

## 10. 开始开发？

确认以下信息后即可开始：

- [ ] 存储方案选择：**本地存储（MVP）**
- [ ] 文件大小限制：**50MB**
- [ ] 支持格式：PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX, PNG, JPG, GIF
- [ ] 是否需要立即开始编码？**是/否**

---

**文档版本**: v1.0  
**创建时间**: 2026-07-23  
**负责人**: AI Assistant  
**预计完成**: 2026-07-24

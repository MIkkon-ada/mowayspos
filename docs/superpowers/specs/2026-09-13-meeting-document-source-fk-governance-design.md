# 会议文档来源外键治理设计

## 目标

消除 `meetings` 与 `meeting_document_sources` 之间的循环外键，使 SQLAlchemy 能稳定排序建表和删表，同时保持会议纪要上传、AI 分析、审阅、下载、导出和项目清理的既有行为。

## 已验证事实

- `Meeting.document_source_id` 是所有读取链路的唯一关联：审阅包、下载、导出、变更回写和分析结果展示均通过它查找文档来源。
- `MeetingDocumentSource.meeting_id` 只在 `project_meeting_agent_processing.py` 创建 AI 草稿会议后回填，仓库中没有读取方。
- 两个字段均带 `ON DELETE SET NULL` 外键，形成 metadata 的不可排序循环，并在完整 pytest 中产生 42 条 SQLAlchemy 警告。
- 项目永久清理先删除会议、再删除文档来源；该顺序不依赖反向字段。

## 备选方案

1. 为其中一个外键标记 `use_alter`：只压制 metadata 排序问题，但保留无读取方的字段、索引和双向约束。
2. 移除 `MeetingDocumentSource.meeting_id` 及其索引和外键：保留唯一真实关联 `Meeting.document_source_id`，消除循环。**采用此方案。**
3. 移除 `Meeting.document_source_id`：会破坏现有审阅、下载、导出与变更回写链路，不采用。

## 设计

`Meeting` 继续通过可空的 `document_source_id` 持有其原始文档来源。`MeetingDocumentSource` 只描述项目级上传文件，`ProjectMeetingRun` 继续以 `document_source_id` 保留不可变分析来源。AI 草稿落库后不再向来源对象写入会议 ID。

新增 Alembic 迁移会在 SQLite 上使用 `batch_alter_table(recreate="always")` 删除反向外键、索引和列；在 PostgreSQL 上先删除外键与索引，再删除列。降级重新添加该可空列、外键和索引，并以 `meetings.document_source_id` 做尽力回填；多个会议共享同一来源时只写入最早的会议 ID，因为该旧字段从未作为业务读取依据。

## 验收

- ORM metadata 的排序不再产生 meetings/document-sources 循环警告。
- 新迁移在空 SQLite 上升级、降级和重新升级成功；升级后反向列不存在，降级后结构恢复。
- 项目会议 AI 草稿仍写入 `Meeting.document_source_id`，来源文件仍能用于审阅、下载和导出。
- 完整后端、前端、构建与迁移门禁保持通过。


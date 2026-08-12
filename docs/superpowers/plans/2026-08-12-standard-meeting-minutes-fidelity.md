# 标准会议纪要保真模式 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将公司标准 Word 纪要直接、可追溯地映射为会议草稿，避免被误判为按成员汇报的转写内容。

**Architecture:** 文档读取服务从 `.docx` 中同时保留段落和表格，新的标准纪要解析器只识别明确的固定标题与表头，返回保真结构。会议 API 将该结构作为独立响应返回；前端在存在该结构时进入标准纪要确认页，不调用通用 AI 提取，也不合并项目推进表事实。

**Tech Stack:** FastAPI、Pydantic、SQLAlchemy/Alembic、Python 标准库 ZIP/XML、React/TypeScript、node:test、pytest。

---

### Task 1: 标准纪要结构解析器

**Files:**
- Create: `bowei_ai_dashboard/app/services/standard_meeting_minutes.py`
- Create: `bowei_ai_dashboard/tests/test_standard_meeting_minutes.py`
- Modify: `bowei_ai_dashboard/app/services/meeting_document_text.py`

- [ ] **Step 1: 写出失败的 Word 结构解析测试**

```python
def test_parses_standard_minutes_without_inventing_people_or_progress():
    parsed = parse_standard_meeting_minutes(document_blocks)
    assert parsed["is_standard_minutes"] is True
    assert parsed["title"] == "AI项目落地周会"
    assert parsed["host"] == "温会林"
    assert len(parsed["agenda_items"]) == 6
    assert len(parsed["current_action_items"]) == 14
    assert len(parsed["prior_action_items"]) == 17
    assert "reports" not in parsed
```

- [ ] **Step 2: 运行失败测试**

Run: `python -m pytest tests/test_standard_meeting_minutes.py -q`

Expected: FAIL，因为 `parse_standard_meeting_minutes` 尚未定义。

- [ ] **Step 3: 实现保真结构提取**

```python
def parse_standard_meeting_minutes(blocks: list[DocumentBlock]) -> dict:
    return {
        "is_standard_minutes": has_required_sections(blocks),
        "title": first_title(blocks),
        "meeting_date": info_value(blocks, "会议时间"),
        "location": info_value(blocks, "会议地点"),
        "meeting_type": info_value(blocks, "会议类型"),
        "host": info_value(blocks, "会议主持人"),
        "participants": info_value(blocks, "与会者"),
        "agenda_items": section_items(blocks, "一、会议议程"),
        "summary": section_text(blocks, "二、会议小结与决议"),
        "current_action_items": table_rows(blocks, "本周新增待办事项"),
        "prior_action_items": table_rows(blocks, "上周待办追踪"),
        "copied_to": footer_value(blocks, "抄送"),
    }
```

只接受明确标题与表头；表格字段缺失时返回空字符串，不补全、不推断。

- [ ] **Step 4: 运行通过测试**

Run: `python -m pytest tests/test_standard_meeting_minutes.py tests/test_meeting_document_text.py -q`

Expected: PASS。

### Task 2: 会议接口与持久化字段

**Files:**
- Modify: `bowei_ai_dashboard/app/models.py`
- Modify: `bowei_ai_dashboard/app/schemas.py`
- Modify: `bowei_ai_dashboard/app/services/meeting_revisions.py`
- Modify: `bowei_ai_dashboard/app/routers/meetings.py`
- Create: `bowei_ai_dashboard/migrations/versions/<revision>_add_standard_meeting_minutes_fields.py`
- Modify: `bowei_ai_dashboard/tests/test_meeting_metadata.py`

- [ ] **Step 1: 为结构字段写失败测试**

```python
def test_meeting_snapshot_keeps_standard_minutes_sections():
    row = models.Meeting(
        agenda_items_json='["市场推广"]',
        prior_action_items_json='[{"编号":"上周-01"}]',
    )
    revision = append_meeting_revision(db, row, saved_by="owner")
    assert revision.agenda_items_json == row.agenda_items_json
    assert revision.prior_action_items_json == row.prior_action_items_json
```

- [ ] **Step 2: 验证测试失败**

Run: `python -m pytest tests/test_meeting_metadata.py -q`

Expected: FAIL，因为模型和版本快照尚无这两个字段。

- [ ] **Step 3: 最小化实现字段与 API 返回**

为 `Meeting`、`MeetingRevision`、`MeetingPayload`、前端类型和 `_SNAPSHOT_FIELDS` 增加：

```python
agenda_items_json: str = "[]"
prior_action_items_json: str = "[]"
source_mode: str = "ai_analysis"  # standard_minutes | ai_analysis
```

迁移为 `meetings` 与 `meeting_revisions` 添加非空默认值字段。`POST /api/meetings/extract-document-text` 返回 `standard_minutes` 结构；`POST /api/meetings/analyze` 仅处理非标准原文，不再用 `re.search(r"\\d+")` 推断发言人模式。

- [ ] **Step 4: 验证保存与路由行为**

Run: `python -m pytest tests/test_meeting_metadata.py tests/test_standard_meeting_minutes.py tests/test_meeting_draft_review.py -q`

Expected: PASS，且标准文件没有进入 `_PROMPT_REPORT`。

### Task 3: 新建页标准纪要确认视图

**Files:**
- Modify: `frontend/src/api/meetings.ts`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/features/meeting/NewMeetingModal.tsx`
- Create: `frontend/tests/standardMeetingMinutesFidelity.test.mjs`

- [ ] **Step 1: 写失败的前端行为测试**

```javascript
test('standard minutes populate a fidelity review without member progress updates', () => {
  assert.match(modal, /source_mode: 'standard_minutes'/)
  assert.match(modal, /会议议程/)
  assert.match(modal, /上周待办追踪/)
  assert.doesNotMatch(standardReviewSource, /成员进度更新/)
})
```

- [ ] **Step 2: 验证测试失败**

Run: `node --test tests/standardMeetingMinutesFidelity.test.mjs`

Expected: FAIL，因为上传结果尚未驱动标准纪要确认视图。

- [ ] **Step 3: 实现前端分流和保真呈现**

`extractMeetingDocumentText` 返回 `standard_minutes` 后，前端应：

```ts
if (result.standard_minutes?.is_standard_minutes) {
  setForm(fromStandardMinutes(result.standard_minutes))
  setStandardMinutes(result.standard_minutes)
  setStep('review')
  return
}
```

确认页显示明确标识“已按标准纪要读取”，并按原始顺序渲染会议议程、会议小结与决议、本周待办和上周待办追踪。仅普通文字/音频材料仍允许进入 `handleAnalyze`。

- [ ] **Step 4: 验证前端行为测试**

Run: `node --test tests/standardMeetingMinutesFidelity.test.mjs tests/newMeetingMultiSource.test.mjs`

Expected: PASS。

### Task 4: 第三页详情与完整验证

**Files:**
- Modify: `frontend/src/features/meeting/MeetingDetailWorkspace.tsx`
- Modify: `frontend/tests/meetingDetailWorkspace.test.mjs`

- [ ] **Step 1: 写失败的详情页结构测试**

```javascript
assert.match(detail, /meeting\.agenda_items_json/)
assert.match(detail, /meeting\.prior_action_items_json/)
assert.match(detail, /抄送/)
```

- [ ] **Step 2: 验证测试失败**

Run: `node --test tests/meetingDetailWorkspace.test.mjs`

Expected: FAIL，因为详情页未区分标准纪要字段。

- [ ] **Step 3: 实现详情页保真渲染**

标准纪要详情依次渲染基本信息、议程、决议、本周待办、上周追踪、整理人/抄送；不显示成员进度组件。

- [ ] **Step 4: 跑完整验证**

Run:

```text
python -m pytest tests/test_standard_meeting_minutes.py tests/test_meeting_document_text.py tests/test_meeting_metadata.py tests/test_meeting_draft_review.py -q
node --test tests/standardMeetingMinutesFidelity.test.mjs tests/newMeetingMultiSource.test.mjs tests/meetingDetailWorkspace.test.mjs
npm run build
```

Expected: 全部通过。受保护本地数据库迁移只在完成独立备份和人工授权后执行。

## 自检

- 规格中的固定区块、保真规则、混合材料规则和验收标准都由任务 1–4 覆盖。
- 所有结构字段名称在模型、API、前端与测试中一致：`agenda_items_json`、`prior_action_items_json`、`source_mode`。
- 无未定义实现步骤、无待定占位符；不会用项目推进表补充标准 Word 的事实。

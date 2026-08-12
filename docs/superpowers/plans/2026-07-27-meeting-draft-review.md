# 会议草稿原文与 AI 纪要展示实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让项目负责人和 CEO 在会议正式发布前查看原文与 AI 提取纪要，并严格隔离草稿权限与 AI 确认中心。

**Architecture:** 复用 `meetings` 的状态及原文、AI 结果字段。后端集中实现草稿读权限和首次草稿通知；前端在现有会议详情页并列呈现原文和 AI 纪要。

**Tech Stack:** FastAPI、SQLAlchemy、pytest、React、TypeScript、站内通知服务、Node 测试。

---

### Task 1: 草稿权限和通知

**Files:**
- Create: `bowei_ai_dashboard/tests/test_meeting_draft_review.py`
- Modify: `bowei_ai_dashboard/app/routers/meetings.py:72-154,238-255`

- [ ] **Step 1: 写失败测试**

```python
def test_draft_is_visible_only_to_creator_owner_and_ceo(client, meeting, creator, owner, ceo, member):
    assert client_as(client, creator).get(f"/api/meetings/{meeting.id}").status_code == 200
    assert client_as(client, owner).get(f"/api/meetings/{meeting.id}").status_code == 200
    assert client_as(client, ceo).get(f"/api/meetings/{meeting.id}").status_code == 200
    assert client_as(client, member).get(f"/api/meetings/{meeting.id}").status_code == 403

def test_creating_draft_notifies_owner_and_ceo_once(client, db, creator, owner, ceo, project):
    response = client_as(client, creator).post("/api/meetings", json=meeting_payload(project.id))
    notices = db.query(models.Notification).filter_by(type="meeting_draft_created").all()
    assert {n.recipient_id for n in notices} == {owner.person_id, ceo.person_id}
    assert all(f"meetingId={response.json()['id']}" in n.link for n in notices)
```

- [ ] **Step 2: 运行失败测试**

Run: `pytest bowei_ai_dashboard/tests/test_meeting_draft_review.py -q`

Expected: 现有代码允许普通成员查看草稿，且未写入 `meeting_draft_created` 通知。

- [ ] **Step 3: 最小后端实现**

在 `meetings.py` 增加 `_can_view_draft(row, current_user, context, db)`；仅技术管理员、CEO、创建人和项目 `owner` 可读。`list_meetings` 过滤不可读草稿，`get_meeting` 对不可读草稿返回 403；`published` 保持既有项目访问规则。

在首次 `create_meeting` 保存 `draft` 时，使用 `notify.project_strict_owner_ids` 和 `notify.company_ceo_person_ids` 去重通知；通知类型为 `meeting_draft_created`，链接为 `/project/{row.project_id}/meeting?meetingId={row.id}`。不调用 confirmations，也不创建任务、问题、成果。

- [ ] **Step 4: 验证后端通过**

Run: `pytest bowei_ai_dashboard/tests/test_meeting_draft_review.py -q`

Expected: PASS。

- [ ] **Step 5: 提交后端**

Run: `git add bowei_ai_dashboard/app/routers/meetings.py bowei_ai_dashboard/tests/test_meeting_draft_review.py && git commit -m "feat: restrict and notify meeting drafts"`

### Task 2: 原文与 AI 纪要并列详情

**Files:**
- Create: `frontend/tests/meetingDraftReviewStructure.test.mjs`
- Modify: `frontend/src/pages/MeetingPage.tsx:1-330`

- [ ] **Step 1: 写失败结构测试**

```javascript
assert.ok(source.includes("searchParams.get('meetingId')"))
assert.ok(source.includes('提交原文'))
assert.ok(source.includes('AI 提取纪要'))
assert.ok(source.includes('selected.transcript_text'))
assert.ok(source.includes('未进入 AI 确认中心'))
```

- [ ] **Step 2: 运行失败测试**

Run: `node --test frontend/tests/meetingDraftReviewStructure.test.mjs`

Expected: FAIL，因为页面尚未提供草稿原文及深链选择。

- [ ] **Step 3: 最小前端实现**

读取 `meetingId` 查询参数并选中对应记录。草稿详情采用两栏：左栏“提交原文”渲染完整 `selected.transcript_text`；右栏“AI 提取纪要”渲染摘要、汇报、行动项、决策、风险。草稿显示“草稿 · 未进入 AI 确认中心”。创建人可编辑，项目负责人可发布/退回，CEO 不显示写操作；不得加入 confirmations API 或任务卡创建操作。

- [ ] **Step 4: 验证前端通过**

Run: `node --test frontend/tests/meetingDraftReviewStructure.test.mjs`

Expected: PASS。

- [ ] **Step 5: 提交前端**

Run: `git add frontend/src/pages/MeetingPage.tsx frontend/tests/meetingDraftReviewStructure.test.mjs && git commit -m "feat: show meeting draft source beside AI notes"`

### Task 3: 生命周期验收

**Files:**
- Modify: `bowei_ai_dashboard/tests/test_meeting_draft_review.py`

- [ ] **Step 1: 写发布后开放测试**

```python
def test_published_meeting_is_visible_to_project_member_and_creates_no_confirmation(client, db, owner, member, meeting):
    client_as(client, owner).patch(f"/api/meetings/{meeting.id}/status", json={"publish_status": "published"})
    assert client_as(client, member).get(f"/api/meetings/{meeting.id}").status_code == 200
    assert db.query(models.Confirmation).count() == 0
```

- [ ] **Step 2: 运行失败测试**

Run: `pytest bowei_ai_dashboard/tests/test_meeting_draft_review.py::test_published_meeting_is_visible_to_project_member_and_creates_no_confirmation -q`

Expected: 在实现中若发布可见性错误，测试失败。

- [ ] **Step 3: 仅修正发布可见性**

确保草稿权限逻辑不应用于 `published`；已发布会议继续由项目访问权限决定。不得改动 AI 确认中心。

- [ ] **Step 4: 完整验证**

Run: `pytest bowei_ai_dashboard/tests/test_meeting_draft_review.py -q && node --test frontend/tests/meetingDraftReviewStructure.test.mjs`

Expected: PASS。

- [ ] **Step 5: 提交验收测试**

Run: `git add bowei_ai_dashboard/tests/test_meeting_draft_review.py && git commit -m "test: cover meeting draft review lifecycle"`

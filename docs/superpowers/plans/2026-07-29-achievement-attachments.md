# 成果库附件 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 支持成果级、多文件、可选附件的上传、入库后补传和项目内下载。

**Architecture:** 新增附件元数据表；文件写入持久化后端卷，数据库只保存定位信息。上传临时绑定到成果提交单，确认入库时转绑到正式成果；列表、下载和删除均复用项目成员权限校验。

**Tech Stack:** FastAPI multipart, SQLAlchemy/Alembic, React/TypeScript, pytest, Node test runner.

---

### Task 1: 建立附件数据模型和迁移

**Files:**
- Modify: `bowei_ai_dashboard/app/models.py`
- Create: `bowei_ai_dashboard/migrations/versions/e8f9a0b1c2d3_add_achievement_attachments.py`
- Test: `bowei_ai_dashboard/tests/test_achievement_attachments.py`

- [ ] **Step 1: Write the failing test**

```python
def test_attachment_metadata_has_required_links():
    from app.models import AchievementAttachment
    assert {"project_id", "achievement_id", "achievement_submission_id", "storage_key", "original_name", "mime_type", "size_bytes", "deleted_at"} <= set(AchievementAttachment.__table__.c.keys())
```

- [ ] **Step 2: Verify RED**

Run: `pytest tests/test_achievement_attachments.py::test_attachment_metadata_has_required_links -q`

Expected: FAIL because `AchievementAttachment` is not defined.

- [ ] **Step 3: Implement the model and migration**

Add `AchievementAttachment` with foreign keys for project, achievement and achievement submission; make the last two nullable. Store UUID `storage_key`, original name, MIME type, byte count, uploader/person, `deleted_at` and `deleted_by`. Create the matching Alembic table and indexes.

- [ ] **Step 4: Verify GREEN**

Run: `pytest tests/test_achievement_attachments.py::test_attachment_metadata_has_required_links -q`

Expected: PASS.

### Task 2: Add secure upload, list, download and delete routes

**Files:**
- Create: `bowei_ai_dashboard/app/routers/achievement_attachments.py`
- Modify: `bowei_ai_dashboard/app/main.py`
- Modify: `docker-compose.prod.yml`
- Test: `bowei_ai_dashboard/tests/test_achievement_attachments.py`

- [ ] **Step 1: Write failing API tests**

```python
def test_member_uploads_pdf_and_project_member_downloads(client, member_headers, achievement):
    result = client.post("/api/achievement-attachments", headers=member_headers, data={"project_id": achievement.project_id, "achievement_id": achievement.id}, files={"file": ("proof.pdf", b"%PDF-1.4", "application/pdf")})
    assert result.status_code == 201
    assert client.get(f"/api/achievement-attachments/{result.json()['id']}/download", headers=member_headers).status_code == 200
```

- [ ] **Step 2: Verify RED**

Run: `pytest tests/test_achievement_attachments.py -q`

Expected: FAIL because the routes do not exist.

- [ ] **Step 3: Implement routes and storage**

Implement `POST /api/achievement-attachments`, `GET /api/achievement-attachments?achievement_id=`, `GET /api/achievement-attachments/{id}/download`, and `DELETE /api/achievement-attachments/{id}`. Allow PDF, Office files, images, ZIP and RAR; reject video, files above 20 MiB and totals above 100 MiB. Store bytes under `/app/data/achievement-attachments/{project_id}/{uuid}`, mount `${MOWAYS_DATA_ROOT:-/data/mowayspos}/achievement-attachments:/app/data/achievement-attachments`, use `FileResponse` for downloads, and soft-delete metadata. Upload/delete requires uploader, project owner or tech admin; list/download requires project membership.

- [ ] **Step 4: Verify GREEN**

Run: `pytest tests/test_achievement_attachments.py -q`

Expected: PASS for permitted PDF upload/download, rejected video and rejected unauthorized delete.

### Task 3: Bind pending attachments to the confirmed outcome

**Files:**
- Modify: `bowei_ai_dashboard/app/schemas.py`
- Modify: `bowei_ai_dashboard/app/routers/achievement_submissions.py`
- Modify: `frontend/src/api/achievements.ts`
- Modify: `frontend/src/types.ts`
- Test: `bowei_ai_dashboard/tests/test_achievement_attachments.py`

- [ ] **Step 1: Write the failing transfer test**

```python
def test_confirming_submission_moves_attachment_to_achievement(client, owner_headers, submission, pending_attachment):
    response = client.patch(f"/api/achievement-submissions/{submission.id}/confirm", headers=owner_headers)
    assert response.status_code == 200
    assert db.get(models.AchievementAttachment, pending_attachment.id).achievement_id == response.json()["achievement"]["id"]
```

- [ ] **Step 2: Verify RED**

Run: `pytest tests/test_achievement_attachments.py::test_confirming_submission_moves_attachment_to_achievement -q`

Expected: FAIL because confirmation does not transfer attachments.

- [ ] **Step 3: Implement submission binding**

Add `attachment_ids: list[int] = []` to `AchievementSubmissionPayload`. On submission creation, validate same-project, unbound and uploader-owned attachments, then set `achievement_submission_id`. After confirmation creates and flushes `Achievement`, set every non-deleted attachment on that submission to `achievement_id=ach.id` and clear `achievement_submission_id`.

- [ ] **Step 4: Verify GREEN**

Run: `pytest tests/test_achievement_attachments.py::test_confirming_submission_moves_attachment_to_achievement -q`

Expected: PASS.

### Task 4: Add attachment controls to the achievement library

**Files:**
- Modify: `frontend/src/api/achievements.ts`
- Modify: `frontend/src/pages/AchievementsPage.tsx`
- Create: `frontend/tests/achievementAttachmentsStructure.test.mjs`

- [ ] **Step 1: Write the failing frontend test**

```javascript
test('achievement detail manages optional attachments', () => {
  assert.match(source, /uploadAchievementAttachment/)
  assert.match(source, /fetchAchievementAttachments/)
  assert.match(source, /deleteAchievementAttachment/)
  assert.match(source, /accept="\.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png,.gif,.webp,.zip,.rar"/)
})
```

- [ ] **Step 2: Verify RED**

Run: `node --test tests/achievementAttachmentsStructure.test.mjs`

Expected: FAIL because attachment controls do not exist.

- [ ] **Step 3: Implement upload and library detail UI**

Add `FormData` upload, list and soft-delete helpers. In `AchievementsPage`, load attachments when the selected achievement changes; show name, size, uploader, time and download link, with image preview. Add a multiple-file input with the exact accepted list, per-file progress/error/retry and delete action for authorized users. Keep the legacy single `file_link` as a separate external link.

- [ ] **Step 4: Verify GREEN and build**

Run: `node --test tests/achievementAttachmentsStructure.test.mjs && npm run build`

Expected: PASS and Vite build exits 0.

### Task 5: Verify and commit

**Files:**
- Test: `bowei_ai_dashboard/tests/test_achievement_attachments.py`
- Test: `frontend/tests/achievementAttachmentsStructure.test.mjs`

- [ ] **Step 1: Run backend verification**

Run: `pytest tests/test_achievement_attachments.py tests/test_achievement_payload_defaults.py tests/test_achievement_log_actions.py -q`

Expected: PASS.

- [ ] **Step 2: Run frontend verification**

Run: `node --test tests/achievementAttachmentsStructure.test.mjs && npm run build`

Expected: PASS.

- [ ] **Step 3: Review and commit**

Run: `git diff --check && git status --short`

Expected: no whitespace errors; stage only the attachment feature files, then commit with `git commit -m "feat: add achievement evidence attachments"`.

# 立项资料 AI 生成工作推进表 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让项目负责人上传多份立项资料，异步生成有来源依据、人员匹配和重复提示的工作推进表草稿，人工确认后追加到现有立项表单。

**Architecture:** 新增项目级立项附件与分析任务表，上传接口负责安全保存文件，独立解析服务把 PDF、Word、Excel、TXT 转成带位置的文本片段，AI 服务返回严格结构化草稿并执行确定性人员匹配和重复分类。FastAPI `BackgroundTasks` 驱动持久化分析任务，前端通过轮询展示进度与预览；“应用”只合并到 `OwnerSubmitModal` 本地草稿，正式写入仍复用现有 `owner-submit` 事务。

**Tech Stack:** FastAPI、SQLAlchemy、Alembic、Pydantic、Anthropic/OpenAI-compatible SDK、pypdf、python-docx、openpyxl、xlrd、React 19、TypeScript、pytest。

---

### Task 1: 建立附件和分析任务的数据契约

**Files:**
- Modify: `bowei_ai_dashboard/requirements.txt`
- Modify: `Dockerfile.backend`
- Modify: `bowei_ai_dashboard/app/models.py`
- Modify: `bowei_ai_dashboard/app/schemas.py`
- Create: `bowei_ai_dashboard/migrations/versions/d2e3f4a5b6c7_add_project_init_ai_tables.py`
- Create: `bowei_ai_dashboard/tests/test_project_init_ai_models.py`

- [ ] **Step 1: 写模型与迁移失败测试**

```python
def test_project_init_ai_models_have_audit_and_result_fields():
    attachment = models.ProjectInitAttachment.__table__
    run = models.ProjectInitAnalysisRun.__table__
    assert attachment.name == "project_init_attachments"
    assert {"project_id", "storage_key", "original_name", "mime_type", "size_bytes",
            "uploaded_by", "uploaded_by_person_id", "deleted_at", "deleted_by"} <= set(attachment.c.keys())
    assert attachment.c.storage_key.unique
    assert run.name == "project_init_analysis_runs"
    assert {"project_id", "attachment_ids_json", "status", "stage", "progress",
            "result_json", "file_results_json", "error_summary", "provider",
            "model_name", "created_by", "created_by_person_id", "applied_at"} <= set(run.c.keys())
    assert run.c.status.default.arg == "queued"
    assert run.c.progress.default.arg == 0


def test_project_init_analysis_request_limits_attachment_count():
    with pytest.raises(ValidationError):
        schemas.ProjectInitAnalysisCreate(
            attachment_ids=list(range(1, 12)),
            current_draft=[],
        )
```

- [ ] **Step 2: 运行测试确认缺少模型**

Run: `python -m pytest tests/test_project_init_ai_models.py -q`

Working directory: `bowei_ai_dashboard`

Expected: FAIL，提示 `ProjectInitAttachment` 或 `ProjectInitAnalysisRun` 不存在。

- [ ] **Step 3: 增加解析依赖和旧版 Word 运行时**

在 `requirements.txt` 增加：

```text
openpyxl==3.1.5
pypdf==6.1.0
xlrd==2.0.2
```

将 `Dockerfile.backend` 的依赖安装段改为：

```dockerfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends antiword \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt
```

- [ ] **Step 4: 新增 SQLAlchemy 模型**

在 `models.py` 增加：

```python
class ProjectInitAttachment(Base, TimestampMixin):
    __tablename__ = "project_init_attachments"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    storage_key = Column(String(255), nullable=False, unique=True)
    original_name = Column(String(255), nullable=False)
    mime_type = Column(String(120), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    uploaded_by = Column(String(50), nullable=False, index=True)
    uploaded_by_person_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    deleted_by = Column(String(50), default="")


class ProjectInitAnalysisRun(Base, TimestampMixin):
    __tablename__ = "project_init_analysis_runs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    attachment_ids_json = Column(Text, nullable=False, default="[]")
    current_draft_json = Column(Text, nullable=False, default="[]")
    status = Column(String(24), nullable=False, default="queued", index=True)
    stage = Column(String(24), nullable=False, default="reading")
    progress = Column(Integer, nullable=False, default=0)
    result_json = Column(Text, nullable=False, default="{}")
    file_results_json = Column(Text, nullable=False, default="[]")
    error_summary = Column(Text, nullable=False, default="")
    provider = Column(String(30), nullable=False, default="")
    model_name = Column(String(100), nullable=False, default="")
    created_by = Column(String(50), nullable=False, index=True)
    created_by_person_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    applied_at = Column(DateTime, nullable=True)
```

- [ ] **Step 5: 新增请求与结果 Pydantic 类型**

在 `schemas.py` 增加：

```python
class ProjectInitAnalysisCreate(BaseModel):
    attachment_ids: list[int] = Field(min_length=1, max_length=10)
    current_draft: list[ProjectWorkProgressTaskDraft] = Field(default_factory=list)


class ProjectInitAnalysisAction(BaseModel):
    action: Literal["retry", "applied"]
```

并从 `typing` 导入 `Literal`。

- [ ] **Step 6: 创建 Alembic 迁移**

迁移 `revision = "d2e3f4a5b6c7"`、`down_revision = "c1d2e3f4a5b6"`，创建与模型一致的两张表及 `project_id`、`status`、`created_by_person_id`、`deleted_at` 索引；`downgrade()` 先删除分析任务表，再删除附件表。

- [ ] **Step 7: 运行模型和迁移测试**

Run: `python -m pytest tests/test_project_init_ai_models.py tests/test_migration_bootstrap.py -q`

Working directory: `bowei_ai_dashboard`

Expected: PASS。

- [ ] **Step 8: 提交数据契约**

```bash
git add Dockerfile.backend bowei_ai_dashboard/requirements.txt bowei_ai_dashboard/app/models.py bowei_ai_dashboard/app/schemas.py bowei_ai_dashboard/migrations/versions/d2e3f4a5b6c7_add_project_init_ai_tables.py bowei_ai_dashboard/tests/test_project_init_ai_models.py
git commit -m "feat: add project init AI persistence"
```

### Task 2: 实现带来源位置的文件解析服务

**Files:**
- Create: `bowei_ai_dashboard/app/services/project_init_file_parser.py`
- Create: `bowei_ai_dashboard/tests/test_project_init_file_parser.py`

- [ ] **Step 1: 写各文件类型解析失败测试**

```python
def test_parse_txt_preserves_line_range(tmp_path):
    path = tmp_path / "plan.txt"
    path.write_text("重点工作一\n关键任务A\n验收标准", encoding="utf-8")
    chunks = parse_project_init_file(path, "plan.txt")
    assert chunks[0].source_label == "plan.txt · 第 1-3 行"
    assert "关键任务A" in chunks[0].text


def test_parse_docx_preserves_paragraph_range(tmp_path):
    path = tmp_path / "plan.docx"
    document = Document()
    document.add_heading("实施计划", level=1)
    document.add_paragraph("完成需求确认")
    document.save(path)
    chunks = parse_project_init_file(path, "plan.docx")
    assert chunks[0].source_label.startswith("plan.docx · 第")
    assert "完成需求确认" in "\n".join(chunk.text for chunk in chunks)


def test_parse_xlsx_preserves_sheet_and_range(tmp_path):
    path = tmp_path / "schedule.xlsx"
    book = Workbook()
    sheet = book.active
    sheet.title = "实施计划"
    sheet.append(["关键任务", "负责人"])
    sheet.append(["上线准备", "张三"])
    book.save(path)
    chunks = parse_project_init_file(path, "schedule.xlsx")
    assert chunks[0].source_label == "schedule.xlsx · 实施计划!A1:B2"


def test_parse_pdf_preserves_page_number(tmp_path):
    reader = StubPdfReader(["第一页任务", "第二页任务"])
    chunks = parse_pdf(tmp_path / "plan.pdf", "plan.pdf", reader_factory=lambda _: reader)
    assert [chunk.source_label for chunk in chunks] == ["plan.pdf · 第 1 页", "plan.pdf · 第 2 页"]
```

- [ ] **Step 2: 运行解析测试确认模块不存在**

Run: `python -m pytest tests/test_project_init_file_parser.py -q`

Working directory: `bowei_ai_dashboard`

Expected: FAIL，提示 `project_init_file_parser` 不存在。

- [ ] **Step 3: 实现统一片段契约和类型分发**

```python
@dataclass(frozen=True)
class SourceChunk:
    file_name: str
    location: str
    text: str

    @property
    def source_label(self) -> str:
        return f"{self.file_name} · {self.location}"


def parse_project_init_file(path: Path, original_name: str) -> list[SourceChunk]:
    suffix = Path(original_name).suffix.lower()
    parsers = {
        ".pdf": parse_pdf,
        ".doc": parse_doc,
        ".docx": parse_docx,
        ".xls": parse_xls,
        ".xlsx": parse_xlsx,
        ".txt": parse_text,
    }
    parser = parsers.get(suffix)
    if parser is None:
        raise UnsupportedProjectInitFile(f"不支持的文件类型：{suffix or '无扩展名'}")
    return [chunk for chunk in parser(path, original_name) if chunk.text.strip()]
```

- [ ] **Step 4: 实现具体解析器**

PDF 每页一个片段；DOCX 每 20 个段落一个片段；XLS/XLSX 每个非空工作表一个片段并计算实际单元格范围；TXT 依次尝试 `utf-8-sig` 和 `gb18030`，每 80 行一个片段。旧版 DOC 使用参数数组调用 `antiword -w 0 <path>`，超时 30 秒，失败时抛出包含文件名的 `ProjectInitFileParseError`，不得通过 shell 拼接命令。

- [ ] **Step 5: 增加损坏文件和旧版 DOC 测试**

```python
def test_parse_doc_uses_safe_argument_list(monkeypatch, tmp_path):
    captured = {}
    def fake_run(args, **kwargs):
        captured["args"] = args
        return CompletedProcess(args, 0, stdout="旧版方案内容", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    chunks = parse_doc(tmp_path / "unsafe name.doc", "unsafe name.doc")
    assert captured["args"] == ["antiword", "-w", "0", str(tmp_path / "unsafe name.doc")]
    assert chunks[0].text == "旧版方案内容"


def test_corrupt_file_raises_normalized_error(tmp_path):
    path = tmp_path / "broken.xlsx"
    path.write_bytes(b"not a workbook")
    with pytest.raises(ProjectInitFileParseError, match="broken.xlsx"):
        parse_project_init_file(path, path.name)
```

- [ ] **Step 6: 运行解析服务测试**

Run: `python -m pytest tests/test_project_init_file_parser.py -q`

Working directory: `bowei_ai_dashboard`

Expected: PASS。

- [ ] **Step 7: 提交解析服务**

```bash
git add bowei_ai_dashboard/app/services/project_init_file_parser.py bowei_ai_dashboard/tests/test_project_init_file_parser.py
git commit -m "feat: parse project init source files"
```

### Task 3: 实现安全的立项附件接口

**Files:**
- Create: `bowei_ai_dashboard/app/routers/project_init_ai.py`
- Modify: `bowei_ai_dashboard/app/main.py`
- Create: `bowei_ai_dashboard/tests/test_project_init_attachments.py`

- [ ] **Step 1: 写上传、权限和生命周期失败测试**

使用 `TestClient` 建立 `dispatched` 项目、负责人、成员和外部人员，断言：负责人上传 PDF 返回 201；普通成员和外部人员返回 403；`pending_review` 项目返回 409；扩展名与文件头不匹配返回 422；单文件超过 25 MB 返回 413 或 422；下载响应包含 `X-Content-Type-Options: nosniff`；删除为软删除且列表不再返回。

```python
uploaded = client.post(
    "/api/projects/1/init-attachments",
    files={"file": ("plan.pdf", b"%PDF-1.7\n", "application/pdf")},
    cookies=cookies("owner"),
)
assert uploaded.status_code == 201
attachment_id = uploaded.json()["id"]
assert client.get("/api/projects/1/init-attachments", cookies=cookies("owner")).json()[0]["id"] == attachment_id
download = client.get(f"/api/projects/1/init-attachments/{attachment_id}/download", cookies=cookies("owner"))
assert download.headers["x-content-type-options"] == "nosniff"
```

- [ ] **Step 2: 运行接口测试确认路由不存在**

Run: `python -m pytest tests/test_project_init_attachments.py -q`

Working directory: `bowei_ai_dashboard`

Expected: FAIL，上传接口返回 404。

- [ ] **Step 3: 实现权限和可编辑状态守卫**

```python
_EDITABLE_LIFECYCLES = {"dispatched", "returned"}


def _require_init_editable(project_id: int, current_user: str, db: Session) -> models.Project:
    require_project_owner_or_admin(current_user, project_id, db)
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    lifecycle = PL.normalize(project.status, "draft")
    if lifecycle not in _EDITABLE_LIFECYCLES:
        raise HTTPException(409, "当前项目状态不可修改立项资料")
    return project
```

- [ ] **Step 4: 实现上传与文件签名校验**

允许 `.pdf/.doc/.docx/.xls/.xlsx/.txt`；限制 25 MB；文件名使用 `Path(file.filename).name`；存储根目录为 `PROJECT_INIT_ATTACHMENT_ROOT`；临时文件写完后校验：PDF 以 `%PDF-` 开头，DOC/XLS 以 OLE 签名开头，DOCX/XLSX 是 ZIP 且包含对应的 `word/document.xml` 或 `xl/workbook.xml`，TXT 不含 NUL 字节。数据库提交失败时删除临时文件和目标文件。

- [ ] **Step 5: 实现列表、下载和软删除**

所有接口同时校验 URL 中的 `project_id` 与附件的 `project_id`；下载路径经 `resolve()` 后必须位于存储根目录下；删除写入 `deleted_at` 和 `deleted_by`，提交后尝试删除文件，失败则在后续附件请求中重试清理。

- [ ] **Step 6: 注册路由并运行测试**

在 `main.py` 导入 `project_init_ai` 并调用：

```python
app.include_router(project_init_ai.router)
```

Run: `python -m pytest tests/test_project_init_attachments.py tests/test_production_runtime_security.py -q`

Working directory: `bowei_ai_dashboard`

Expected: PASS。

- [ ] **Step 7: 提交附件接口**

```bash
git add bowei_ai_dashboard/app/routers/project_init_ai.py bowei_ai_dashboard/app/main.py bowei_ai_dashboard/tests/test_project_init_attachments.py
git commit -m "feat: add project init attachment API"
```

### Task 4: 实现 AI 草稿提取、人员匹配和重复分类

**Files:**
- Create: `bowei_ai_dashboard/app/services/project_init_ai_agent.py`
- Create: `bowei_ai_dashboard/tests/test_project_init_ai_agent.py`

- [ ] **Step 1: 写结构化输出和确定性匹配失败测试**

```python
def test_build_draft_matches_only_unique_active_people():
    people = [
        PersonCandidate(id=1, name="张三", is_active=True),
        PersonCandidate(id=2, name="李四", is_active=True),
        PersonCandidate(id=3, name="李四", is_active=True),
        PersonCandidate(id=4, name="王五", is_active=False),
    ]
    result = normalize_agent_result(raw_result(), people, current_draft=[])
    key_task = result.tasks[0].subtasks[0]
    assert key_task.assignee_id == 1
    assert key_task.helper_ids == []
    assert {warning.code for warning in key_task.warnings} == {"ambiguous_person", "inactive_person"}


def test_duplicate_task_requires_human_decision():
    existing = [{"title": "实施交付", "subtasks": [{"title": "完成系统上线"}]}]
    result = normalize_agent_result(raw_result(subtask_title="完成系统上线"), [], existing)
    assert result.tasks[0].merge_status == "possible_duplicate"
    assert result.tasks[0].subtasks[0].merge_status == "possible_duplicate"
```

- [ ] **Step 2: 运行测试确认 Agent 模块不存在**

Run: `python -m pytest tests/test_project_init_ai_agent.py -q`

Working directory: `bowei_ai_dashboard`

Expected: FAIL，提示 `project_init_ai_agent` 不存在。

- [ ] **Step 3: 定义严格结果模型**

```python
class Evidence(BaseModel):
    attachment_id: int
    file_name: str
    location: str
    excerpt: str = Field(max_length=300)


class AgentSubTask(BaseModel):
    title: str = Field(max_length=200)
    assignee_name: str = Field(default="", max_length=50)
    helper_names: list[str] = Field(default_factory=list, max_length=20)
    plan_start: str = Field(default="", max_length=50)
    plan_end: str = Field(default="", max_length=50)
    evaluation_standard: str = Field(default="", max_length=1000)
    confidence: float = Field(ge=0, le=1)
    evidence: list[Evidence] = Field(default_factory=list, max_length=10)


class AgentTask(BaseModel):
    title: str = Field(max_length=200)
    description: str = Field(default="", max_length=2000)
    plan_start: str = Field(default="", max_length=50)
    plan_end: str = Field(default="", max_length=50)
    subtasks: list[AgentSubTask] = Field(min_length=1, max_length=100)
```

- [ ] **Step 4: 实现模型调用**

使用 `resolve_provider()` 选择启用模型，使用 `get_provider_config()` 记录 provider 和 model。Anthropic 和 OpenAI-compatible 调用均设置 90 秒超时，提示词要求只输出 JSON，结构为 `{"tasks": [...]}`，明确“不得发明人员、日期或人员 ID；自然语言日期保留原文；每个关键任务必须附来源”。解析响应时截取 JSON 对象并交给 Pydantic 校验；无任务时抛出 `ProjectInitAiEmptyResult`。

- [ ] **Step 5: 实现分批提取和合并**

每批最多 40,000 字符并保持片段边界；每批单独提取，最后将候选任务送入一次合并提示。完全相同的归一化任务标题在本地先去重并合并 evidence。调用函数接收可注入的 `llm_call`，测试中禁止真实网络访问。

- [ ] **Step 6: 实现人员和重复匹配**

姓名匹配只接受 `strip().casefold()` 后唯一精确匹配且 `is_active=True` 的人员；同名、未找到和停用分别产生 `ambiguous_person`、`person_not_found`、`inactive_person`。重复判断对归一化后的标题先做精确比较，再用 `difflib.SequenceMatcher(...).ratio() >= 0.86` 标记 `possible_duplicate`；不自动覆盖现有字段。

- [ ] **Step 7: 运行 Agent 单元测试**

Run: `python -m pytest tests/test_project_init_ai_agent.py -q`

Working directory: `bowei_ai_dashboard`

Expected: PASS，且测试日志中无外部模型调用。

- [ ] **Step 8: 提交 AI 服务**

```bash
git add bowei_ai_dashboard/app/services/project_init_ai_agent.py bowei_ai_dashboard/tests/test_project_init_ai_agent.py
git commit -m "feat: generate project init drafts with AI"
```

### Task 5: 实现持久化异步分析任务和轮询接口

**Files:**
- Modify: `bowei_ai_dashboard/app/routers/project_init_ai.py`
- Create: `bowei_ai_dashboard/app/services/project_init_analysis.py`
- Create: `bowei_ai_dashboard/tests/test_project_init_analysis_flow.py`

- [ ] **Step 1: 写创建、部分失败、重试和无副作用测试**

```python
def test_analysis_run_is_draft_only_and_records_partial_failure(db, seeded_project, monkeypatch):
    run = create_analysis_run(
        project_id=1,
        attachment_ids=[1, 2],
        current_draft=[],
        current_user="owner",
        db=db,
    )
    monkeypatch.setattr(parser, "parse_project_init_file", fake_one_success_one_failure)
    monkeypatch.setattr(agent, "generate_project_init_draft", fake_agent_result)
    process_analysis_run(run.id)
    db.expire_all()
    saved = db.get(models.ProjectInitAnalysisRun, run.id)
    assert saved.status == "partial_failed"
    assert saved.stage == "completed"
    assert saved.progress == 100
    assert db.query(models.Task).filter_by(project_id=1).count() == 0
    assert db.get(models.Project, 1).status == "dispatched"
```

接口测试同时断言：附件超过 10 个返回 422；总大小超过 100 MB 返回 422；跨项目附件返回 422；`GET latest` 恢复最近结果；`retry` 创建新 run 而不是覆盖旧审计记录；`applied` 只写 `applied_at`。

- [ ] **Step 2: 运行流程测试确认失败**

Run: `python -m pytest tests/test_project_init_analysis_flow.py -q`

Working directory: `bowei_ai_dashboard`

Expected: FAIL，提示分析服务或接口不存在。

- [ ] **Step 3: 实现分析 worker**

```python
def process_analysis_run(run_id: int) -> None:
    db = SessionLocal()
    try:
        run = db.get(models.ProjectInitAnalysisRun, run_id)
        if run is None or run.status != "queued":
            return
        _set_run_state(db, run, status="processing", stage="reading", progress=10)
        parsed, file_results = _parse_run_files(run, db)
        if not parsed:
            _fail_run(db, run, "没有可供分析的文件内容", file_results)
            return
        _set_run_state(db, run, status="processing", stage="extracting", progress=45)
        result, provider, model_name = _generate_run_result(run, parsed, db)
        _complete_run(db, run, result, file_results, provider, model_name)
    except Exception as exc:
        db.rollback()
        _persist_worker_failure(run_id, normalize_analysis_error(exc))
    finally:
        db.close()
```

每次阶段更新立即提交，worker 日志仅记录 run ID、状态、耗时和错误类型，不记录附件正文。

- [ ] **Step 4: 实现创建和查询接口**

`POST /api/projects/{project_id}/init-analysis-runs` 使用 `BackgroundTasks.add_task(process_analysis_run, run.id)`；创建前锁定项目，验证 1–10 个未删除且属于当前项目的附件，总大小不超过 100 MB，并保存 `current_draft_json` 快照。查询接口仅返回已序列化状态、逐文件结果和结构化结果，不返回服务器存储路径。

- [ ] **Step 5: 实现恢复、重试和应用审计**

`GET .../latest` 返回最近 run 或 404；读取时若 `processing` 且 `updated_at` 超过 30 分钟，原子标记为 `failed` 和“分析进程中断，可重新分析”。`POST .../{run_id}/retry` 复制附件和当前草稿快照创建新 run；`POST .../{run_id}/applied` 仅允许 completed/partial_failed 状态并写 `applied_at=utc_now()`。

- [ ] **Step 6: 运行异步流程测试**

Run: `python -m pytest tests/test_project_init_analysis_flow.py tests/test_project_init_attachments.py -q`

Working directory: `bowei_ai_dashboard`

Expected: PASS。

- [ ] **Step 7: 提交异步分析流程**

```bash
git add bowei_ai_dashboard/app/routers/project_init_ai.py bowei_ai_dashboard/app/services/project_init_analysis.py bowei_ai_dashboard/tests/test_project_init_analysis_flow.py
git commit -m "feat: run project init analysis asynchronously"
```

### Task 6: 建立前端 API、上传和轮询契约

**Files:**
- Create: `frontend/src/api/projectInitAi.ts`
- Create: `bowei_ai_dashboard/tests/test_project_init_ai_frontend.py`

- [ ] **Step 1: 写前端 API 结构失败测试**

```python
def test_project_init_ai_api_contains_upload_poll_and_audit_contracts():
    source = _frontend_source("api/projectInitAi.ts")
    for expected in [
        "export type ProjectInitAttachment",
        "export type ProjectInitAnalysisRun",
        "uploadProjectInitAttachment",
        "fetchProjectInitAttachments",
        "createProjectInitAnalysisRun",
        "fetchProjectInitAnalysisRun",
        "fetchLatestProjectInitAnalysisRun",
        "retryProjectInitAnalysisRun",
        "markProjectInitAnalysisApplied",
        "xhr.upload.onprogress",
    ]:
        assert expected in source
```

- [ ] **Step 2: 运行结构测试确认文件不存在**

Run: `python -m pytest bowei_ai_dashboard/tests/test_project_init_ai_frontend.py -q`

Working directory: repository root

Expected: FAIL，提示 `frontend/src/api/projectInitAi.ts` 不存在。

- [ ] **Step 3: 定义前端类型**

```ts
export type AnalysisStatus = 'queued' | 'processing' | 'completed' | 'partial_failed' | 'failed'
export type AnalysisStage = 'reading' | 'extracting' | 'matching' | 'completed'

export type ProjectInitAnalysisRun = {
  id: number
  project_id: number
  status: AnalysisStatus
  stage: AnalysisStage
  progress: number
  error_summary: string
  file_results: Array<{ attachment_id: number; file_name: string; status: 'completed' | 'failed'; error: string }>
  result: ProjectInitAiResult | null
  applied_at?: string | null
}
```

`ProjectInitAiResult` 的 task/subtask 字段与后端结果逐一对应，包括 `assignee_id`、`helper_ids`、`merge_status`、`warnings`、`confidence` 和 `evidence`。

- [ ] **Step 4: 实现 API 方法**

上传使用 XHR 和 `withCredentials=true`，支持进度和 `AbortSignal`；其他方法使用现有 `apiGet/apiPost/apiDelete`。创建分析请求发送 `{ attachment_ids, current_draft }`；下载 URL 使用 `/api/projects/${projectId}/init-attachments/${attachmentId}/download`。

- [ ] **Step 5: 运行结构测试与构建**

Run: `python -m pytest bowei_ai_dashboard/tests/test_project_init_ai_frontend.py -q`

Working directory: repository root

Expected: PASS。

Run: `npm run build`

Working directory: `frontend`

Expected: TypeScript 编译和 Vite 构建成功。

- [ ] **Step 6: 提交前端 API**

```bash
git add frontend/src/api/projectInitAi.ts bowei_ai_dashboard/tests/test_project_init_ai_frontend.py
git commit -m "feat: add project init AI frontend API"
```

### Task 7: 构建立项 AI 上传、进度和结果预览面板

**Files:**
- Create: `frontend/src/features/settings/OwnerSubmitAiPanel.tsx`
- Modify: `bowei_ai_dashboard/tests/test_project_init_ai_frontend.py`

- [ ] **Step 1: 写四状态 UI 失败测试**

```python
def test_owner_submit_ai_panel_exposes_upload_progress_preview_and_apply_states():
    source = _frontend_source("features/settings/OwnerSubmitAiPanel.tsx")
    for expected in [
        "AI 从文件生成",
        "读取文件",
        "提取结构",
        "匹配人员",
        "生成草稿",
        "疑似重复",
        "待确认",
        "应用到推进表",
        "setInterval",
        "1500",
        'accept=".pdf,.doc,.docx,.xls,.xlsx,.txt"',
    ]:
        assert expected in source
```

- [ ] **Step 2: 运行 UI 结构测试确认失败**

Run: `python -m pytest bowei_ai_dashboard/tests/test_project_init_ai_frontend.py -q`

Working directory: repository root

Expected: FAIL，提示面板文件不存在。

- [ ] **Step 3: 实现多文件上传队列**

组件 props 为 `projectId`、`currentDraft`、`onApply`。本地队列保存 `file/progress/uploading/error/attachment`；选择时拒绝超过 10 个、单文件超过 25 MB 或合计超过 100 MB，并显示文本错误。上传失败项提供“重试”和“移除”，成功附件提供受控下载和删除。

- [ ] **Step 4: 实现分析启动和轮询**

点击“开始分析”时发送成功附件 ID 和当前草稿；状态为 queued/processing 时每 1500 ms 查询一次，组件卸载或 run 终态时清除定时器。恢复时先请求附件列表和 latest run，404 视为尚无结果，不显示错误。

- [ ] **Step 5: 实现预览决策状态**

每个候选任务保存 `selected` 和 `decision: 'new' | 'ignore' | 'supplement'`；非重复项默认 `new`，疑似重复项不设置默认决定并禁用总“应用”按钮。未匹配人员显示 warning，低于 0.65 的置信度显示“低置信度”；来源链接显示文件名和位置，点击通过受控下载接口打开附件。

- [ ] **Step 6: 实现部分失败、重试和应用回调**

`partial_failed` 同时显示成功结果和失败文件；`failed` 显示错误及“重新分析”。点击应用时只把选中且已决策的候选传给 `onApply`，成功后调用 `markProjectInitAnalysisApplied`，但标记审计失败不能回滚已合并的本地草稿，只显示 toast。

- [ ] **Step 7: 运行 UI 结构测试与构建**

Run: `python -m pytest bowei_ai_dashboard/tests/test_project_init_ai_frontend.py -q`

Working directory: repository root

Expected: PASS。

Run: `npm run build`

Working directory: `frontend`

Expected: PASS。

- [ ] **Step 8: 提交 AI 面板**

```bash
git add frontend/src/features/settings/OwnerSubmitAiPanel.tsx bowei_ai_dashboard/tests/test_project_init_ai_frontend.py
git commit -m "feat: add owner submit AI draft panel"
```

### Task 8: 将 AI 草稿安全合并到现有推进表

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Create: `frontend/src/features/settings/ownerSubmitDraft.ts`
- Create: `frontend/src/features/settings/ownerSubmitDraft.test.ts`
- Modify: `frontend/src/features/settings/OwnerSubmitModal.tsx`
- Modify: `bowei_ai_dashboard/tests/test_project_init_ai_frontend.py`
- Modify: `bowei_ai_dashboard/tests/test_project_init_work_progress_frontend.py`
- Modify: `bowei_ai_dashboard/tests/test_owner_submit_modal_semantics_frontend.py`

- [ ] **Step 1: 安装并配置前端单元测试**

Run: `npm install --save-dev vitest@^3.2.4`

Working directory: `frontend`

在 `package.json` 的 scripts 增加：

```json
"test": "vitest run"
```

- [ ] **Step 2: 写非覆盖合并失败测试**

结构测试要求 `OwnerSubmitModal` 渲染 `OwnerSubmitAiPanel`，传入 `currentDraft={toPayloadDraft(draftTasks)}` 并通过 `applyAiDraft` 更新本地任务。`ownerSubmitDraft.test.ts` 使用 Vitest 验证：现有任务保持不变；new 决策追加任务；supplement 只填充空字段；负责人 ID 和协助人 ID 映射到本地草稿；负责人从协助人中移除。

```ts
import { describe, expect, it } from 'vitest'
import { mergeAiDraft, type AiDraftDecision, type LocalTaskDraft } from './ownerSubmitDraft'
import type { Person } from '../../types'

const people: Person[] = [
  { id: 5, name: '负责人', is_active: true },
  { id: 6, name: '协助人甲', is_active: true },
  { id: 7, name: '协助人乙', is_active: true },
]

function manualTask(overrides: Partial<LocalTaskDraft> = {}): LocalTaskDraft {
  return {
    title: '实施交付', description: '', owner: '', helper: '', plan_start: '', plan_end: '',
    subtasks: [{ title: '已有任务', evaluation_standard: '', assignee: '', assigneeId: '',
      helper: '', helperIds: [], plan_start: '', plan_end: '' }],
    ...overrides,
  }
}

function decision(action: 'new' | 'supplement', overrides: Record<string, unknown> = {}): AiDraftDecision {
  return {
    action,
    targetTaskIndex: action === 'supplement' ? 0 : undefined,
    task: {
      title: action === 'new' ? 'AI 新重点工作' : '实施交付',
      description: '', plan_start: '', plan_end: '', merge_status: action === 'new' ? 'new' : 'possible_duplicate',
      confidence: 0.9, evidence: [], warnings: [],
      subtasks: [{ title: 'AI 关键任务', evaluation_standard: '', assignee: '负责人', assignee_id: 5,
        helper: '负责人、协助人甲、协助人乙', helper_ids: [5, 6, 7], plan_start: '', plan_end: '',
        merge_status: 'new', confidence: 0.9, evidence: [], warnings: [] }],
      ...overrides,
    },
  }
}

describe('mergeAiDraft', () => {
  it('preserves manual content and appends confirmed AI tasks', () => {
    const existing = [manualTask({ description: '人工已填写内容' })]
    const merged = mergeAiDraft(existing, [decision('new')], people)

    expect(merged[0].description).toBe('人工已填写内容')
    expect(merged[1].subtasks[0].assigneeId).toBe(5)
    expect(merged[1].subtasks[0].helperIds).toEqual([6, 7])
  })

  it('supplements only empty fields', () => {
    const merged = mergeAiDraft(
      [manualTask({ description: '人工描述', plan_start: '' })],
      [decision('supplement', { description: 'AI 描述', plan_start: '2026-09-01' })],
      people,
    )
    expect(merged[0].description).toBe('人工描述')
    expect(merged[0].plan_start).toBe('2026-09-01')
  })
})
```

- [ ] **Step 3: 运行测试确认合并模块不存在**

Run: `python -m pytest bowei_ai_dashboard/tests/test_project_init_ai_frontend.py bowei_ai_dashboard/tests/test_project_init_work_progress_frontend.py -q`

Working directory: repository root

Expected: FAIL，提示 `ownerSubmitDraft.ts` 或集成标记不存在。

Run: `npm test -- ownerSubmitDraft.test.ts`

Working directory: `frontend`

Expected: FAIL，提示 `ownerSubmitDraft` 模块不存在。

- [ ] **Step 4: 抽取共享草稿类型和转换函数**

将 `LocalTaskDraft`、`LocalSubTaskDraft`、空草稿工厂、`toPayloadDraft` 和 AI 候选转本地草稿函数移到 `ownerSubmitDraft.ts`。保持字段名 `assigneeId/helperIds` 与现有请求映射不变；`OwnerSubmitModal` 从该模块导入并继续在提交前调用 `toPayloadDraft`。

同时导出预览面板和合并函数共用的决定类型：

```ts
export type AiDraftDecision = {
  action: 'new' | 'ignore' | 'supplement'
  task: ProjectInitAiTask
  targetTaskIndex?: number
}
```

- [ ] **Step 5: 实现非覆盖合并**

```ts
export function mergeAiDraft(
  existing: LocalTaskDraft[],
  decisions: AiDraftDecision[],
  people: Person[],
): LocalTaskDraft[] {
  return decisions.reduce((tasks, decision) => {
    if (decision.action === 'ignore') return tasks
    if (decision.action === 'supplement') return supplementExistingTask(tasks, decision, people)
    return [...tasks, aiTaskToLocalDraft(decision.task, people)]
  }, existing.map(cloneTaskDraft))
}
```

`supplementExistingTask` 只在目标字段为空时写入；数组字段仅在原数组为空时补充；找不到目标任务时保持原值并抛出可显示的 `AiDraftMergeError`。`aiTaskToLocalDraft` 只接受仍在 `people` 中且启用的 ID，并从 helperIds 移除 assigneeId。

- [ ] **Step 6: 在弹窗中挂载 AI 面板**

将面板放在右侧“工作推进方案”标题下方；传入当前项目、人员列表和当前草稿。`onApply` 使用函数式 `setDraftTasks(prev => mergeAiDraft(prev, decisions, people))`，显示“已添加 X 条重点工作、Y 条关键任务”；AI 分析期间不禁用手工编辑或关闭弹窗。

- [ ] **Step 7: 更新既有结构测试**

将原来要求 `OwnerSubmitModal.tsx` 内部声明 `function toPayloadDraft` 的断言改为检查导入和调用；继续断言 `owner-submit` payload 包含 `assignee_id/helper_ids`，语义测试继续禁止第四层结构和越界术语。

- [ ] **Step 8: 运行所有立项前端测试与构建**

Run: `python -m pytest bowei_ai_dashboard/tests/test_project_init_ai_frontend.py bowei_ai_dashboard/tests/test_project_init_work_progress_frontend.py bowei_ai_dashboard/tests/test_owner_submit_modal_semantics_frontend.py bowei_ai_dashboard/tests/test_owner_submit_modal_visual_frontend.py bowei_ai_dashboard/tests/test_owner_submit_modal_final_workbench_frontend.py -q`

Working directory: repository root

Expected: PASS。

Run: `npm test -- ownerSubmitDraft.test.ts`

Working directory: `frontend`

Expected: PASS。

Run: `npm run build`

Working directory: `frontend`

Expected: PASS。

- [ ] **Step 9: 提交弹窗集成**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/features/settings/ownerSubmitDraft.ts frontend/src/features/settings/ownerSubmitDraft.test.ts frontend/src/features/settings/OwnerSubmitModal.tsx bowei_ai_dashboard/tests/test_project_init_ai_frontend.py bowei_ai_dashboard/tests/test_project_init_work_progress_frontend.py bowei_ai_dashboard/tests/test_owner_submit_modal_semantics_frontend.py
git commit -m "feat: merge AI drafts into owner submission"
```

### Task 9: 完成安全回归和真实流程验收

**Files:**
- Modify: `bowei_ai_dashboard/tests/test_project_init_analysis_flow.py`
- Modify: `bowei_ai_dashboard/tests/test_project_init_ai_frontend.py`
- Verify: `bowei_ai_dashboard/app/routers/project_init_ai.py`
- Verify: `frontend/src/features/settings/OwnerSubmitAiPanel.tsx`

- [ ] **Step 1: 增加跨项目与项目状态变化竞态测试**

创建 run 后、worker 执行前将项目状态改为 `pending_review`，断言 worker 将 run 标记为 failed 且不调用模型；把附件 ID 替换成另一项目附件，断言失败且不读取文件。下载、删除、retry、applied 接口均使用 URL 项目 ID 与资源项目 ID 双重校验。

- [ ] **Step 2: 增加上传后恢复与轮询终止结构测试**

断言面板加载时调用 `fetchProjectInitAttachments` 和 `fetchLatestProjectInitAnalysisRun`；终态 completed/partial_failed/failed 清除 interval；组件卸载调用 `clearInterval` 并中止仍在上传的 XHR。

- [ ] **Step 3: 运行完整专项测试**

Run: `python -m pytest tests/test_project_init_ai_models.py tests/test_project_init_file_parser.py tests/test_project_init_attachments.py tests/test_project_init_ai_agent.py tests/test_project_init_analysis_flow.py tests/test_project_init_work_progress_draft.py -q`

Working directory: `bowei_ai_dashboard`

Expected: PASS。

Run: `python -m pytest bowei_ai_dashboard/tests/test_project_init_ai_frontend.py bowei_ai_dashboard/tests/test_project_init_work_progress_frontend.py bowei_ai_dashboard/tests/test_owner_submit_modal_semantics_frontend.py bowei_ai_dashboard/tests/test_owner_submit_modal_visual_frontend.py bowei_ai_dashboard/tests/test_owner_submit_modal_final_workbench_frontend.py -q`

Working directory: repository root

Expected: PASS。

- [ ] **Step 4: 验证迁移和生产构建**

Run: `python -m alembic upgrade head`

Working directory: `bowei_ai_dashboard`

Expected: 升级到 `d2e3f4a5b6c7`，无错误。

Run: `npm run build`

Working directory: `frontend`

Expected: TypeScript 编译和 Vite 构建成功。

Run: `docker build -f Dockerfile.backend -t bowei-ai-backend:init-ai .`

Working directory: repository root

Expected: 依赖安装、antiword 安装和后端镜像构建成功。

- [ ] **Step 5: 执行浏览器端到端验收**

在一个 `dispatched` 测试项目中上传包含段落和表格的 PDF、DOCX、XLSX：确认部分文件失败不影响成功结果；处理一项疑似重复任务和一项未匹配人员；应用草稿后确认原有手工字段未被覆盖；选择有效负责人并提交；验证项目进入 `pending_review`、新人员成为项目 member、附件仍可下载、分析来源可追溯。

- [ ] **Step 6: 提交最终回归测试**

```bash
git add bowei_ai_dashboard/tests/test_project_init_analysis_flow.py bowei_ai_dashboard/tests/test_project_init_ai_frontend.py
git commit -m "test: cover project init AI recovery and security"
```

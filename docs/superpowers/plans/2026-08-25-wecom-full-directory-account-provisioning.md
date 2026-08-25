# 企业微信全员通讯录与账号自动创建 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** 从企业微信递归同步全员的部门、岗位和身份，并为缺失账号的成员自动创建可登录的普通成员账号。

**Architecture:** 保留已有“预览后按人确认”的同步接口，新增独立的管理员批量导入接口和纯后端 provisioning helper，避免改变手工同步语义。批量路径以企微 userid、唯一姓名、新建人员、冲突跳过的顺序决策；前端在现有同步弹窗提供一键入口和统计结果。

**Tech Stack:** FastAPI、SQLAlchemy、Pydantic、pytest、React、TypeScript、Node test runner。

---

## File structure

- bowei_ai_dashboard/app/routers/accounts.py — 批量导入 helper、用户名生成器和管理员路由；复用已有部门路径和企微身份写入代码。
- bowei_ai_dashboard/tests/test_wecom_identity_sync.py — 内存 SQLite 的自动关联、创建账号、部门归属和冲突回归测试。
- frontend/src/api/accounts.ts — 批量导入 API 类型与请求函数。
- frontend/src/features/settings/WecomIdentitySyncModal.tsx — 一键同步入口、运行状态和冲突结果。
- frontend/tests/wecomIdentitySync.test.mjs — 前端文件契约测试。

### Task 1: 后端自动导入核心逻辑

**Files:**
- Modify: bowei_ai_dashboard/app/routers/accounts.py:71-260
- Modify: bowei_ai_dashboard/tests/test_wecom_identity_sync.py

- [ ] **Step 1: 写入会失败的后端测试。**

在测试文件导入 ROLE_NORMAL 和 provision_wecom_directory_accounts，追加下列完整测试；它覆盖新成员、完整部门路径、缺失账号、按唯一姓名关联、用户名去重和重名跳过。

~~~python
def test_provision_wecom_directory_creates_accounts_and_skips_ambiguous_names():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add_all([
            models.Person(name="王伟", system_role=ROLE_NORMAL),
            models.Person(name="张三"),
            models.Person(name="张三"),
            models.Account(username="lihua", password_hash="existing", status="active"),
        ])
        db.commit()
        result = provision_wecom_directory_accounts(db, [
            {"userid": "lihua", "name": "李华", "department_path": "博维 / 产品部", "position": "产品经理"},
            {"userid": "wangwei", "name": "王伟", "department_path": "博维 / 研发部", "position": "工程师"},
            {"userid": "zhangsan", "name": "张三", "department_path": "博维 / 销售部", "position": "销售"},
        ])
        new_person = db.query(models.Person).filter_by(wecom_userid="lihua").one()
        linked_person = db.query(models.Person).filter_by(wecom_userid="wangwei").one()
        new_account = db.query(models.Account).filter_by(person_id=new_person.id).one()
        linked_account = db.query(models.Account).filter_by(person_id=linked_person.id).one()
        assert (new_person.department, new_person.wecom_department, new_person.position_title) == ("博维 / 产品部", "博维 / 产品部", "产品经理")
        assert (new_account.username, new_account.password_hash, new_account.wecom_userid) == ("lihua-2", "123456", "lihua")
        assert new_account.status == "active"
        assert new_account.must_change_password is False
        assert linked_account.username == "wangwei"
        assert result == {
            "updated": 2, "linked_by_name": 1, "created_people": 1, "created_accounts": 2,
            "conflicts": [{"userid": "zhangsan", "name": "张三", "reason": "ambiguous_name"}],
        }
    finally:
        db.close()
~~~

- [ ] **Step 2: 运行测试确认失败。**

Run: cd bowei_ai_dashboard && .\.venv\Scripts\python.exe -m pytest -q tests/test_wecom_identity_sync.py -k provision

Expected: FAIL，无法导入 provision_wecom_directory_accounts。

- [ ] **Step 3: 实现用户名生成和批量 provision helper。**

在 sync_wecom_identity_records 前添加以下函数。先检查现有账户绑定冲突，再调用 apply_wecom_identity_record，以保证冲突人员的部门和岗位不会被意外写入。person_id 为空的账户绑定标记为 orphaned_account_binding，不能擅自关联给其他人员。

~~~python
_INITIAL_WECOM_PASSWORD = "123456"

def _next_wecom_username(db: Session, userid: str) -> str:
    base = (userid.strip() or "wecom-user")[:50]
    candidate, suffix = base, 2
    while db.query(models.Account.id).filter(models.Account.username == candidate).first():
        ending = f"-{suffix}"
        candidate = f"{base[:50 - len(ending)]}{ending}"
        suffix += 1
    return candidate

def provision_wecom_directory_accounts(db: Session, records: list[dict]) -> dict:
    people = db.query(models.Person).all()
    accounts = db.query(models.Account).all()
    by_userid = {p.wecom_userid.strip(): p for p in people if p.wecom_userid}
    by_name, accounts_by_person = {}, {}
    account_by_userid = {a.wecom_userid.strip(): a for a in accounts if a.wecom_userid}
    for person in people:
        if person.name.strip():
            by_name.setdefault(person.name.strip(), []).append(person)
    for account in accounts:
        if account.person_id:
            accounts_by_person.setdefault(account.person_id, []).append(account)

    result = {"updated": 0, "linked_by_name": 0, "created_people": 0, "created_accounts": 0, "conflicts": []}
    for record in records:
        userid, name = str(record.get("userid") or "").strip(), str(record.get("name") or "").strip()
        if not userid:
            continue
        account_owner = account_by_userid.get(userid)
        if account_owner and not account_owner.person_id:
            result["conflicts"].append({"userid": userid, "name": name, "reason": "orphaned_account_binding"})
            continue
        person = by_userid.get(userid) or (db.get(models.Person, account_owner.person_id) if account_owner else None)
        if person is None:
            matches = by_name.get(name, [])
            if len(matches) > 1:
                result["conflicts"].append({"userid": userid, "name": name, "reason": "ambiguous_name"})
                continue
            if len(matches) == 1:
                person = matches[0]
                result["linked_by_name"] += 1
            else:
                person = models.Person(name=name or userid, system_role=ROLE_NORMAL, is_active=True)
                db.add(person)
                db.flush()
                by_name.setdefault(person.name.strip(), []).append(person)
                result["created_people"] += 1
        if account_owner and account_owner.person_id != person.id:
            result["conflicts"].append({"userid": userid, "name": name, "reason": "userid_bound_to_other_account"})
            continue
        person_accounts = accounts_by_person.get(person.id, [])
        if person.wecom_userid and person.wecom_userid != userid:
            result["conflicts"].append({"userid": userid, "name": name, "reason": "person_bound_to_other_userid"})
            continue
        if any(a.wecom_userid and a.wecom_userid != userid for a in person_accounts):
            result["conflicts"].append({"userid": userid, "name": name, "reason": "account_bound_to_other_userid"})
            continue
        duplicate = db.query(models.Person).filter(models.Person.wecom_userid == userid, models.Person.id != person.id).first()
        if duplicate:
            result["conflicts"].append({"userid": userid, "name": name, "reason": "userid_bound_to_other_person"})
            continue
        apply_wecom_identity_record(person, record)
        by_userid[userid] = person
        if person_accounts:
            for account in person_accounts:
                account.wecom_userid = userid
        else:
            account = models.Account(username=_next_wecom_username(db, userid), password_hash=hash_password(_INITIAL_WECOM_PASSWORD), person_id=person.id, status="active", is_tech_admin=False, must_change_password=False, last_password_changed_at=utc_now(), wecom_userid=userid)
            db.add(account)
            accounts_by_person[person.id] = [account]
            result["created_accounts"] += 1
        result["updated"] += 1
    return result
~~~

- [ ] **Step 4: 运行测试确认通过。**

Run: cd bowei_ai_dashboard && .\.venv\Scripts\python.exe -m pytest -q tests/test_wecom_identity_sync.py -k provision

Expected: PASS，新增测试通过。

- [ ] **Step 5: 提交后端核心逻辑。**

~~~powershell
git add bowei_ai_dashboard/app/routers/accounts.py bowei_ai_dashboard/tests/test_wecom_identity_sync.py
git commit -m "feat: provision accounts from wecom directory"
~~~

### Task 2: 受保护的全员导入 API

**Files:**
- Modify: bowei_ai_dashboard/app/routers/accounts.py:690-740
- Modify: bowei_ai_dashboard/tests/test_wecom_identity_sync.py

- [ ] **Step 1: 写入接口失败测试。**

在测试文件导入 SimpleNamespace 和 app.routers.accounts as accounts_router，追加：

~~~python
def test_provision_wecom_directory_endpoint_reads_children_and_returns_stats(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        monkeypatch.setattr(accounts_router, "_require_admin", lambda current_user, session: None)
        monkeypatch.setattr(accounts_router, "get_settings", lambda: SimpleNamespace(wecom_directory_enabled=True))
        monkeypatch.setattr(accounts_router.wecom, "list_department_user_details", lambda **kwargs: [{"userid": "alice", "name": "Alice", "department": [7], "position": "产品经理"}])
        monkeypatch.setattr(accounts_router.wecom, "list_departments", lambda: [{"id": 1, "name": "博维", "parentid": 0}, {"id": 7, "name": "产品部", "parentid": 1}])
        response = accounts_router.provision_wecom_directory_accounts_endpoint(current_user="admin", db=db)
        assert response["created_people"] == 1
        assert response["created_accounts"] == 1
        assert db.query(models.Person).filter_by(wecom_userid="alice").one().department == "博维 / 产品部"
    finally:
        db.close()
~~~

- [ ] **Step 2: 运行接口测试确认失败。**

Run: cd bowei_ai_dashboard && .\.venv\Scripts\python.exe -m pytest -q tests/test_wecom_identity_sync.py -k endpoint

Expected: FAIL，缺少 provision_wecom_directory_accounts_endpoint。

- [ ] **Step 3: 增加返回模型和管理员路由。**

在请求模型附近加入返回模型，并在已有 POST /wecom-directory/sync 后添加如下路由；仅要求通讯录配置，不依赖扫码登录配置。

~~~python
class WecomDirectoryProvisionResult(BaseModel):
    updated: int
    linked_by_name: int
    created_people: int
    created_accounts: int
    conflicts: list[dict]

@router.post("/wecom-directory/provision-all", response_model=WecomDirectoryProvisionResult)
def provision_wecom_directory_accounts_endpoint(
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _require_admin(current_user, db)
    if not get_settings().wecom_directory_enabled:
        raise HTTPException(503, "wecom_directory_disabled")
    try:
        users = wecom.list_department_user_details(department_id=1, fetch_child=True)
        departments = wecom.list_departments()
    except wecom.WecomError as exc:
        raise HTTPException(502, str(exc)) from exc
    records = _normalize_wecom_directory_records(users, wecom.build_department_paths(departments))
    result = provision_wecom_directory_accounts(db, records)
    crud.log(db, current_user, "provision_wecom_directory_accounts", "people", None, after=result)
    db.commit()
    return result
~~~

- [ ] **Step 4: 运行接口及现有企微回归。**

Run: cd bowei_ai_dashboard && .\.venv\Scripts\python.exe -m pytest -q tests/test_wecom_identity_sync.py tests/test_wecom_login_urls.py tests/test_wecom_silent_auth_url.py tests/test_execution_schedule_wecom.py

Expected: PASS。

- [ ] **Step 5: 提交 API。**

~~~powershell
git add bowei_ai_dashboard/app/routers/accounts.py bowei_ai_dashboard/tests/test_wecom_identity_sync.py
git commit -m "feat: add wecom directory account provisioning api"
~~~

### Task 3: 前端 API 和一键同步入口

**Files:**
- Modify: frontend/src/api/accounts.ts:96-114
- Modify: frontend/src/features/settings/WecomIdentitySyncModal.tsx
- Modify: frontend/tests/wecomIdentitySync.test.mjs

- [ ] **Step 1: 写入前端契约失败测试。**

~~~javascript
test('WeCom modal exposes full-directory account provisioning', () => {
  assert.match(accountsApi, /provisionWecomDirectoryAccounts/)
  assert.match(accountsApi, /wecom-directory\/provision-all/)
  assert.match(modal, /同步全员并创建账号/)
  assert.match(modal, /初始密码为 123456/)
  assert.match(modal, /created_accounts/)
  assert.match(modal, /conflicts/)
})
~~~

- [ ] **Step 2: 运行测试确认失败。**

Run: node --test frontend/tests/wecomIdentitySync.test.mjs

Expected: FAIL，尚无批量导入前端契约。

- [ ] **Step 3: 添加 API 类型和调用函数。**

在 syncWecomDirectory 后增加：

~~~typescript
export type WecomDirectoryProvisionResult = {
  updated: number
  linked_by_name: number
  created_people: number
  created_accounts: number
  conflicts: Array<{ userid: string; name: string; reason: string }>
}

export function provisionWecomDirectoryAccounts(): Promise<WecomDirectoryProvisionResult> {
  return apiPost<WecomDirectoryProvisionResult>('/api/accounts/wecom-directory/provision-all', {})
}
~~~

- [ ] **Step 4: 更新同步弹窗。**

扩展 import、新增 provisionResult 状态，并在 handleSync 旁实现：

~~~tsx
async function handleProvisionAll() {
  setSaving(true)
  try {
    const result = await provisionWecomDirectoryAccounts()
    setProvisionResult(result)
    toast.success('已同步 ' + result.updated + ' 人，创建 ' + result.created_people + ' 名人员和 ' + result.created_accounts + ' 个账号')
    onDone()
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '同步企业微信全员失败')
  } finally {
    setSaving(false)
  }
}
~~~

在弹窗页脚保留原“确认同步”按钮，新增：

~~~tsx
<button type="button" onClick={() => void handleProvisionAll()} disabled={loading || saving} className="px-4 py-1.5 rounded-lg text-xs font-semibold text-white bg-sky-700 disabled:opacity-50">
  {saving ? '同步中…' : '同步全员并创建账号'}
</button>
<span className="text-[11px] text-slate-500">新账号用户名使用企微 ID，初始密码为 123456。</span>
~~~

在表格下方显示 provisionResult 的更新数、按姓名关联数、新建人员数、新建账号数；conflicts 不为空时使用中文展示“需人工处理”以及成员姓名和冲突原因。成功后调用 onDone() 刷新人员和账号列表，但不要关闭弹窗，以便管理员看到冲突结果。

- [ ] **Step 5: 运行前端测试和构建。**

Run: node --test frontend/tests/wecomIdentitySync.test.mjs

Expected: PASS。

Run: cd frontend && npm run build

Expected: TypeScript 和 Vite 构建都以 exit code 0 完成。

- [ ] **Step 6: 提交前端实现。**

~~~powershell
git add frontend/src/api/accounts.ts frontend/src/features/settings/WecomIdentitySyncModal.tsx frontend/tests/wecomIdentitySync.test.mjs
git commit -m "feat: add one-click wecom account provisioning"
~~~

### Task 4: 最终权限与回归审计

**Files:**
- Verify: bowei_ai_dashboard/app/routers/accounts.py
- Verify: bowei_ai_dashboard/tests/test_wecom_identity_sync.py
- Verify: frontend/src/api/accounts.ts
- Verify: frontend/src/features/settings/WecomIdentitySyncModal.tsx

- [ ] **Step 1: 运行后端回归。**

Run: cd bowei_ai_dashboard && .\.venv\Scripts\python.exe -m pytest -q tests/test_wecom_identity_sync.py tests/test_role_boundary.py tests/test_company_ceo_owner_confirmation_permission.py tests/test_execution_schedule_wecom.py

Expected: PASS。

- [ ] **Step 2: 审查权限边界。**

Run: rg -n "ROLE_SUPER_ADMIN|ProjectMember|project_members|is_tech_admin=True|must_change_password=True" bowei_ai_dashboard/app/routers/accounts.py

Expected: 新 provisioning helper 不创建项目成员、不提升管理员权限，并仅创建 is_tech_admin=False 与 must_change_password=False 的普通账号。

- [ ] **Step 3: 审查最终改动。**

Run: git diff HEAD~3 --check; git diff HEAD~3 --stat

Expected: 无空白错误；修改仅涉及计划中的后端、测试、前端文件。

- [ ] **Step 4: 提交验证期间必要的修正。**

~~~powershell
git status --short
git add <only-files-fixed-during-verification>
git commit -m "test: verify wecom directory provisioning"
~~~

## Plan self-review

- **Spec coverage:** Task 1 实现 userid 优先、唯一姓名关联、新人员/账号创建、用户名去重、固定密码、非强制改密、部门路径/岗位同步和冲突跳过；Task 2 实现根部门递归拉取、配置与管理员边界、审计；Task 3 实现一键入口和结果可见；Task 4 回归角色与项目权限不变。
- **Placeholder scan:** 文件路径、函数名、请求路径、测试命令和预期结果均已明确，没有待定项。
- **Type consistency:** 后端 WecomDirectoryProvisionResult、前端 WecomDirectoryProvisionResult 和响应字段一致；前端请求函数和后端路由均为 /api/accounts/wecom-directory/provision-all。

# 企业微信可见部门通讯录同步 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 仅从企业微信应用可见的部门读取成员，供人员绑定、身份同步和账号创建使用，不再请求企业根部门全员。

**Architecture:** 在 `app.services.wecom` 增加共享目录读取函数：先读取应用可见部门，排除根部门后逐部门以非递归方式读取成员，并以 `userid` 去重。`accounts` 路由的四个通讯录入口改为复用这个函数；前端仅修正“全员”措辞，不增加第二套范围配置。

**Tech Stack:** Python 3、FastAPI、pytest、React、TypeScript、Node test runner。

---

### Task 1: 为可见部门读取行为建立回归测试

**Files:**
- Modify: `D:/项目整体备份/mowayspos-next-task/bowei_ai_dashboard/tests/test_wecom_identity_sync.py`

- [ ] **Step 1: 写入失败测试：普通成员列表按每个可见部门请求并去重**

```python
def test_visible_department_members_query_each_non_root_department_without_children(monkeypatch):
    calls = []
    departments = [{"id": 1}, {"id": 2, "name": "咨询部"}, {"id": 3, "name": "商务部"}]
    monkeypatch.setattr(wecom, "list_departments", lambda: departments)

    def fake_list_users(department_id, fetch_child):
        calls.append((department_id, fetch_child))
        return ([{"userid": "alice"}] if department_id == 2 else [{"userid": "alice"}, {"userid": "bob"}])

    monkeypatch.setattr(wecom, "list_department_users", fake_list_users)
    users, returned_departments = wecom.list_visible_department_users()
    assert calls == [(2, False), (3, False)]
    assert [item["userid"] for item in users] == ["alice", "bob"]
    assert returned_departments == departments
```

- [ ] **Step 2: 运行测试，确认它因函数尚不存在而失败**

Run: `pytest tests/test_wecom_identity_sync.py::test_visible_department_members_query_each_non_root_department_without_children -q`，工作目录 `D:/项目整体备份/mowayspos-next-task/bowei_ai_dashboard`。

Expected: FAIL，提示 `module 'app.services.wecom' has no attribute 'list_visible_department_users'`。

- [ ] **Step 3: 写入失败测试：详情读取使用同一部门范围**

```python
def test_visible_department_details_use_detail_endpoint_for_each_visible_department(monkeypatch):
    calls = []
    monkeypatch.setattr(wecom, "list_departments", lambda: [{"id": 1}, {"id": 8}, {"id": 9}])

    def fake_details(department_id, fetch_child):
        calls.append((department_id, fetch_child))
        return [{"userid": f"user-{department_id}"}]

    monkeypatch.setattr(wecom, "list_department_user_details", fake_details)
    users, _ = wecom.list_visible_department_users(details=True)
    assert calls == [(8, False), (9, False)]
    assert [item["userid"] for item in users] == ["user-8", "user-9"]
```

- [ ] **Step 4: 运行第二个测试，确认它同样因函数尚不存在而失败**

Run: `pytest tests/test_wecom_identity_sync.py::test_visible_department_details_use_detail_endpoint_for_each_visible_department -q`，工作目录 `D:/项目整体备份/mowayspos-next-task/bowei_ai_dashboard`。

Expected: FAIL，提示 `module 'app.services.wecom' has no attribute 'list_visible_department_users'`。

### Task 2: 实现共享可见部门目录读取并接入后端入口

**Files:**
- Modify: `D:/项目整体备份/mowayspos-next-task/bowei_ai_dashboard/app/services/wecom.py:147-206`
- Modify: `D:/项目整体备份/mowayspos-next-task/bowei_ai_dashboard/app/routers/accounts.py:665-874`
- Test: `D:/项目整体备份/mowayspos-next-task/bowei_ai_dashboard/tests/test_wecom_identity_sync.py`

- [ ] **Step 1: 在 `wecom.py` 的 `list_departments` 后添加共享函数**

```python
def list_visible_department_users(*, details: bool = False) -> tuple[list[dict], list[dict]]:
    departments = list_departments()
    department_ids, seen_department_ids = [], set()
    for department in departments:
        try:
            department_id = int(department.get("id"))
        except (TypeError, ValueError):
            continue
        if department_id != 1 and department_id not in seen_department_ids:
            seen_department_ids.add(department_id)
            department_ids.append(department_id)
    if not department_ids:
        raise WecomError("wecom no visible departments: 请在企业微信管理后台将至少一个业务部门加入应用可见范围")
    fetch_users = list_department_user_details if details else list_department_users
    users, seen_userids = [], set()
    for department_id in department_ids:
        for user in fetch_users(department_id=department_id, fetch_child=False):
            userid = str(user.get("userid") or "").strip()
            if userid and userid not in seen_userids:
                seen_userids.add(userid)
                users.append(user)
    return users, departments
```

- [ ] **Step 2: 将四个入口替换为共享函数**

`list_wecom_users` 使用 `wecom_users, _ = wecom.list_visible_department_users()`；`preview_wecom_directory`、`sync_wecom_directory`、`provision_wecom_directory_accounts_endpoint` 使用 `users, departments = wecom.list_visible_department_users(details=True)`。删除这四处 `department_id=1, fetch_child=True`，保留管理员校验、异常转换、审计日志、路由与响应形状。

- [ ] **Step 3: 让 `60011` 文案说明真实范围问题**

在 `list_department_users`、`list_department_user_details`、`list_departments` 三处统一使用：

```python
"wecom department permission denied: 应用对所请求部门无查看权限，或该部门不在应用可见范围"
```

- [ ] **Step 4: 运行新增测试并确认转绿**

Run: `pytest tests/test_wecom_identity_sync.py::test_visible_department_members_query_each_non_root_department_without_children tests/test_wecom_identity_sync.py::test_visible_department_details_use_detail_endpoint_for_each_visible_department -q`，工作目录 `D:/项目整体备份/mowayspos-next-task/bowei_ai_dashboard`。

Expected: PASS，2 passed。

- [ ] **Step 5: 运行企业微信身份同步测试文件并提交后端改动**

Run: `pytest tests/test_wecom_identity_sync.py -q`，工作目录 `D:/项目整体备份/mowayspos-next-task/bowei_ai_dashboard`；通过后执行 `git add bowei_ai_dashboard/app/services/wecom.py bowei_ai_dashboard/app/routers/accounts.py bowei_ai_dashboard/tests/test_wecom_identity_sync.py`，再执行 `git commit -m "feat: scope wecom sync to visible departments"`。

Expected: pytest 0 failures；提交仅包含这三个后端文件。

### Task 3: 修正范围文案并验证前端

**Files:**
- Modify: `D:/项目整体备份/mowayspos-next-task/frontend/src/features/settings/WecomIdentitySyncModal.tsx:65-120`
- Modify: `D:/项目整体备份/mowayspos-next-task/frontend/tests/wecomIdentitySync.test.mjs:24-31`

- [ ] **Step 1: 写入失败测试，要求页面不再称为同步企业全员**

```javascript
assert.match(modal, /同步范围内人员并创建账号/)
assert.doesNotMatch(modal, /同步全员并创建账号/)
```

- [ ] **Step 2: 运行测试，确认它因旧文案而失败**

Run: `node --test tests/wecomIdentitySync.test.mjs`，工作目录 `D:/项目整体备份/mowayspos-next-task/frontend`。

Expected: FAIL，提示未找到“同步范围内人员并创建账号”。

- [ ] **Step 3: 替换按钮和成功提示**

```tsx
toast.success(`已同步范围内 ${result.updated} 人，创建 ${result.created_people} 名人员和 ${result.created_accounts} 个账号`)
{saving ? '同步中…' : '同步范围内人员并创建账号'}
```

- [ ] **Step 4: 重新运行前端测试、构建并提交前端改动**

Run: `node --test tests/wecomIdentitySync.test.mjs && npm run build`，工作目录 `D:/项目整体备份/mowayspos-next-task/frontend`；通过后执行 `git add frontend/src/features/settings/WecomIdentitySyncModal.tsx frontend/tests/wecomIdentitySync.test.mjs`，再执行 `git commit -m "fix: clarify scoped wecom account provisioning"`。

Expected: Node test PASS；TypeScript 与 Vite build 退出码为 0；提交只包含这两个前端文件。

### Task 4: 完整回归与交付前核验

**Files:**
- Verify: `D:/项目整体备份/mowayspos-next-task/bowei_ai_dashboard/app/services/wecom.py`
- Verify: `D:/项目整体备份/mowayspos-next-task/bowei_ai_dashboard/app/routers/accounts.py`
- Verify: `D:/项目整体备份/mowayspos-next-task/frontend/src/features/settings/WecomIdentitySyncModal.tsx`

- [ ] **Step 1: 检查路由没有保留根部门全员读取**

Run: `rg -n "list_department_(users|user_details)\(department_id=1, fetch_child=True\)" app/routers/accounts.py`，工作目录 `D:/项目整体备份/mowayspos-next-task/bowei_ai_dashboard`。

Expected: 无输出，退出码为 1。

- [ ] **Step 2: 运行后端完整测试套件**

Run: `pytest -q`，工作目录 `D:/项目整体备份/mowayspos-next-task/bowei_ai_dashboard`。

Expected: PASS，0 failures。

- [ ] **Step 3: 检查提交前差异与工作树**

Run: `git diff --check && git status --short`，工作目录 `D:/项目整体备份/mowayspos-next-task`。

Expected: `git diff --check` 无输出；状态中仅出现用户原有的未关联改动，不出现本功能文件的未提交改动。

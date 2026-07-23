"""任务卡问题流转 — API 联测脚本

通过 HTTP 调用完整链路：
1. 登录获取 session
2. 在 DB 中创建测试提交（短 session，用完即关）
3. POST /api/confirmations/{id}/cards/{idx}/escalate-to-issue
4. PATCH /api/issues/{id}/submit-opinion
5. PATCH /api/issues/{id}/owner-confirm (accepted=true)
6. 验证回写
7. 清理

关键：不持有 DB session 做 API 调用，避免 SQLite 写锁冲突。
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# ── 设置环境变量 ──────────────────────────────────────────────
DB_PATH = Path(__file__).parent / "bowei_ai_dashboard.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH.as_posix()}"
os.environ["ALLOW_PROTECTED_DATABASE_MIGRATION"] = "true"

sys.path.insert(0, str(Path(__file__).parent))

BASE_URL = "http://127.0.0.1:8008"
USERNAME = "moways"
PASSWORD = "123456"

PASSED = []
FAILED = []


def check(name: str, condition: bool, detail: str = ""):
    if condition:
        PASSED.append(name)
        print(f"  [PASS] {name}")
    else:
        FAILED.append(name)
        print(f"  [FAIL] {name} — {detail}")


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


class ApiClient:
    def __init__(self):
        self.cookie = ""

    def _request(self, method: str, path: str, data: dict | None = None):
        url = f"{BASE_URL}{path}"
        body = json.dumps(data).encode("utf-8") if data else None
        req = Request(url, data=body, method=method)
        req.add_header("Content-Type", "application/json")
        if self.cookie:
            req.add_header("Cookie", self.cookie)
        try:
            resp = urlopen(req, timeout=15)
            body_text = resp.read().decode("utf-8")
            set_cookie = resp.headers.get("Set-Cookie")
            if set_cookie:
                self.cookie = set_cookie.split(";")[0]
            return resp.status, json.loads(body_text) if body_text else {}
        except HTTPError as e:
            body_text = e.read().decode("utf-8")
            try:
                return e.code, json.loads(body_text)
            except Exception:
                return e.code, {"raw": body_text}

    def get(self, path: str):
        return self._request("GET", path)

    def post(self, path: str, data: dict):
        return self._request("POST", path, data)

    def patch(self, path: str, data: dict):
        return self._request("PATCH", path, data)


def create_test_submission(project_id: int, title: str, raw_text: str, card_title: str) -> int:
    """在短 session 中创建测试提交，返回 submission_id。"""
    from app.database import SessionLocal
    from app import models
    from app.domain import submission_status as SS

    human_result = {
        "raw_text": raw_text,
        "task_reports": [
            {
                "type": "progress",
                "result_type": "subtask_progress",
                "matched_subtask_id": None,
                "title": card_title,
                "content": "测试用内容",
                "assignee": USERNAME,
                "confirmation_status": "pending",
                "subtask_issues": [],
                "achievements": [],
            },
        ],
    }

    db = SessionLocal()
    try:
        submission = models.UpdateSubmission(
            project_id=project_id,
            source_type="语音汇报",
            submitter=USERNAME,
            submitter_id=1,
            title=title,
            transcript_text=raw_text,
            human_result_json=json.dumps(human_result, ensure_ascii=False),
            confirm_status=SS.S_PENDING_OWNER,
        )
        db.add(submission)
        db.commit()
        return submission.id
    finally:
        db.close()


def get_card(sub_id: int, card_index: int = 0) -> dict:
    """在短 session 中读取卡片数据。"""
    from app.database import SessionLocal
    from app.services import workflow as W

    db = SessionLocal()
    try:
        sub = db.get(__import__("app.models", fromlist=["UpdateSubmission"]).UpdateSubmission, sub_id)
        data = W.submission_result(sub)
        return data["task_reports"][card_index]
    finally:
        db.close()


def get_project_id() -> int:
    from app.database import SessionLocal
    from app import models

    db = SessionLocal()
    try:
        project = db.query(models.Project).filter(models.Project.is_active.is_(True)).first()
        return project.id
    finally:
        db.close()


def cleanup_test_data(submission_ids: list[int], issue_ids: list[int]):
    from app.database import SessionLocal
    from app import models

    db = SessionLocal()
    try:
        for iid in issue_ids:
            issue = db.get(models.Issue, iid)
            if issue:
                db.delete(issue)
        for sid in submission_ids:
            sub = db.get(models.UpdateSubmission, sid)
            if sub:
                db.delete(sub)
        db.commit()
    except Exception as e:
        print(f"  清理失败: {e}")
        db.rollback()
    finally:
        db.close()


def main():
    client = ApiClient()
    cleanup_subs = []
    cleanup_issues = []

    try:
        # ──────────────────────────────────────────────────────
        # Phase 1: 登录
        # ──────────────────────────────────────────────────────
        section("Phase 1: 登录")
        status, body = client.post("/api/auth/login", {"username": USERNAME, "password": PASSWORD})
        check("登录成功", status == 200 and body.get("ok") is True, f"status={status} body={body}")
        check("获取 session cookie", bool(client.cookie))

        project_id = get_project_id()
        print(f"  项目 id={project_id}")

        # ──────────────────────────────────────────────────────
        # Phase 2: 创建测试提交
        # ──────────────────────────────────────────────────────
        section("Phase 2: 创建测试提交")

        sub_id = create_test_submission(
            project_id=project_id,
            title="【API联测】任务卡问题流转测试",
            raw_text="API联测：本周推进了项目A的进度，但遇到了需要统筹协调的资源问题",
            card_title="项目A进度推进",
        )
        cleanup_subs.append(sub_id)
        print(f"  创建提交 id={sub_id}")

        card = get_card(sub_id)
        check("卡片初始状态=pending",
              card["confirmation_status"] == "pending",
              f"实际={card.get('confirmation_status')}")

        # ──────────────────────────────────────────────────────
        # Phase 3: 转问题中心（待协调）
        # ──────────────────────────────────────────────────────
        section("Phase 3: 转问题中心（待协调）")

        status, body = client.post(
            f"/api/confirmations/{sub_id}/cards/0/escalate-to-issue",
            {
                "target": "coordinator",
                "note": "API联测：资源冲突需要统筹人协调",
                "operator": USERNAME,
            },
        )
        check("escalate-to-issue 返回 200", status == 200, f"status={status} body={body}")
        issue_id = body.get("issue_id")
        check("返回 issue_id", issue_id is not None, f"body={body}")
        if issue_id:
            cleanup_issues.append(issue_id)
        check("submission 在返回中", "submission" in body)

        # 验证卡片锁定
        card = get_card(sub_id)
        check("卡片状态=transferred_to_coordinator",
              card["confirmation_status"] == "transferred_to_coordinator",
              f"实际={card['confirmation_status']}")
        check("卡片有 escalated_issue_id",
              card.get("escalated_issue_id") == issue_id)

        # ──────────────────────────────────────────────────────
        # Phase 4: 获取 Issue 详情
        # ──────────────────────────────────────────────────────
        section("Phase 4: 验证 Issue 详情")

        status, issue = client.get(f"/api/issues/{issue_id}")
        check("获取 Issue 返回 200", status == 200, f"status={status}")
        check("Issue source_type=ai_confirmation",
              issue.get("source_type") == "ai_confirmation",
              f"实际={issue.get('source_type')}")
        check("Issue issue_type=待协调",
              issue.get("issue_type") == "待协调",
              f"实际={issue.get('issue_type')}")
        check("Issue status=待协调",
              issue.get("status") == "待协调",
              f"实际={issue.get('status')}")
        check("Issue source_submission_id 正确",
              issue.get("source_submission_id") == sub_id)
        check("Issue source_card_index=0",
              issue.get("source_card_index") == 0)
        check("Issue description 包含【来自 AI 确认中心】",
              "【来自 AI 确认中心】" in (issue.get("description") or ""))

        # ──────────────────────────────────────────────────────
        # Phase 5: 重复转出应返回 409
        # ──────────────────────────────────────────────────────
        section("Phase 5: 重复转出校验")

        status, body = client.post(
            f"/api/confirmations/{sub_id}/cards/0/escalate-to-issue",
            {
                "target": "coordinator",
                "note": "再次转出测试",
                "operator": USERNAME,
            },
        )
        check("重复转出返回 409", status == 409, f"status={status} body={body}")

        # ──────────────────────────────────────────────────────
        # Phase 6: 统筹人提交意见
        # ──────────────────────────────────────────────────────
        section("Phase 6: 统筹人提交意见")

        status, body = client.patch(
            f"/api/issues/{issue_id}/submit-opinion",
            {"opinion": "API联测意见：已协调资源，下周一可推进。"},
        )
        check("submit-opinion 返回 200", status == 200, f"status={status} body={body}")
        check("Issue 状态=待负责人确认",
              body.get("status") == "待负责人确认",
              f"实际={body.get('status')}")
        check("Issue opinion 已设置",
              "API联测意见" in (body.get("opinion") or ""))

        # ──────────────────────────────────────────────────────
        # Phase 7: 负责人确认接受 → 回写
        # ──────────────────────────────────────────────────────
        section("Phase 7: 负责人确认接受 → 回写")

        status, body = client.patch(
            f"/api/issues/{issue_id}/owner-confirm",
            {"accepted": True, "note": "同意，按计划推进"},
        )
        check("owner-confirm 返回 200", status == 200, f"status={status} body={body}")
        check("Issue 状态=已解决",
              body.get("status") == "已解决",
              f"实际={body.get('status')}")

        # ──────────────────────────────────────────────────────
        # Phase 8: 验证任务卡回写
        # ──────────────────────────────────────────────────────
        section("Phase 8: 验证任务卡回写")

        card = get_card(sub_id)
        check("卡片状态=coordinator_given",
              card["confirmation_status"] == "coordinator_given",
              f"实际={card['confirmation_status']}")
        check("卡片 coordinator_note 回写",
              "API联测意见" in (card.get("coordinator_note") or ""),
              f"实际={card.get('coordinator_note')}")
        check("卡片 escalated_issue_id 已清除",
              "escalated_issue_id" not in card)

        # ──────────────────────────────────────────────────────
        # Phase 9: CEO 路线测试（coordinator_given → 再转 CEO）
        # ──────────────────────────────────────────────────────
        section("Phase 9: CEO 路线测试")

        status, body = client.post(
            f"/api/confirmations/{sub_id}/cards/0/escalate-to-issue",
            {
                "target": "ceo",
                "note": "API联测：需要企业教练决策优先级",
                "operator": USERNAME,
            },
        )
        check("CEO escalate 返回 200", status == 200, f"status={status} body={body}")
        ceo_issue_id = body.get("issue_id")
        if ceo_issue_id:
            cleanup_issues.append(ceo_issue_id)

        card = get_card(sub_id)
        check("CEO 转出后卡片状态=pending_ceo_decision",
              card["confirmation_status"] == "pending_ceo_decision",
              f"实际={card['confirmation_status']}")

        # CEO 提交意见
        status, body = client.patch(
            f"/api/issues/{ceo_issue_id}/submit-opinion",
            {"opinion": "CEO决策：优先推进，资源下周到位。"},
        )
        check("CEO submit-opinion 返回 200", status == 200, f"status={status} body={body}")

        # 负责人确认
        status, body = client.patch(
            f"/api/issues/{ceo_issue_id}/owner-confirm",
            {"accepted": True, "note": "同意CEO决策"},
        )
        check("CEO owner-confirm 返回 200", status == 200, f"status={status} body={body}")

        # 验证 CEO 回写
        card = get_card(sub_id)
        check("CEO 回写后卡片状态=ceo_decided",
              card["confirmation_status"] == "ceo_decided",
              f"实际={card['confirmation_status']}")
        check("CEO 回写后卡片 ceo_note",
              "CEO决策" in (card.get("ceo_note") or ""),
              f"实际={card.get('ceo_note')}")

        # ──────────────────────────────────────────────────────
        # Phase 10: 退回补充路径
        # ──────────────────────────────────────────────────────
        section("Phase 10: 退回补充路径")

        sub2_id = create_test_submission(
            project_id=project_id,
            title="【API联测】退回补充测试",
            raw_text="退回测试：遇到了新的技术难点",
            card_title="技术难点攻关",
        )
        cleanup_subs.append(sub2_id)

        # 转问题中心
        status, body = client.post(
            f"/api/confirmations/{sub2_id}/cards/0/escalate-to-issue",
            {
                "target": "coordinator",
                "note": "退回测试：请评估技术方案",
                "operator": USERNAME,
            },
        )
        check("退回测试 escalate 返回 200", status == 200, f"status={status} body={body}")
        reject_issue_id = body.get("issue_id")
        if reject_issue_id:
            cleanup_issues.append(reject_issue_id)

        # 统筹人提交意见
        status, body = client.patch(
            f"/api/issues/{reject_issue_id}/submit-opinion",
            {"opinion": "初步方案可行，但需补充时间线。"},
        )
        check("退回测试 submit-opinion 返回 200", status == 200, f"status={status} body={body}")

        # 负责人退回
        status, body = client.patch(
            f"/api/issues/{reject_issue_id}/owner-confirm",
            {"accepted": False, "note": "需要更详细的时间线和责任人"},
        )
        check("退回测试 owner-confirm(reject) 返回 200", status == 200, f"status={status} body={body}")
        check("退回后 Issue 状态=处理中",
              body.get("status") == "处理中",
              f"实际={body.get('status')}")

        # 验证卡片仍锁定
        card2 = get_card(sub2_id)
        check("退回后卡片仍锁定",
              card2["confirmation_status"] == "transferred_to_coordinator",
              f"实际={card2['confirmation_status']}")
        check("退回后 escalated_issue_id 仍存在",
              card2.get("escalated_issue_id") == reject_issue_id)

        # 统筹人再次补充意见
        status, body = client.patch(
            f"/api/issues/{reject_issue_id}/submit-opinion",
            {"opinion": "补充：下周一启动，周三完成，负责人张三。"},
        )
        check("再次 submit-opinion 返回 200", status == 200, f"status={status} body={body}")
        check("再次提交后 Issue 状态=待负责人确认",
              body.get("status") == "待负责人确认",
              f"实际={body.get('status')}")

        # 负责人这次接受
        status, body = client.patch(
            f"/api/issues/{reject_issue_id}/owner-confirm",
            {"accepted": True, "note": "同意补充后的方案"},
        )
        check("再次 owner-confirm 返回 200", status == 200, f"status={status} body={body}")

        # 验证最终回写
        card2 = get_card(sub2_id)
        check("退回后最终回写卡片状态=coordinator_given",
              card2["confirmation_status"] == "coordinator_given",
              f"实际={card2['confirmation_status']}")
        check("退回后最终回写 coordinator_note 更新",
              "下周一启动" in (card2.get("coordinator_note") or ""),
              f"实际={card2.get('coordinator_note')}")

    except Exception as e:
        print(f"\n  [ERROR] 测试中断: {e}")
        traceback.print_exc()
        FAILED.append(f"异常中断: {e}")
    finally:
        # ──────────────────────────────────────────────────────
        # 清理
        # ──────────────────────────────────────────────────────
        section("清理测试数据")
        cleanup_test_data(cleanup_subs, cleanup_issues)
        print("  清理完成")

    # ──────────────────────────────────────────────────────
    # 汇总
    # ──────────────────────────────────────────────────────
    section("API 联测汇总")
    print(f"  通过: {len(PASSED)}")
    print(f"  失败: {len(FAILED)}")
    print(f"  总计: {len(PASSED) + len(FAILED)}")

    if FAILED:
        print("\n  失败项:")
        for f in FAILED:
            print(f"    - {f}")

    return len(FAILED) == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)

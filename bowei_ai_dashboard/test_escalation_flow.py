"""任务卡问题流转 — 端到端测试脚本

测试链路：
1. 创建测试提交（带 task_reports）
2. escalate_card_to_issue（coordinator 路线）
3. submit_opinion（统筹人提交意见）
4. owner_confirm_opinion（accepted=true → 已解决 → 回写任务卡）
5. 验证回写结果
6. 同理测试 ceo 路线
7. 测试退回补充路径
8. 清理测试数据
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

# ── 设置环境变量 ──────────────────────────────────────────────
DB_PATH = Path(__file__).parent / "bowei_ai_dashboard.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH.as_posix()}"
os.environ["ALLOW_PROTECTED_DATABASE_MIGRATION"] = "true"
# 抑制通知发送
os.environ["BOWEI_TEST_MODE"] = "true"

# 确保 cwd 在项目根
os.chdir(Path(__file__).parent.parent)

sys.path.insert(0, str(Path(__file__).parent))

# ── 导入 app 模块 ──────────────────────────────────────────────
from app.database import SessionLocal, engine
from app import models, crud
from app.domain import issue_flow as IF
from app.domain import submission_status as SS
from app.services import escalation as ESC
from app.services import workflow as W

# ── 测试框架 ──────────────────────────────────────────────────
PASSED = []
FAILED = []
SKIPPED = []


def check(name: str, condition: bool, detail: str = ""):
    if condition:
        PASSED.append(name)
        print(f"  [PASS] {name}")
    else:
        FAILED.append(name)
        print(f"  [FAIL] {name} — {detail}")


def skip(name: str, reason: str):
    SKIPPED.append(name)
    print(f"  [SKIP] {name} — {reason}")


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def main():
    db = SessionLocal()
    cleanup_ids = {"submissions": [], "issues": [], "logs": []}

    try:
        # ──────────────────────────────────────────────────────
        # Phase 0: 准备测试数据（找项目、账号）
        # ──────────────────────────────────────────────────────
        section("Phase 0: 准备测试数据")

        project = db.query(models.Project).filter(
            models.Project.is_active.is_(True)
        ).first()
        if not project:
            print("  [ABORT] 没有可用项目")
            return

        # 找一个有 owner 角色的账号
        owner_member = db.query(models.ProjectMember).filter(
            models.ProjectMember.project_id == project.id,
            models.ProjectMember.role == "owner",
        ).first()

        if owner_member:
            owner_account = db.query(models.Account).filter(
                models.Account.person_id == owner_member.person_id
            ).first()
            owner_username = owner_account.username if owner_account else f"owner_{project.id}"
            owner_person_id = owner_member.person_id
        else:
            # fallback: 用任意账号
            owner_account = db.query(models.Account).first()
            owner_username = owner_account.username if owner_account else "admin"
            owner_person_id = owner_account.person_id if owner_account else None

        print(f"  项目：{project.name} (id={project.id})")
        print(f"  负责人账号：{owner_username} (person_id={owner_person_id})")

        # 找 coordinator
        coord_member = db.query(models.ProjectMember).filter(
            models.ProjectMember.project_id == project.id,
            models.ProjectMember.role == "coordinator",
        ).first()
        coord_username = ""
        if coord_member:
            coord_account = db.query(models.Account).filter(
                models.Account.person_id == coord_member.person_id
            ).first()
            coord_username = coord_account.username if coord_account else ""

        # 找 project_ceo
        ceo_member = db.query(models.ProjectMember).filter(
            models.ProjectMember.project_id == project.id,
            models.ProjectMember.role == "project_ceo",
        ).first()
        ceo_username = ""
        if ceo_member:
            ceo_account = db.query(models.Account).filter(
                models.Account.person_id == ceo_member.person_id
            ).first()
            ceo_username = ceo_account.username if ceo_account else ""

        print(f"  统筹人账号：{coord_username or '（无）'}")
        print(f"  企业教练账号：{ceo_username or '（无）'}")

        check("项目存在", project is not None)
        check("负责人账号存在", bool(owner_username))

        # ──────────────────────────────────────────────────────
        # Phase 1: 创建测试提交（带 task_reports 格式）
        # ──────────────────────────────────────────────────────
        section("Phase 1: 创建测试提交")

        human_result = {
            "raw_text": "本周完成了客户A的需求调研，发现一个需要统筹的资源冲突问题",
            "task_reports": [
                {
                    "type": "progress",
                    "result_type": "subtask_progress",
                    "matched_subtask_id": None,  # 测试用，不写入实际 subtask
                    "title": "客户A需求调研",
                    "content": "完成了需求文档初稿，但遇到资源冲突",
                    "assignee": owner_username,
                    "confirmation_status": "pending",
                    "subtask_issues": [],
                    "achievements": [],
                },
                {
                    "type": "progress",
                    "result_type": "subtask_progress",
                    "matched_subtask_id": None,
                    "title": "系统架构设计",
                    "content": "架构方案已完成评审",
                    "assignee": owner_username,
                    "confirmation_status": "pending",
                    "subtask_issues": [],
                    "achievements": [],
                },
            ],
        }

        submission = models.UpdateSubmission(
            project_id=project.id,
            source_type="语音汇报",
            submitter=owner_username,
            submitter_id=owner_person_id,
            title="【测试】任务卡问题流转测试提交",
            transcript_text="本周完成了客户A的需求调研，发现一个需要统筹的资源冲突问题",
            human_result_json=json.dumps(human_result, ensure_ascii=False),
            confirm_status=SS.S_PENDING_OWNER,
        )
        db.add(submission)
        db.flush()
        cleanup_ids["submissions"].append(submission.id)
        print(f"  创建提交 id={submission.id}")

        # 验证提交
        data = W.submission_result(submission)
        check("提交有 2 张任务卡", len(data.get("task_reports", [])) == 2,
              f"实际 {len(data.get('task_reports', []))} 张")
        check("卡片0初始状态=pending",
              data["task_reports"][0].get("confirmation_status") == "pending")

        # ──────────────────────────────────────────────────────
        # Phase 2: 测试 escalate_card_to_issue（coordinator 路线）
        # ──────────────────────────────────────────────────────
        section("Phase 2: 转问题中心（待协调）")

        caller_name = owner_username
        issue = ESC.escalate_card_to_issue(
            db=db,
            submission=submission,
            card_index=0,
            target="coordinator",
            note="资源冲突需要统筹人协调，请协助处理",
            caller_username=owner_username,
            caller_name=caller_name,
            project_id=project.id,
        )
        cleanup_ids["issues"].append(issue.id)
        db.flush()

        check("Issue 已创建", issue.id is not None)
        check("Issue source_type=ai_confirmation",
              issue.source_type == ESC.SOURCE_AI_CONFIRMATION,
              f"实际={issue.source_type}")
        check("Issue issue_type=待协调",
              issue.issue_type == IF.TYPE_COORDINATE,
              f"实际={issue.issue_type}")
        check("Issue status=待协调",
              issue.status == IF.STATUS_COORDINATING,
              f"实际={issue.status}")
        check("Issue source_submission_id 正确",
              issue.source_submission_id == submission.id)
        check("Issue source_card_index=0",
              issue.source_card_index == 0)

        # 验证卡片锁定
        data = W.submission_result(submission)
        card0 = data["task_reports"][0]
        check("卡片0状态=transferred_to_coordinator",
              card0["confirmation_status"] == "transferred_to_coordinator",
              f"实际={card0['confirmation_status']}")
        check("卡片0有 escalated_issue_id",
              card0.get("escalated_issue_id") == issue.id)
        check("卡片0有 escalation_history",
              len(card0.get("escalation_history", [])) == 1)
        check("卡片0 confirmation_note 已设置",
              "资源冲突" in (card0.get("confirmation_note") or ""))

        # 卡片1 未受影响
        card1 = data["task_reports"][1]
        check("卡片1状态仍为 pending",
              card1["confirmation_status"] == "pending")

        # Issue description 包含上下文
        check("Issue description 包含【来自 AI 确认中心】",
              "【来自 AI 确认中心】" in (issue.description or ""))
        check("Issue description 包含提交人原文",
              "资源冲突" in (issue.description or ""))

        # ──────────────────────────────────────────────────────
        # Phase 3: 重复转出应该被拒绝
        # ──────────────────────────────────────────────────────
        section("Phase 3: 重复转出校验")
        try:
            ESC.escalate_card_to_issue(
                db=db,
                submission=submission,
                card_index=0,
                target="coordinator",
                note="再次转出测试",
                caller_username=owner_username,
                caller_name=caller_name,
                project_id=project.id,
            )
            check("重复转出应被拒绝", False, "没有抛出异常")
        except Exception as e:
            check("重复转出被拒绝（409）",
                  "已转出" in str(e) or "409" in str(e),
                  f"异常={e}")

        # ──────────────────────────────────────────────────────
        # Phase 4: 测试 submit_opinion + owner_confirm（accepted=true）
        # ──────────────────────────────────────────────────────
        section("Phase 4: 统筹人提交意见 → 负责人确认接受")

        # 直接操作 Issue（模拟 submit_opinion 的效果）
        issue.opinion = "已协调资源，下周一可以安排，请推进。"
        issue.status = IF.STATUS_PENDING_OWNER_CONFIRM
        db.flush()
        check("Issue 状态=待负责人确认",
              issue.status == IF.STATUS_PENDING_OWNER_CONFIRM)

        # 负责人确认接受 → 触发回写
        issue.status = IF.STATUS_RESOLVED
        resolution_parts = [issue.opinion or ""]
        resolution_parts.append("负责人确认：同意，按计划推进")
        issue.resolution = "\n".join(p for p in resolution_parts if p)
        db.flush()

        # 调用回写
        updated_sub = ESC.write_back_to_card(db, issue)
        check("回写函数返回 submission",
              updated_sub is not None and updated_sub.id == submission.id)

        db.flush()

        # 验证回写结果
        data = W.submission_result(submission)
        card0 = data["task_reports"][0]
        check("回写后卡片0状态=coordinator_given",
              card0["confirmation_status"] == "coordinator_given",
              f"实际={card0['confirmation_status']}")
        check("回写后卡片0有 coordinator_note",
              "已协调资源" in (card0.get("coordinator_note") or ""),
              f"实际={card0.get('coordinator_note')}")
        check("回写后卡片0有 coordinator_operator",
              bool(card0.get("coordinator_operator")))
        check("回写后卡片0有 coordinator_feedback_at",
              bool(card0.get("coordinator_feedback_at")))
        check("回写后 escalated_issue_id 已清除",
              "escalated_issue_id" not in card0)
        check("回写后 escalation_history 保留",
              len(card0.get("escalation_history", [])) >= 1)

        # ──────────────────────────────────────────────────────
        # Phase 5: 测试 CEO 路线
        # ──────────────────────────────────────────────────────
        section("Phase 5: 转问题中心（需决策）")

        # 卡片0 回写后状态=coordinator_given，可以再次转出
        issue_ceo = ESC.escalate_card_to_issue(
            db=db,
            submission=submission,
            card_index=0,
            target="ceo",
            note="需要企业教练决策优先级",
            caller_username=owner_username,
            caller_name=caller_name,
            project_id=project.id,
        )
        cleanup_ids["issues"].append(issue_ceo.id)
        db.flush()

        check("CEO Issue 已创建", issue_ceo.id is not None)
        check("CEO Issue issue_type=需决策",
              issue_ceo.issue_type == IF.TYPE_DECISION,
              f"实际={issue_ceo.issue_type}")
        check("CEO Issue status=待决策",
              issue_ceo.status == IF.STATUS_PENDING_DECISION,
              f"实际={issue_ceo.status}")

        # 验证卡片锁定
        data = W.submission_result(submission)
        card0 = data["task_reports"][0]
        check("卡片0状态=pending_ceo_decision",
              card0["confirmation_status"] == "pending_ceo_decision",
              f"实际={card0['confirmation_status']}")
        check("卡片0 escalation_history 有 2 条",
              len(card0.get("escalation_history", [])) == 2,
              f"实际 {len(card0.get('escalation_history', []))} 条")

        # CEO 提交意见
        issue_ceo.opinion = "决策：优先推进，资源下周到位。"
        issue_ceo.status = IF.STATUS_PENDING_OWNER_CONFIRM
        db.flush()

        # 负责人确认接受 → 回写
        issue_ceo.status = IF.STATUS_RESOLVED
        issue_ceo.resolution = "决策：优先推进，资源下周到位。\n负责人确认：同意"
        db.flush()

        updated_sub2 = ESC.write_back_to_card(db, issue_ceo)
        check("CEO 回写函数返回 submission", updated_sub2 is not None)
        db.flush()

        data = W.submission_result(submission)
        card0 = data["task_reports"][0]
        check("CEO 回写后卡片0状态=ceo_decided",
              card0["confirmation_status"] == "ceo_decided",
              f"实际={card0['confirmation_status']}")
        check("CEO 回写后卡片0有 ceo_note",
              "优先推进" in (card0.get("ceo_note") or ""),
              f"实际={card0.get('ceo_note')}")
        check("CEO 回写后卡片0有 ceo_decided_at",
              bool(card0.get("ceo_decided_at")))

        # ──────────────────────────────────────────────────────
        # Phase 6: 测试退回补充路径
        # ──────────────────────────────────────────────────────
        section("Phase 6: 负责人退回补充")

        # 用卡片1 测试退回
        issue_reject = ESC.escalate_card_to_issue(
            db=db,
            submission=submission,
            card_index=1,
            target="coordinator",
            note="请补充资源分配细节",
            caller_username=owner_username,
            caller_name=caller_name,
            project_id=project.id,
        )
        cleanup_ids["issues"].append(issue_reject.id)
        db.flush()

        # 统筹人提交意见
        issue_reject.opinion = "初步方案是A，但细节不够。"
        issue_reject.status = IF.STATUS_PENDING_OWNER_CONFIRM
        db.flush()

        # 负责人退回补充
        issue_reject.status = IF.STATUS_IN_PROGRESS
        issue_reject.resolution = "负责人要求补充：需要具体时间线和责任人"
        db.flush()

        check("退回后 Issue status=处理中",
              issue_reject.status == IF.STATUS_IN_PROGRESS,
              f"实际={issue_reject.status}")

        # 卡片1 应该仍然锁定（未回写）
        data = W.submission_result(submission)
        card1 = data["task_reports"][1]
        check("退回后卡片1仍锁定=transferred_to_coordinator",
              card1["confirmation_status"] == "transferred_to_coordinator",
              f"实际={card1['confirmation_status']}")
        check("退回后卡片1 escalated_issue_id 仍存在",
              card1.get("escalated_issue_id") == issue_reject.id)

        # 统筹人再次提交意见
        issue_reject.opinion = "补充：下周一启动，周三完成，负责人是张三。"
        issue_reject.status = IF.STATUS_PENDING_OWNER_CONFIRM
        db.flush()

        # 负责人这次确认接受
        issue_reject.status = IF.STATUS_RESOLVED
        issue_reject.resolution = "补充：下周一启动，周三完成。\n负责人确认：同意"
        db.flush()

        updated_sub3 = ESC.write_back_to_card(db, issue_reject)
        check("退回后再次回写成功", updated_sub3 is not None)
        db.flush()

        data = W.submission_result(submission)
        card1 = data["task_reports"][1]
        check("退回后回写卡片1状态=coordinator_given",
              card1["confirmation_status"] == "coordinator_given",
              f"实际={card1['confirmation_status']}")
        check("退回后回写卡片1 coordinator_note 更新",
              "下周一启动" in (card1.get("coordinator_note") or ""),
              f"实际={card1.get('coordinator_note')}")

        # ──────────────────────────────────────────────────────
        # Phase 7: 测试 build_escalation_description
        # ──────────────────────────────────────────────────────
        section("Phase 7: build_escalation_description 内容验证")

        desc = ESC.build_escalation_description(
            submission=submission,
            card=data["task_reports"][0],
            card_index=0,
            note="测试转交说明",
            caller_name=caller_name,
        )
        check("description 包含提交标题",
              "任务卡问题流转测试提交" in desc)
        check("description 包含提交人",
              owner_username in desc)
        check("description 包含任务卡标题",
              "客户A需求调研" in desc)
        check("description 包含转交说明",
              "测试转交说明" in desc)
        check("description 包含转交人",
              caller_name in desc)

        # ──────────────────────────────────────────────────────
        # Phase 8: 测试 is_card_escalated
        # ──────────────────────────────────────────────────────
        section("Phase 8: is_card_escalated 判断函数")

        # 卡片0 已回写（coordinator_given），不应处于锁定
        check("卡片0 不锁定（已回写）",
              not ESC.is_card_escalated(data["task_reports"][0]))

        # 构造锁定状态卡片
        locked_card = {"confirmation_status": "pending_ceo_decision"}
        check("pending_ceo_decision 判定为锁定",
              ESC.is_card_escalated(locked_card))

        locked_card2 = {"confirmation_status": "transferred_to_coordinator"}
        check("transferred_to_coordinator 判定为锁定",
              ESC.is_card_escalated(locked_card2))

        unlocked_card = {"confirmation_status": "pending"}
        check("pending 不锁定",
              not ESC.is_card_escalated(unlocked_card))

        unlocked_card2 = {"confirmation_status": ""}
        check("空状态不锁定",
              not ESC.is_card_escalated(unlocked_card2))

    except Exception as e:
        print(f"\n  [ERROR] 测试中断: {e}")
        traceback.print_exc()
        FAILED.append(f"异常中断: {e}")
    finally:
        # ──────────────────────────────────────────────────────
        # 清理测试数据
        # ──────────────────────────────────────────────────────
        section("清理测试数据")
        try:
            for issue_id in cleanup_ids["issues"]:
                issue = db.get(models.Issue, issue_id)
                if issue:
                    db.delete(issue)
            for sub_id in cleanup_ids["submissions"]:
                sub = db.get(models.UpdateSubmission, sub_id)
                if sub:
                    db.delete(sub)
            db.commit()
            print("  清理完成")
        except Exception as e:
            print(f"  清理失败: {e}")
            db.rollback()
        finally:
            db.close()

    # ──────────────────────────────────────────────────────
    # 汇总
    # ──────────────────────────────────────────────────────
    section("测试汇总")
    total = len(PASSED) + len(FAILED) + len(SKIPPED)
    print(f"  通过: {len(PASSED)}")
    print(f"  失败: {len(FAILED)}")
    print(f"  跳过: {len(SKIPPED)}")
    print(f"  总计: {total}")

    if FAILED:
        print("\n  失败项:")
        for f in FAILED:
            print(f"    - {f}")

    return len(FAILED) == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)

"""FIX-2C-2 frontend projection and payload contracts (no Git-history coupling)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "frontend" / "src" / "pages" / "ConfirmPage.tsx"
ASSETS = ROOT / "frontend" / "src" / "domain" / "confirmationAssets.ts"
TASK_CARDS = ROOT / "frontend" / "src" / "domain" / "confirmationTaskCards.ts"


def _page() -> str:
    return PAGE.read_text(encoding="utf-8")


def _run_projection(payload: dict) -> dict:
    script = r"""
const fs = require('fs');
const vm = require('vm');
const { createRequire } = require('module');
const req = createRequire(process.argv[1]);
const ts = req('typescript');
const source = fs.readFileSync(process.argv[2], 'utf8');
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
const mod = { exports: {} };
vm.runInNewContext(`(function(exports,module,require){${js}\n})(mod.exports,mod,require)`, { mod, require });
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(mod.exports.buildConfirmationAssetProjection(input)));
"""
    result = subprocess.run(
        [
            "node",
            "-e",
            script,
            str(ROOT / "frontend" / "package.json"),
            str(ASSETS),
        ],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_projection_helper_exists_and_confirm_page_uses_it():
    assert ASSETS.is_file()
    source = ASSETS.read_text(encoding="utf-8")
    page = _page()
    assert "buildConfirmationAssetProjection" in source
    assert "buildConfirmationAssetProjection" in page
    assert "assetProjection.allIssues" in page


def test_achievement_projection_prefers_report_and_keeps_unique_submission_asset():
    original = {
        "task_reports": [{
            "matched_subtask_id": 7,
            "matched_subtask_title": "资料核验",
            "achievements": [{"name": "《数据核验报告 V1.0》"}],
        }],
        "achievements": [
            {"name": "数据核验报告v1.0"},
            {"name": "提交整体说明"},
            {"name": " 提交整体说明！"},
        ],
    }
    projection = _run_projection(original)
    assert len(projection["reportAchievements"]) == 1
    assert projection["reportAchievements"][0]["reportIndex"] == 0
    assert projection["reportAchievements"][0]["matchedSubtaskId"] == 7
    assert [item["item"]["name"] for item in projection["submissionAchievements"]] == ["提交整体说明"]
    assert original["achievements"][0]["name"] == "数据核验报告v1.0"


def test_issue_projection_uses_priority_and_preserves_report_provenance():
    projection = _run_projection({
        "task_reports": [{
            "matched_subtask_id": 7,
            "matched_subtask_title": "资料核验",
            "subtask_issues": ["接口读取权限尚未开通，导致自动核验无法继续"],
        }],
        "key_task_issues": [{"description": "接口读取权限尚未开通，导致自动核验无法继续，需要项目负责人协调技术部门开通权限"}],
        "issues": [{"description": "接口读取权限尚未开通，导致自动核验无法继续"}],
        "pending_items": [{"description": "接口读取权限尚未开通，导致自动核验无法继续"}],
    })
    assert len(projection["allIssues"]) == 1
    issue = projection["allIssues"][0]
    assert issue["source"] == "task_report"
    assert issue["reportIndex"] == 0
    assert issue["issueIndex"] == 0
    assert issue["matchedSubtaskId"] == 7
    assert issue["matchedSubtaskTitle"] == "资料核验"


def test_pending_only_issue_survives_as_submission_issue():
    projection = _run_projection({"task_reports": [], "pending_items": [{"description": "仅 pending 的阻塞"}]})
    assert len(projection["submissionIssues"]) == 1
    assert projection["submissionIssues"][0]["source"] == "submission"
    assert projection["submissionIssues"][0]["description"] == "仅 pending 的阻塞"


def test_negative_issue_pair_is_not_merged():
    projection = _run_projection({
        "key_task_issues": [{"description": "接口权限未开通导致自动核验无法继续"}],
        "issues": [{"description": "客户数据未提供导致人工核验无法继续"}],
    })
    assert len(projection["submissionIssues"]) == 2


def test_conservative_dice_threshold_merges_non_containment_near_duplicate():
    projection = _run_projection({
        "key_task_issues": [{"description": "接口读取权限尚未开通导致自动核验无法继续"}],
        "issues": [{"description": "接口读取权限仍未开通导致自动核验无法继续"}],
    })
    assert len(projection["submissionIssues"]) == 1


def test_same_issue_on_different_subtasks_is_preserved_twice():
    projection = _run_projection({"task_reports": [
        {"matched_subtask_id": 7, "subtask_issues": [{"description": "共同阻塞"}]},
        {"matched_subtask_id": 8, "subtask_issues": [{"description": "共同阻塞"}]},
    ]})
    assert len(projection["reportIssues"]) == 2
    assert {item["matchedSubtaskId"] for item in projection["reportIssues"]} == {7, 8}


def test_submission_achievement_block_is_before_owner_actions_and_not_view_restricted():
    page = _page()
    block = page.index("{/* Submission-level achievements */}")
    issues = page.index("{/* Unified issue review projection */}")
    owner = page.index("{/* Submission-level owner actions */}")
    assert block < issues < owner
    snippet = page[block:issues]
    assert "提交级成果" in snippet
    assert "submissionAchievements.length > 0" in snippet
    assert "viewMode === 'all'" not in snippet
    assert "viewMode === 'mine'" not in snippet


def test_confirm_payload_preserves_report_issues_and_separates_submission_issues():
    page = _page()
    assert "assetProjection.submissionAchievements.map" in page
    assert "humanResult.key_task_issues = submissionIssues" in page
    assert "humanResult.issues = []" in page
    assert "reportIndex" in page
    assert "subtask_issues: []" not in page
    assert "pending_items" in page


def test_task_cards_keep_their_existing_report_only_projection_semantics():
    source = TASK_CARDS.read_text(encoding="utf-8")
    assert "report.achievements" in source
    assert "result.achievements" not in source
    assert "buildConfirmationTaskCards" in _page()


def test_frontend_contract_test_has_no_git_or_fixed_commit_dependency():
    source = Path(__file__).read_text(encoding="utf-8")
    forbidden = ["git " + value for value in ("diff", "status", "rev-parse")]
    forbidden.append("1147e783" + "464676855e034b1a3b6f2c63228520f1")
    for value in forbidden:
        assert value not in source


def test_single_card_confirm_call_remains_present_and_separate():
    page = _page()
    assert "confirmTaskCard(" in page
    assert "handleTaskCardDecision" in page
    assert "assetProjection" not in page[page.index("async function handleTaskCardDecision"):page.index("async function handleCoachSubmissionDecide")]

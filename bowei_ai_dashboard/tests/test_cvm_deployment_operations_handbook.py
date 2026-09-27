from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HANDBOOK = ROOT / "docs" / "cvm-deployment-operations-handbook.html"


def handbook_text() -> str:
    return HANDBOOK.read_text(encoding="utf-8")


def test_handbook_is_self_contained_and_project_specific() -> None:
    html = handbook_text()

    assert "<!doctype html>" in html.lower()
    assert '<html lang="zh-CN">' in html
    assert "mowayspos" in html
    assert "CLOUD CVM incremental application deploy" in html
    assert "CLOUD P1B2B-A private GHCR image publish" in html
    assert "CVM_HOST" in html
    assert "CVM_USER" in html
    assert "CVM_SSH_KEY" in html
    assert "CVM_KNOWN_HOSTS" in html
    assert "component=backend" in html
    assert "run_migrations=true" in html
    assert "--pull never" in html

    assert not re.search(r'<script[^>]+src=["\']https?://', html, re.IGNORECASE)
    assert not re.search(r'<link[^>]+href=["\']https?://', html, re.IGNORECASE)
    assert not re.search(r'<img[^>]+src=["\']https?://', html, re.IGNORECASE)
    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html


def test_handbook_exposes_copy_checklist_and_progress_contracts() -> None:
    html = handbook_text()

    command_ids = re.findall(r'<code id="([^"]+)"', html)
    copy_targets = re.findall(r'data-copy-target="([^"]+)"', html)
    step_ids = re.findall(r'data-step-id="([^"]+)"', html)

    assert len(command_ids) >= 12
    assert sorted(command_ids) == sorted(copy_targets)
    assert len(step_ids) >= 18
    assert len(step_ids) == len(set(step_ids))
    assert "mowayspos-cvm-handbook:v1" in html
    assert "localStorage.getItem" in html
    assert "localStorage.setItem" in html
    assert "navigator.clipboard.writeText" in html
    assert "window.confirm" in html
    assert 'aria-live="polite"' in html
    assert "prefers-reduced-motion" in html


def test_handbook_avoids_unsafe_or_secret_bearing_content() -> None:
    html = handbook_text()

    assert "docker system prune -a" not in html
    assert "ghp_" not in html
    assert "BEGIN OPENSSH PRIVATE KEY" not in html
    assert "CVM_SSH_KEY=" not in html
    assert "password=" not in html.lower()
    assert "保留当前版本和至少一个回滚版本" in html
    assert "先列出，再确认，最后定向删除" in html

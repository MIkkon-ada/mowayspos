# -*- coding: utf-8 -*-
"""
修复 project_members 孤儿记录数据一致性脚本（可重复执行 / 幂等）

问题背景：
  project_members.person_id 应外键指向 people.id。
  但测试库中存在孤儿记录：person_name_snapshot='吴肖', role='coordinator',
  person_id=3，而 people 表不存在 id=3（吴肖真实 id=5）。

  这导致"组织与分工"页面以 person_id 构建 roleMap 时，
  吴肖(id=5)查不到角色 → 回退为"协同成员"；
  而"项目管理"页面用 person_name_snapshot 直接取值 → 显示"统筹人"。

修复策略（仅修脏数据，不改表结构 / 接口 / 前端 / 权限）：
  1. 找出 project_members 中 person_id 不存在于 people.id 的孤儿记录。
  2. 对每条孤儿记录，按 person_name_snapshot 在 people 表查找真实人员。
     - 找到唯一匹配 → 更新 person_id 为正确值。
     - 找到多个匹配 → 跳过并告警（需人工确认）。
     - 找不到匹配 → 跳过并告警（可能是已删除人员）。
  3. 更新后同步 projects 旧字符串字段（coordinator/owners/collaborators），
     保持与 project_members 一致。

幂等性：修复后再次运行不会重复修改（无孤儿记录时直接退出）。

用法：
  python fix_orphan_project_members.py            # 执行修复
  python fix_orphan_project_members.py --dry-run  # 仅检查不修改
"""
import argparse
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "bowei_ai_dashboard.db"

# project_members.role → projects 旧字段映射
_ROLE_TO_OLD_FIELD = {
    "owner":       "owners",
    "coordinator": "coordinator",
    "member":      "collaborators",
}


def _split_names(value: str) -> list[str]:
    import re
    s = str(value or "").strip()
    if not s:
        return []
    return [x.strip() for x in re.split(r"[,，、/;\n]+", s) if x.strip()]


def _join_names(names: list[str]) -> str:
    seen: list[str] = []
    for n in names:
        n = str(n or "").strip()
        if n and n not in seen:
            seen.append(n)
    return "、".join(seen)


def find_orphans(con: sqlite3.Connection) -> list[dict]:
    """查找 project_members 中 person_id 不存在于 people.id 的孤儿记录。"""
    cur = con.execute(
        """
        SELECT pm.id, pm.project_id, pm.person_id, pm.person_name_snapshot,
               pm.role, pm.note
        FROM project_members pm
        LEFT JOIN people p ON p.id = pm.person_id
        WHERE p.id IS NULL
        ORDER BY pm.id
        """
    )
    return [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]


def find_person_by_name(con: sqlite3.Connection, name: str) -> list[dict]:
    """按姓名在 people 表查找活跃人员。"""
    cur = con.execute(
        "SELECT id, name, system_role FROM people WHERE name = :name AND is_active = 1",
        {"name": name},
    )
    return [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]


def check_duplicate_by_name(con: sqlite3.Connection) -> list[dict]:
    """检查同一项目同一姓名但 person_id 不一致的记录。"""
    cur = con.execute(
        """
        SELECT pm1.project_id, pm1.person_name_snapshot,
               GROUP_CONCAT(DISTINCT pm1.person_id) AS person_ids,
               COUNT(*) AS cnt
        FROM project_members pm1
        WHERE pm1.person_name_snapshot != ''
        GROUP BY pm1.project_id, pm1.person_name_snapshot
        HAVING COUNT(DISTINCT pm1.person_id) > 1
        ORDER BY pm1.project_id
        """
    )
    return [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]


def rebuild_project_old_fields(con: sqlite3.Connection, project_id: int):
    """
    根据 project_members 重建 projects 旧字符串字段（coordinator/owners/collaborators）。
    与后端 _sync_project_old_fields 逻辑一致。
    """
    members = con.execute(
        "SELECT person_name_snapshot, role FROM project_members WHERE project_id = :pid",
        {"pid": project_id},
    ).fetchall()

    owners: list[str] = []
    coordinators: list[str] = []
    collaborators: list[str] = []
    all_names: set[str] = set()

    for name, role in members:
        n = (name or "").strip()
        if not n:
            continue
        all_names.add(n)
        if role == "owner":
            owners.append(n)
        elif role == "coordinator":
            coordinators.append(n)
        elif role == "member":
            collaborators.append(n)

    # 保留旧字段中不在 project_members 里的历史人员
    proj_row = con.execute(
        "SELECT coordinator, owners, collaborators FROM projects WHERE id = :pid",
        {"pid": project_id},
    ).fetchone()
    if proj_row:
        legacy_coord = set(_split_names(proj_row[0])) - all_names
        legacy_owners = set(_split_names(proj_row[1])) - all_names
        legacy_collab = set(_split_names(proj_row[2])) - all_names
        coordinators = sorted(set(coordinators) | legacy_coord)
        owners = sorted(set(owners) | legacy_owners)
        collaborators = sorted(set(collaborators) | legacy_collab)

    con.execute(
        """
        UPDATE projects
        SET coordinator = :coord, owners = :owners, collaborators = :collab
        WHERE id = :pid
        """,
        {
            "coord": _join_names(coordinators),
            "owners": _join_names(owners),
            "collab": _join_names(collaborators),
            "pid": project_id,
        },
    )


def main():
    parser = argparse.ArgumentParser(description="修复 project_members 孤儿记录")
    parser.add_argument("--dry-run", action="store_true", help="仅检查不修改")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"[ERROR] 数据库不存在: {DB_PATH}")
        sys.exit(1)

    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row

    print("=" * 70)
    print("project_members 孤儿记录修复脚本")
    print(f"数据库: {DB_PATH}")
    print(f"模式:   {'DRY-RUN（仅检查）' if args.dry_run else 'EXECUTE（执行修复）'}")
    print("=" * 70)

    # ── 1. 检查同姓名不同 person_id 的重复记录 ──────────────────
    dups = check_duplicate_by_name(con)
    if dups:
        print("\n[警告] 发现同一项目同一姓名但 person_id 不一致的记录（需人工确认）:")
        for d in dups:
            print(f"  project_id={d['project_id']}, name={d['person_name_snapshot']}, "
                  f"person_ids={d['person_ids']}, count={d['cnt']}")
    else:
        print("\n[OK] 无同姓名不同 person_id 的重复记录。")

    # ── 2. 查找孤儿记录 ──────────────────────────────────────────
    orphans = find_orphans(con)
    if not orphans:
        print("\n[OK] 未发现孤儿 project_members 记录，无需修复。")
        con.close()
        return

    print(f"\n发现 {len(orphans)} 条孤儿记录 (person_id 不存在于 people.id):")
    affected_project_ids: set[int] = set()
    fixes: list[tuple[dict, int]] = []  # (orphan, correct_person_id)
    skipped: list[tuple[dict, str]] = []  # (orphan, reason)

    for o in orphans:
        print(f"\n  孤儿记录 id={o['id']}, project_id={o['project_id']}, "
              f"person_id={o['person_id']}, name='{o['person_name_snapshot']}', "
              f"role='{o['role']}'")

        # 按姓名查找真实人员
        candidates = find_person_by_name(con, o["person_name_snapshot"])
        if len(candidates) == 1:
            correct_id = candidates[0]["id"]
            print(f"    → 找到唯一匹配: people.id={correct_id}, name='{candidates[0]['name']}', "
                  f"system_role='{candidates[0]['system_role']}'")
            fixes.append((o, correct_id))
            affected_project_ids.add(o["project_id"])
        elif len(candidates) == 0:
            reason = f"people 表中无活跃人员 name='{o['person_name_snapshot']}'"
            print(f"    → [跳过] {reason}")
            skipped.append((o, reason))
        else:
            reason = (f"people 表中存在 {len(candidates)} 个 name='{o['person_name_snapshot']}' "
                      f"的活跃人员: {[c['id'] for c in candidates]}，需人工确认")
            print(f"    → [跳过] {reason}")
            skipped.append((o, reason))

    # ── 3. 执行修复 ──────────────────────────────────────────────
    if not fixes:
        print("\n[完成] 无可自动修复的记录。")
        con.close()
        return

    if args.dry_run:
        print(f"\n[DRY-RUN] 将修复 {len(fixes)} 条记录，但不实际写入。")
        for o, correct_id in fixes:
            print(f"  UPDATE project_members SET person_id={correct_id} WHERE id={o['id']} "
                  f"(原 person_id={o['person_id']}, name='{o['person_name_snapshot']}')")
        con.close()
        return

    print(f"\n开始修复 {len(fixes)} 条记录...")
    for o, correct_id in fixes:
        con.execute(
            "UPDATE project_members SET person_id = :new_id WHERE id = :pm_id",
            {"new_id": correct_id, "pm_id": o["id"]},
        )
        print(f"  [已修复] project_members.id={o['id']}: "
              f"person_id {o['person_id']} → {correct_id} "
              f"(name='{o['person_name_snapshot']}', role='{o['role']}')")

    # ── 4. 同步 projects 旧字符串字段 ────────────────────────────
    print(f"\n同步 {len(affected_project_ids)} 个项目的旧字符串字段 (coordinator/owners/collaborators)...")
    for pid in sorted(affected_project_ids):
        rebuild_project_old_fields(con, pid)
        proj = con.execute("SELECT id, name, coordinator, owners, collaborators FROM projects WHERE id = :pid",
                           {"pid": pid}).fetchone()
        print(f"  项目 id={pid}, name='{proj['name']}': "
              f"coordinator='{proj['coordinator']}', owners='{proj['owners']}', "
              f"collaborators='{proj['collaborators']}'")

    con.commit()
    print("\n[完成] 修复已提交。")

    # ── 5. 修复后验证 ────────────────────────────────────────────
    remaining = find_orphans(con)
    if remaining:
        print(f"\n[警告] 修复后仍有 {len(remaining)} 条孤儿记录（未能自动匹配）:")
        for r in remaining:
            print(f"  id={r['id']}, person_id={r['person_id']}, name='{r['person_name_snapshot']}'")
    else:
        print("\n[验证通过] 修复后无孤儿 project_members 记录。")

    con.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""
一次性迁移脚本：将 people.system_role 从旧中文值迁移为英文键。

用法：
  python scripts/migrate_system_role_keys.py --dry-run   # 预览
  python scripts/migrate_system_role_keys.py --apply     # 执行

特性：
  - 幂等：已迁移的值不会被重复处理
  - 安全：遇到无法识别的 system_role 时停止 apply
  - 同步：apply 后自动同步 people.is_admin 和 accounts.is_tech_admin
  - 不改数据库结构
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.database import engine
from app.permissions import (
    ROLE_CEO,
    ROLE_SUPER_ADMIN,
    ROLE_NORMAL,
    SYSTEM_ROLE_LABELS,
    _LEGACY_SYSTEM_ROLE_VALUES,
    _ALL_VALID_ROLE_KEYS,
    normalize_system_role,
)


def get_role_distribution():
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT system_role, COUNT(*) FROM people "
                "GROUP BY system_role ORDER BY COUNT(*) DESC"
            )
        ).fetchall()
    return [(row[0], row[1]) for row in rows]


def get_migration_records():
    """返回 (to_migrate, unrecognized, already_done)"""
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, name, system_role FROM people ORDER BY id")
        ).fetchall()

    to_migrate: list[tuple] = []
    unrecognized: list[tuple] = []
    already_done: list[tuple] = []

    for row in rows:
        pid, name, old_role = row[0], row[1], row[2] or ""
        if old_role in _ALL_VALID_ROLE_KEYS:
            already_done.append((pid, name, old_role))
            continue
        new_role = normalize_system_role(old_role)
        if new_role and new_role != old_role:
            to_migrate.append((pid, name, old_role, new_role))
        else:
            unrecognized.append((pid, name, old_role))

    return to_migrate, unrecognized, already_done


def print_distribution():
    dist = get_role_distribution()
    print("\n=== people.system_role ===")
    if not dist:
        print("  (table empty)")
        return
    for role, count in dist:
        label = SYSTEM_ROLE_LABELS.get(role, "(unknown)")
        marker = "OK " if role in _ALL_VALID_ROLE_KEYS else "!! "
        print(f"  {marker} {role or '(empty)':<20} {label:<12} {count}")


def print_preview(to_migrate, unrecognized, already_done):
    print(f"\n=== summary ===")
    print(f"  already english key : {len(already_done)}")
    print(f"  to migrate          : {len(to_migrate)}")
    print(f"  unrecognized        : {len(unrecognized)}")

    if to_migrate:
        print(f"\n--- to migrate ---")
        for pid, name, old_role, new_role in to_migrate:
            print(f"  id={pid:<6} name={name:<12} {old_role!r} -> {new_role!r}")

    if unrecognized:
        print(f"\n--- unrecognized (blocks apply) ---")
        for pid, name, old_role in unrecognized:
            print(f"  id={pid:<6} name={name:<12} system_role={old_role!r}")


def apply_migration(to_migrate, unrecognized):
    if unrecognized:
        print(f"\nERROR: {len(unrecognized)} unrecognized system_role value(s). Apply aborted.")
        print("Fix them manually and retry.")
        return False

    if not to_migrate:
        print("\nNothing to migrate — all records already use english keys.")
        return True

    print(f"\n=== applying ({len(to_migrate)} records) ===")
    with engine.begin() as conn:
        for pid, name, old_role, new_role in to_migrate:
            conn.execute(
                text("UPDATE people SET system_role = :new WHERE id = :pid"),
                {"new": new_role, "pid": pid},
            )
            print(f"  id={pid:<6} name={name:<12} {old_role!r} -> {new_role!r}  OK")

        print("\n--- sync people.is_admin ---")
        conn.execute(
            text("UPDATE people SET is_admin = 1 WHERE system_role = :sa"),
            {"sa": ROLE_SUPER_ADMIN},
        )
        conn.execute(
            text("UPDATE people SET is_admin = 0 WHERE system_role != :sa"),
            {"sa": ROLE_SUPER_ADMIN},
        )
        print("  people.is_admin synced")

        print("\n--- sync accounts.is_tech_admin ---")
        r1 = conn.execute(
            text(
                "UPDATE accounts SET is_tech_admin = 1 "
                "WHERE person_id IN (SELECT id FROM people WHERE system_role = :sa)"
            ),
            {"sa": ROLE_SUPER_ADMIN},
        )
        print(f"  set admin   : {r1.rowcount} accounts")
        r2 = conn.execute(
            text(
                "UPDATE accounts SET is_tech_admin = 0 "
                "WHERE person_id IN (SELECT id FROM people WHERE system_role != :sa)"
            ),
            {"sa": ROLE_SUPER_ADMIN},
        )
        print(f"  unset admin : {r2.rowcount} accounts")

    print("\nMigration done.")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Migrate people.system_role to english keys"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="preview only")
    group.add_argument("--apply", action="store_true", help="execute migration")
    args = parser.parse_args()

    print_distribution()

    to_migrate, unrecognized, already_done = get_migration_records()
    print_preview(to_migrate, unrecognized, already_done)

    if args.dry_run:
        print("\n[dry-run] No changes made. Use --apply to execute.")
        return

    if args.apply:
        ok = apply_migration(to_migrate, unrecognized)
        if ok:
            print_distribution()


if __name__ == "__main__":
    main()

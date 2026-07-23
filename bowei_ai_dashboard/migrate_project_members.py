# -*- coding: utf-8 -*-
"""
数据迁移：将 projects 旧字符串字段中的成员信息同步到 project_members 表，
并将完全没有项目归属的人员自动添加到系统中唯一或主要的项目中。

用法:
    cd bowei_ai_dashboard && .venv\\Scripts\\python.exe migrate_project_members.py
    （默认 dry_run=False，加 --dry-run 可预览不写入）
"""
import os, sys, io, re, argparse
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.database import SessionLocal
from app import models


def _split_names(value) -> list[str]:
    if isinstance(value, list):
        source = "、".join(str(item or "").strip() for item in value if str(item or "").strip())
    else:
        source = str(value or "").strip()
    if not source:
        return []
    return [item.strip() for item in re.split(r"[,，、/;\n]+", source) if item.strip()]


def migrate(dry_run: bool = True):
    db = SessionLocal()
    try:
        people = db.query(models.Person).all()
        people_by_name = {p.name: p for p in people}
        projects = db.query(models.Project).all()

        existing = db.query(models.ProjectMember).all()
        pm_lookup = set()
        for m in existing:
            pm_lookup.add((m.project_id, m.person_id, m.role))

        # ── Step 1: 从旧字段迁移到 project_members ──
        print("=" * 70)
        print("Step 1: 旧字段 -> project_members")
        print("=" * 70)

        new_members = []
        for proj in projects:
            for person_name in _split_names(proj.owners or ""):
                p = people_by_name.get(person_name)
                if not p:
                    continue
                if (proj.id, p.id, "owner") not in pm_lookup:
                    new_members.append((proj, p, "owner"))
                    print(f"  + [{proj.id}] {proj.name} / {person_name} / owner")

            for person_name in _split_names(proj.collaborators or ""):
                p = people_by_name.get(person_name)
                if not p:
                    continue
                if (proj.id, p.id, "member") not in pm_lookup:
                    new_members.append((proj, p, "member"))
                    print(f"  + [{proj.id}] {proj.name} / {person_name} / member")

            coord = (proj.coordinator or "").strip()
            if coord and coord in people_by_name:
                p = people_by_name[coord]
                if (proj.id, p.id, "coordinator") not in pm_lookup:
                    new_members.append((proj, p, "coordinator"))
                    print(f"  + [{proj.id}] {proj.name} / {coord} / coordinator")

        # ── Step 2: 无项目归属人员 -> 加到主要项目 ──
        pm_pids = {m.person_id for m in existing}
        no_project = [p for p in people if p.id not in pm_pids]
        # Also include people we just added in step 1
        for proj, p, role in new_members:
            no_project = [np for np in no_project if np.id != p.id]

        print(f"\n{'=' * 70}")
        print(f"Step 2: {len(no_project)} 个无项目人员 -> 自动分配到唯一项目")
        print("=" * 70)

        # 策略：如果只有一个非归档项目，全部加进去
        active_projects = [p for p in projects if getattr(p, 'status', None) != 'archived']
        if not active_projects:
            active_projects = projects

        if active_projects:
            # 优先把所有无项目人员加到第一个可用项目中
            # 如果有多个项目，加到最后修改的那个
            target_proj = sorted(active_projects, key=lambda p: getattr(p, 'updated_at', p.id) or p.id)[-1]
            for p in no_project:
                if (target_proj.id, p.id, "member") not in pm_lookup:
                    new_members.append((target_proj, p, "member"))
                    print(f"  + [{target_proj.id}] {target_proj.name} / {p.name} / member (auto-assign)")
        else:
            print("  (无可用项目，跳过)")

        # ── 写入 ──
        print(f"\n{'=' * 70}")
        print(f"共需新增 {len(new_members)} 条 project_members 记录")
        if dry_run:
            print("[DRY RUN] 未写入数据库。去掉 --dry-run 后执行。")
        else:
            for proj, p, role in new_members:
                db.add(models.ProjectMember(
                    project_id=proj.id,
                    person_id=p.id,
                    person_name_snapshot=p.name,
                    role=role,
                ))
            db.commit()
            print("迁移完成！")

        return len(new_members)

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不写入")
    args = parser.parse_args()
    migrate(dry_run=args.dry_run)

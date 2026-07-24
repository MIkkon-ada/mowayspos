#!/usr/bin/env python3
"""
SQLite → PostgreSQL 数据迁移脚本。

用法：
  1. 将本地 SQLite db 文件上传到 CVM：
     scp bowei_ai_dashboard.db root@<CVM_IP>:/tmp/local.db

  2. 在 CVM 上执行：
     sudo docker cp /tmp/local.db mowayspos-backend:/tmp/local.db
     sudo docker exec mowayspos-backend python /tmp/migrate_sqlite_to_postgres.py /tmp/local.db

注意：
  - 目标 PostgreSQL 在 Docker 网络内，主机名 postgres，端口 5432
  - 连接信息从环境变量读取（与 backend 容器一致）
  - 会清空目标表后重新插入（幂等）
  - auth_sessions 和 login_attempts 不迁移（临时数据）
"""

import sqlite3
import os
import sys
import json
from datetime import datetime

# ── PostgreSQL 驱动 ──────────────────────────────────────────────
try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("安装 psycopg2...")
    os.system("pip install psycopg2-binary -q")
    import psycopg2
    import psycopg2.extras


# ── 配置 ──────────────────────────────────────────────────────────
def get_pg_url():
    """从环境变量构建 PostgreSQL 连接 URL。"""
    pg_user = os.environ.get("POSTGRES_USER", "mowayspos")
    pg_pass = os.environ.get("DB_PASSWORD", "")
    pg_host = os.environ.get("POSTGRES_HOST", "postgres")  # Docker 内部主机名
    pg_port = os.environ.get("POSTGRES_PORT", "5432")
    pg_db = os.environ.get("POSTGRES_DB", "mowayspos")
    return f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"


# ── 表定义（按依赖顺序排列） ─────────────────────────────────────
# 每个表：(表名, 排除字段列表, 是否需要重置序列)
TABLES = [
    # 无外键依赖的基础表
    ("people", [], True),
    ("accounts", [], True),
    ("projects", [], True),
    ("platform_settings", [], False),  # 单行 id=1

    # 依赖 people / projects
    ("project_members", [], True),
    ("tasks", ["owner_id"], True),      # owner_id FK 可能引用不存在的 people

    # 依赖 tasks
    ("subtasks", ["assignee_id"], True),
    ("subtask_drafts", ["assignee_id"], True),

    # 依赖多张表
    ("update_submission_batches", ["submitter_id"], True),
    ("update_submissions",
     ["submitter_id", "related_task_id", "related_subtask_id"], True),
    ("achievements", ["owner_id", "related_task_id", "related_subtask_id"], True),
    ("achievement_submissions",
     ["submitter_id", "related_task_id", "related_subtask_id"], True),
    ("issues", ["owner_id", "related_task_id", "related_subtask_id"], True),

    ("meetings", [], True),
    ("project_close_requests", ["requester_person_id", "reviewer_person_id"], True),
    ("member_change_requests",
     ["requester_person_id", "target_person_id", "reviewer_person_id"], True),
    ("notifications", ["recipient_id"], True),
    ("operation_logs", [], True),

    # 不迁移的临时表
    # auth_sessions, login_attempts
]

SKIP_TABLES = {"auth_sessions", "login_attempts"}


# ── 类型转换 ──────────────────────────────────────────────────────
def convert_value(val, col_type):
    """将 SQLite 值转换为 PostgreSQL 兼容格式。"""
    if val is None:
        return None

    # Boolean: SQLite 存 0/1，PostgreSQL 要 true/false
    if col_type and "boolean" in col_type.lower():
        if isinstance(val, int):
            return bool(val)
        if isinstance(val, str):
            return val.lower() in ("1", "true", "yes")

    # DateTime: ISO 格式字符串
    if isinstance(val, datetime):
        return val.isoformat()

    # JSON/Text 字段原样传
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)

    return val


# ── 主流程 ────────────────────────────────────────────────────────
def migrate(sqlite_path):
    print(f"[1/5] 连接 SQLite: {sqlite_path}")
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    print("[2/5] 连接 PostgreSQL ...")
    pg_url = get_pg_url()
    pg_conn = psycopg2.connect(pg_url)
    pg_conn.autocommit = False
    pg_cur = pg_conn.cursor()

    total_rows = 0
    total_tables = 0

    try:
        for table_name, exclude_cols, reset_seq in TABLES:
            if table_name in SKIP_TABLES:
                continue

            print(f"\n  迁移表: {table_name} ...", end=" ", flush=True)

            # 获取 SQLite 表结构
            sqlite_cur.execute(f'PRAGMA table_info("{table_name}")')
            columns_info = sqlite_cur.fetchall()
            col_names = [col[1] for col in columns_info]
            col_types = {col[1]: col[2] for col in columns_info}

            # 过滤排除的字段
            target_cols = [c for c in col_names if c not in exclude_cols and c != "rowid"]
            if not target_cols:
                print("跳过（无有效列）")
                continue

            # 读取所有数据
            placeholders = ", ".join(["?" for _ in target_cols])
            sqlite_cur.execute(f'SELECT {", ".join(target_cols)} FROM "{table_name}"')
            rows = sqlite_cur.fetchall()

            if not rows:
                print(f"0 行（空表）")
                continue

            # 清空目标表（按正确的外键顺序，此时应该安全）
            pg_cur.execute(f'TRUNCATE TABLE "{table_name}" CASCADE')

            # 批量插入
            inserted = 0
            for row in rows:
                values = []
                for i, col in enumerate(target_cols):
                    val = row[i]
                    col_type = col_types.get(col, "")
                    values.append(convert_value(val, col_type))

                cols_str = ", ".join(f'"{c}"' for c in target_cols)
                placeholders_str = ", ".join(["%s" for _ in target_cols])
                try:
                    pg_cur.execute(
                        f'INSERT INTO "{table_name}" ({cols_str}) VALUES ({placeholders_str})',
                        values,
                    )
                    inserted += 1
                except Exception as e:
                    # 单行失败不中断，记录并继续
                    row_id = row[0] if row else "?"
                    print(f"\n    ⚠ 行 id={row_id} 跳过: {e}")

            # 重置自增序列
            if reset_seq and inserted > 0:
                try:
                    pg_cur.execute(
                        f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
                        f"COALESCE((SELECT MAX(id) FROM \"{table_name}\"), 1))"
                    )
                except Exception:
                    pass  # 序列不存在时忽略

            total_rows += inserted
            total_tables += 1
            print(f"{inserted} 行 ✓")

        pg_conn.commit()
        print(f"\n[3/5] ✓ 迁移完成！共 {total_tables} 张表, {total_rows} 行数据")

    except Exception as e:
        pg_conn.rollback()
        print(f"\n✗ 迁移失败: {e}")
        raise
    finally:
        sqlite_cur.close()
        sqlite_conn.close()
        pg_cur.close()
        pg_conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"用法: {sys.argv][0]} <sqlite_db_path>")
        print(f"示例: {sys.argv][0]} /tmp/local.db")
        sys.exit(1)

    migrate(sys.argv[1])

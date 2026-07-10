# -*- coding: utf-8 -*-
"""
备份 SQLite 数据库（含 WAL 模式正确处理）。

使用 sqlite3.backup() API，确保 WAL 中已提交的事务也被完整复制到备份文件。
备份文件名带时间戳，避免覆盖。
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

SRC = Path(__file__).resolve().parent / "bowei_ai_dashboard.db"
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
DST = Path(__file__).resolve().parent / f"_backup_db_{TS}.db"

if not SRC.exists():
    print(f"[ERROR] 源数据库不存在: {SRC}")
    sys.exit(1)

src = sqlite3.connect(str(SRC))
dst = sqlite3.connect(str(DST))
try:
    # WAL checkpoint 后再 backup，确保数据完整
    src.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    src.backup(dst)
    dst.commit()
    print(f"[OK] 数据库已备份到: {DST}")
    print(f"     源文件大小: {SRC.stat().st_size} bytes")
    print(f"     备份大小:   {DST.stat().st_size} bytes")
finally:
    src.close()
    dst.close()

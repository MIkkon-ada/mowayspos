from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from .database_safety import (
    ensure_application_target_allowed,
    normalize_database_target,
    require_database_url,
)


_raw_database_url = require_database_url()
_database_target = normalize_database_target(_raw_database_url)
ensure_application_target_allowed(_raw_database_url)
SQLALCHEMY_DATABASE_URL = _database_target.engine_url

_is_sqlite = _database_target.kind == "sqlite"

connect_args = {}
if _is_sqlite:
    # timeout=20: 等待锁释放最多 20 秒，避免并发写入时过早报 SQLITE_BUSY（默认 5 秒）
    connect_args = {"check_same_thread": False, "timeout": 20}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=3600,
)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _record):
        # WAL 模式允许读写并发，避免读操作阻塞写操作
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

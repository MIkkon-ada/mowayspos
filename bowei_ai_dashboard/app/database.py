import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SQLITE_URL = f"sqlite:///{BASE_DIR / 'bowei_ai_dashboard.db'}"

SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    DEFAULT_SQLITE_URL,
)

_is_sqlite = SQLALCHEMY_DATABASE_URL.startswith("sqlite")

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

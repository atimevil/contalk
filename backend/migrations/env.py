"""
Alembic 환경 설정.

- asyncpg 드라이버를 사용하는 async SQLAlchemy 엔진을 지원한다.
- DATABASE_URL 환경변수가 있으면 alembic.ini 설정을 오버라이드한다.
"""
import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ─── 모든 모델을 import 해야 target_metadata 에 반영된다 ─────────────────────
from app.core.database import Base  # noqa: F401 — Base 임포트
import app.models.user              # noqa: F401
import app.models.contract          # noqa: F401
import app.models.payment           # noqa: F401
import app.models.quota             # noqa: F401
import app.models.special_clause    # noqa: F401

# ─── Alembic Config 오브젝트 ─────────────────────────────────────────────────
config = context.config

# logging.ini 스타일 설정 적용
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 마이그레이션 대상 메타데이터
target_metadata = Base.metadata

# ─── DATABASE_URL 환경변수 오버라이드 ────────────────────────────────────────
db_url = os.environ.get("DATABASE_URL")
if db_url:
    # asyncpg URL 그대로 사용 (Alembic 1.12+ 지원)
    config.set_main_option("sqlalchemy.url", db_url)


# ─── 오프라인 마이그레이션 (SQL 스크립트 생성용) ───────────────────────────
def run_migrations_offline() -> None:
    """오프라인 모드: DB 연결 없이 SQL 스크립트를 생성한다."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ─── 온라인 마이그레이션 (실제 DB에 적용) ────────────────────────────────────
def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """비동기 엔진으로 마이그레이션을 실행한다."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """온라인 모드: 실제 DB에 마이그레이션을 적용한다."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

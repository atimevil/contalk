from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from app.core.config import settings

# SQLite는 pool_size/max_overflow를 지원하지 않으므로 조건부 적용
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
_engine_kwargs: dict = {"echo": not settings.is_production}
if not _is_sqlite:
    _engine_kwargs["pool_size"] = settings.DATABASE_POOL_SIZE
    _engine_kwargs["max_overflow"] = settings.DATABASE_MAX_OVERFLOW

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def make_celery_session() -> async_sessionmaker:
    """
    Celery 태스크 전용 세션 팩토리.

    NullPool을 사용하여 asyncio 이벤트 루프가 교체될 때
    커넥션 재사용 문제를 완전히 차단한다.

    Celery 태스크는 asyncio.run()을 호출할 때마다 새 이벤트 루프를 만드는데,
    일반 QueuePool은 첫 번째 루프에 묶인 커넥션을 보관해 두 번째 호출 시 충돌한다.
    NullPool은 커넥션을 보관하지 않고 매번 새로 생성·즉시 폐기하므로 안전하다.
    """
    _engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    return async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

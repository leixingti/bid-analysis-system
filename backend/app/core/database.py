"""数据库配置 — 异步引擎 + 连接池"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

engine = create_async_engine(
    settings.get_async_database_url(),
    echo=settings.DEBUG,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=300,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """初始化数据库：创建新表 + 迁移已有表"""
    import logging
    _logger = logging.getLogger(__name__)

    # 1. 创建所有新表（对已存在的表无影响）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. 执行增量迁移（给已有表加新列）
    try:
        from app.core.migration import run_migration
        async with engine.connect() as conn:
            await run_migration(conn)
    except Exception as e:
        _logger.warning(f"⚠️ Migration skipped: {e}")

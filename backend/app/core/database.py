from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings
import os

# Build async database URL
database_url = settings.DATABASE_URL

if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif database_url.startswith("postgresql://") and "+asyncpg" not in database_url:
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# For Railway networking, disable SSL
connect_args = {}
if "railway" in database_url and "sslmode" not in database_url:
    if "?" in database_url:
        database_url += "&ssl=disable"
    else:
        database_url += "?ssl=disable"

# 🔧 优化：配置连接池参数，解决 "connection is closed" 问题
engine = create_async_engine(
    database_url,
    echo=settings.DEBUG,
    pool_size=5,              # 连接池大小
    max_overflow=10,          # 超出pool_size时最多再建10个连接
    pool_timeout=30,          # 获取连接超时（秒）
    pool_recycle=300,         # 每5分钟回收连接（避免数据库断开闲置连接）
    pool_pre_ping=True,       # 🔧 关键：每次使用前先ping检测连接是否存活
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

import asyncio
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    async_scoped_session,
    AsyncSession as _AsyncSession,
)
from sqlalchemy.orm import declarative_base
from .config import DATABASE_URL
from .logger import logger

class AsyncSession(_AsyncSession):
    """
    自定义 AsyncSession，优化事务处理
    """
    def begin(self):
        if not self.in_transaction():
            return super().begin()
        else:
            return self.begin_nested()

# 创建异步引擎
# 注意：DATABASE_URL 必须以 postgresql+asyncpg:// 开头
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600,
)

# 创建 scoped session
# 使用 asyncio.current_task 确保在同一个协程任务中共享 session
async_session = async_scoped_session(
    async_sessionmaker(
        bind=engine, 
        expire_on_commit=False, 
        class_=AsyncSession
    ),
    scopefunc=asyncio.current_task,
)

# 声明式基类，所有数据库模型应继承自此基类
Base = declarative_base()

async def init_db():
    """
    初始化数据库，创建所有已定义的表
    """
    if not DATABASE_URL:
        logger.warning("DATABASE_URL 未配置，跳过数据库初始化。")
        return

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库初始化完成。")
    except Exception as e:
        logger.error(f"数据库初始化过程中发生错误: {e}")
        # 在关键核心组件初始化失败时，通常建议抛出异常以阻止程序在错误状态下运行
        raise e

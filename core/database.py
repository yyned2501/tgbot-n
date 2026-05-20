import asyncio
import os
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    async_scoped_session,
    AsyncSession as _AsyncSession,
)
from sqlalchemy import select, text
from .config import DATABASE_URL
from .logger import logger
from .models import Base, SystemSetting

class AsyncSession(_AsyncSession):
    """
    自定义 AsyncSession，优化事务处理
    """
    def begin(self):
        if not self.in_transaction():
            return super().begin()
        else:
            return self.begin_nested()

# 状态变量
_is_initialized = False
_is_using_sqlite = False

# 创建初始异步引擎 (可能在 init_db 中被替换)
engine = create_async_engine(
    DATABASE_URL or "sqlite+aiosqlite:///data.db",
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600,
) if DATABASE_URL else create_async_engine("sqlite+aiosqlite:///data.db")

# 创建 session 工厂
_session_factory = async_sessionmaker(
    bind=engine, 
    expire_on_commit=False, 
    class_=AsyncSession
)

# 创建 scoped session
async_session = async_scoped_session(
    _session_factory,
    scopefunc=asyncio.current_task,
)

async def get_setting(key: str, default: str = "") -> str:
    """
    获取系统设置
    """
    async with async_session() as session:
        try:
            result = await session.execute(select(SystemSetting).where(SystemSetting.key == key))
            setting = result.scalar_one_or_none()
            return setting.value if setting else default
        except Exception:
            return default

async def set_setting(key: str, value: str):
    """
    保存系统设置
    """
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(select(SystemSetting).where(SystemSetting.key == key))
            setting = result.scalar_one_or_none()
            if setting:
                setting.value = value
            else:
                setting = SystemSetting(key=key, value=value)
                session.add(setting)

async def migrate_from_sqlite():
    """
    从本地 SQLite 迁移数据到当前数据库 (主库)
    """
    global _is_using_sqlite
    if _is_using_sqlite:
        return

    sqlite_path = "data.db"
    if not os.path.exists(sqlite_path):
        return

    logger.info("检测到本地 SQLite 数据库，准备迁移数据到主数据库...")
    sqlite_url = f"sqlite+aiosqlite:///{sqlite_path}"
    sqlite_engine = create_async_engine(sqlite_url)
    
    try:
        async with sqlite_engine.connect() as sqlite_conn:
            # 1. 迁移 system_settings
            try:
                result = await sqlite_conn.execute(text("SELECT key, value FROM system_settings"))
                rows = result.all()
                if rows:
                    async with async_session() as session:
                        async with session.begin():
                            for key, value in rows:
                                # Upsert 逻辑
                                res = await session.execute(select(SystemSetting).where(SystemSetting.key == key))
                                setting = res.scalar_one_or_none()
                                if setting:
                                    setting.value = value
                                else:
                                    session.add(SystemSetting(key=key, value=value))
                    logger.info(f"已迁移 {len(rows)} 条系统设置。")
            except Exception as e:
                logger.warning(f"迁移 system_settings 失败 (可能表不存在): {e}")

        # 迁移完成后重命名文件
        # 注意：在 Windows 上，如果有连接未关闭，重命名会失败
        await sqlite_engine.dispose()
        try:
            os.rename(sqlite_path, f"{sqlite_path}.bak")
            logger.info(f"数据迁移完成，原数据库已重命名为 {sqlite_path}.bak")
        except Exception as e:
            logger.error(f"重命名 SQLite 文件失败 (请手动处理): {e}")
            
    except Exception as e:
        logger.error(f"数据迁移过程中发生错误: {e}")
    finally:
        await sqlite_engine.dispose()

async def init_db():
    """
    初始化数据库，包含降级和迁移逻辑
    """
    global engine, _session_factory, _is_initialized, _is_using_sqlite
    
    # 导入所有模型以确保它们被注册到 Base.metadata
    from .models import ZhuqueResult, BonusLog

    if _is_initialized:
        # 如果已经初始化过，只需确保表结构同步
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            return
        except Exception as e:
            logger.error(f"二次同步表结构失败: {e}")
            return

    use_sqlite = False
    if not DATABASE_URL:
        logger.warning("DATABASE_URL 未配置，将使用本地 SQLite。")
        use_sqlite = True
    else:
        try:
            # 尝试连接主数据库
            # 使用新的临时引擎测试连接，避免污染全局引擎
            test_engine = create_async_engine(DATABASE_URL)
            async with test_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await test_engine.dispose()
            logger.info("成功连接到主数据库。")
        except Exception as e:
            logger.error(f"无法连接到主数据库: {e}。正在切换到本地 SQLite...")
            use_sqlite = True

    if use_sqlite:
        sqlite_url = "sqlite+aiosqlite:///data.db"
        engine = create_async_engine(sqlite_url)
        _session_factory.configure(bind=engine)
        _is_using_sqlite = True
        logger.info("已切换至本地 SQLite 数据库。")
    else:
        # 如果连接主库成功，尝试从 SQLite 迁移数据
        await migrate_from_sqlite()

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库表结构同步完成。")
        _is_initialized = True
    except Exception as e:
        logger.error(f"数据库初始化过程中发生错误: {e}")
        if not use_sqlite:
            logger.warning("主库初始化失败，尝试强制切换到 SQLite...")
            engine = create_async_engine("sqlite+aiosqlite:///data.db")
            _session_factory.configure(bind=engine)
            _is_using_sqlite = True
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            _is_initialized = True
        else:
            raise e

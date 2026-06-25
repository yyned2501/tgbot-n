import asyncio
import os
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    async_scoped_session,
    AsyncSession as _AsyncSession,
)
from sqlalchemy import select, text, delete
from .config import DATABASE_URL
from .logger import logger
from .models import Base, SystemSetting, UserAccount

# 全局写入锁：序列化跨协程的写操作，防止多账号/多任务并发写入导致的数据重复
# 用法: async with write_lock: ...
write_lock = asyncio.Lock()

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

async def delete_setting(key: str):
    """
    删除系统设置
    """
    async with async_session() as session:
        async with session.begin():
            await session.execute(delete(SystemSetting).where(SystemSetting.key == key))

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

async def migrate_session_to_account():
    """
    将旧版 system_settings 中的 session_string 迁移到 UserAccount 表
    """
    session_str = await get_setting("session_string", "")
    if not session_str:
        return  # 没有旧数据，无需迁移

    owner_id_str = await get_setting("owner_id", "0")
    owner_id = int(owner_id_str) if owner_id_str and owner_id_str != "0" else 0

    if not owner_id:
        logger.warning("发现旧版 session_string 但 owner_id 未设置，无法迁移")
        return

    # 检查是否已迁移过（UserAccount 表中是否已有该 owner_id）
    async with async_session() as session:
        result = await session.execute(
            select(UserAccount).where(UserAccount.owner_id == owner_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            logger.info("UserAccount 已存在，跳过迁移")
            # 仍然删除旧 session_string 防止重复
            await delete_setting("session_string")
            return

        # 创建 UserAccount 记录
        account = UserAccount(
            owner_id=owner_id,
            phone="migrated",
            session_string=session_str,
            is_active=True,
            is_connected=False,
        )
        session.add(account)
        await session.commit()

    # 迁移完成后删除旧 session_string
    await delete_setting("session_string")
    logger.info(f"✅ 已成功将旧版 session_string 迁移到 UserAccount (owner_id={owner_id})")


async def init_db():
    """
    初始化数据库，包含降级和迁移逻辑
    """
    global engine, _session_factory, _is_initialized, _is_using_sqlite
    
    # 导入所有模型以确保它们被注册到 Base.metadata
    from .models import ZhuqueResult, BonusLog, UserAccount

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

        # 清理 zhuque_results 中的重复记录，然后创建唯一索引
        # （已有重复数据会阻止 CREATE UNIQUE INDEX，必须先清理）
        try:
            async with engine.begin() as conn:
                # 删除重复行：保留每个 created_at 中 id 最小的那条
                await conn.execute(
                    text(
                        "DELETE FROM zhuque_results WHERE id NOT IN "
                        "(SELECT MIN(id) FROM zhuque_results GROUP BY created_at)"
                    )
                )
                # 现在可以安全创建唯一索引
                await conn.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS "
                        "idx_zhuque_results_created_at ON zhuque_results(created_at)"
                    )
                )
            logger.info("zhuque_results 唯一索引已就绪。")
        except Exception as e:
            logger.warning(f"zhuque_results 唯一索引创建失败（可能数据库不支持）: {e}")

        _is_initialized = True

        # 迁移旧版 session_string 到 UserAccount
        await migrate_session_to_account()

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
            # 迁移旧版 session_string 到 UserAccount
            await migrate_session_to_account()
        else:
            raise e

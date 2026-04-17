import os
from core import manager, idle, logger, init_db

async def main():
    # 初始化并启动所有客户端 (Userbot & Assistant Bot)
    manager.init_apps()
    
    # 初始化数据库 (此时插件已加载，模型已注册)
    await init_db()
    
    if not manager.user and not manager.bot:
        logger.error("未配置 SESSION_STRING 或 BOT_TOKEN。请检查 config/config.toml。")
        return

    logger.info("人形脚本系统启动中...")
    await manager.start_all()
    
    logger.info("系统已就绪。")
    await manager.send_bot_message("🚀 **人形脚本系统已启动并就绪！**")
    await idle()
    await manager.stop_all()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

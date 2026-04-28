import os
from core import app, db, tg

async def main():
    # 1. 初始化数据库 (仅核心表)
    await db.init_db()
    
    # 2. 从数据库加载动态配置 (owner_id, prefix, session_string)
    await app.manager.load_settings()
    
    # 3. 加载插件模块 (注册插件模型到 Base)
    app.manager.load_plugins()
    
    # 4. 再次同步数据库 (创建插件定义的表)
    await db.init_db()
    
    # 5. 初始化所有客户端实例
    app.manager.init_apps()
    
    if not app.manager.user and not app.manager.bot:
        app.logger.error("未配置 SESSION_STRING 或 BOT_TOKEN。请检查 config/config.toml 或数据库。")
        return

    app.logger.info("人形脚本系统启动中...")
    await app.manager.start_all()
    
    app.logger.info("系统已就绪。")
    await app.manager.send_bot_message("🚀 **人形脚本系统已启动并就绪！**")
    await tg.idle()
    await app.manager.stop_all()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

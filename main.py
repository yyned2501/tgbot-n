"""
主入口 - 多账号人形脚本系统

启动流程:
1. 初始化数据库
2. 加载动态配置
3. 加载插件模块
4. 再次同步数据库
5. 初始化 Assistant Bot
6. 启动 Web 配置面板
7. 启动 Bot 和所有 Userbot 账号
"""
import asyncio
import os
from core import app, db, tg


async def main():
    # 1. 初始化数据库 (仅核心表)
    await db.init_db()

    # 2. 从数据库加载动态配置 (owner_id, prefix)
    await app.manager.load_settings()

    # 3. 加载插件模块 (注册插件模型到 Base)
    app.manager.load_plugins()

    # 4. 再次同步数据库 (创建插件定义的表)
    await db.init_db()

    # 5. 初始化客户端实例 (只初始化 Bot，Userbot 由 account_manager 管理)
    app.manager.init_apps()

    if not app.manager.bot:
        app.logger.error("未配置 BOT_TOKEN。请检查 config/config.toml。")
        return

    # 6. 启动 Web 配置面板（非阻塞，共享事件循环）
    from core.config import CONFIG
    web_port = CONFIG.get("web", {}).get("port", 8080)
    web_host = CONFIG.get("web", {}).get("host", "0.0.0.0")

    try:
        from web.server import start_server
        asyncio.create_task(start_server(host=web_host, port=web_port))
        app.logger.info(f"🌐 Web 配置面板已启动: http://{web_host}:{web_port}")
    except ImportError as e:
        app.logger.warning(f"Web 面板未安装依赖，跳过启动: {e}")
    except Exception as e:
        app.logger.warning(f"Web 面板启动失败: {e}")

    app.logger.info("人形脚本系统启动中...")
    await app.manager.start_all()

    app.logger.info("系统已就绪。")
    await app.manager.send_bot_message(
        f"🚀 **人形脚本系统已启动并就绪！**\n"
        f"🌐 Web 面板: `http://0.0.0.0:{web_port}`"
    )
    await tg.idle()
    await app.manager.stop_all()


if __name__ == "__main__":
    asyncio.run(main())

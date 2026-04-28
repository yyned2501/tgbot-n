from core import tg, app

@tg.Client.bot_command("status", "查看运行状态")
async def status_handler(client: tg.Client, message: tg.Message):
    # 检查是否是 Owner
    if message.from_user.id != app.manager.owner_id:
        await message.reply("❌ 您没有权限执行此操作。")
        return

    user_status = "✅ 运行中" if app.manager.user and app.manager.user.is_connected else "❌ 未启动"
    bot_status = "✅ 运行中" if app.manager.bot and app.manager.bot.is_connected else "❌ 未启动"
    
    status_text = (
        "🤖 **机器人状态报告**\n\n"
        f"👤 **Userbot**: {user_status}\n"
        f"🤖 **Assistant Bot**: {bot_status}\n"
        f"🆔 **Owner ID**: `{app.manager.owner_id}`"
    )
    
    await message.reply(status_text)

@tg.Client.bot_command("help", "显示帮助信息")
async def help_handler(client: tg.Client, message: tg.Message):
    if message.from_user.id != app.manager.owner_id:
        return

    help_text = (
        "🛠️ **Assistant Bot 指令列表**\n\n"
        "/start - 开始交互\n"
        "/login - 登录 Userbot\n"
        "/status - 查看运行状态\n"
        "/settings - 系统设置\n"
        "/userhelp - 查看 Userbot 功能汇总\n"
        "/help - 显示此帮助信息"
    )
    await message.reply(help_text)

@tg.Client.bot_command("userhelp", "查看 Userbot 功能汇总")
async def userhelp_handler(client: tg.Client, message: tg.Message):
    if message.from_user.id != app.manager.owner_id:
        await message.reply("❌ 您没有权限执行此操作。")
        return

    plugin_info = app.manager.get_user_plugin_info()
    if not plugin_info:
        await message.reply("📭 未找到任何 Userbot 插件。")
        return

    # 按模块路径排序
    plugin_info.sort(key=lambda x: x["module"])

    text = "👤 **Userbot 功能汇总**\n\n"
    
    current_category = ""
    for info in plugin_info:
        # 提取分类 (plugins.user.category.name)
        parts = info["module"].split(".")
        category = parts[2] if len(parts) > 3 else "其他"
        
        if category != current_category:
            current_category = category
            text += f"\n📂 **{category.capitalize()}**\n"
        
        status_icon = "✅" if info["enabled"] else "❌"
        text += f"{status_icon} `{app.manager.prefix}{info['name']}` - {info['description']}\n"

    await message.reply(text)

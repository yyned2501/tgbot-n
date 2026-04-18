from core import Client, filters, Message, manager

@Client.bot_command("status", "查看运行状态")
async def status_handler(client: Client, message: Message):
    # 检查是否是 Owner
    if message.from_user.id != manager.owner_id:
        await message.reply("❌ 您没有权限执行此操作。")
        return

    user_status = "✅ 运行中" if manager.user and manager.user.is_connected else "❌ 未启动"
    bot_status = "✅ 运行中" if manager.bot and manager.bot.is_connected else "❌ 未启动"
    
    status_text = (
        "🤖 **机器人状态报告**\n\n"
        f"👤 **Userbot**: {user_status}\n"
        f"🤖 **Assistant Bot**: {bot_status}\n"
        f"🆔 **Owner ID**: `{manager.owner_id}`"
    )
    
    await message.reply(status_text)

@Client.bot_command("help", "显示帮助信息")
async def help_handler(client: Client, message: Message):
    if message.from_user.id != manager.owner_id:
        return

    help_text = (
        "🛠️ **Assistant Bot 指令列表**\n\n"
        "/start - 开始交互\n"
        "/login - 登录 Userbot\n"
        "/status - 查看运行状态\n"
        "/settings - 系统设置\n"
        "/help - 显示此帮助信息"
    )
    await message.reply(help_text)

"""
状态信息插件 — 支持多账号，所有已绑定用户可访问
"""
import asyncio
from core import tg, app


@tg.Client.bot_command("status", "查看运行状态")
async def status_handler(client: tg.Client, message: tg.Message):
    """显示当前用户的系统运行状态"""
    asyncio.create_task(tg.delete_later(message))

    user_id = message.from_user.id
    is_owner = user_id == app.manager.owner_id

    bot_status = "🟢 运行中" if (app.manager.bot and app.manager.bot.is_connected) else "🔴 离线"

    lines = [
        "📊 **系统运行状态**\n",
        f"🤖 **Bot**: {bot_status}",
    ]

    # 显示当前用户自己的账号
    account = app.account_manager.get_account(user_id)
    if account:
        try:
            me = await account.get_me()
            prefix = getattr(account, "_prefix", "") or app.manager.prefix
            lines.append(f"👤 **你的账号**: 🟢 `{user_id}` | {me.first_name or 'N/A'}")
            lines.append(f"⌨️ **你的前缀**: `{prefix}`")
        except Exception:
            lines.append(f"👤 **你的账号**: 🔴 `{user_id}` | 无法获取信息")
    else:
        lines.append("👤 **你的账号**: 未绑定 (发送 /login 绑定)")

    # Owner 额外看到全部账号列表
    if is_owner:
        account_count = app.account_manager.account_count
        lines.append(f"\n👥 **在线账号总数**: {account_count} 个")
        accounts = app.account_manager.get_all_accounts()
        if accounts:
            for oid, acct in accounts.items():
                try:
                    m = await acct.get_me()
                    name = m.first_name or "N/A"
                    uname = f"@{m.username}" if m.username else "无用户名"
                    lines.append(f"  🟢 `{oid}` | {name} | {uname}")
                except Exception:
                    lines.append(f"  🔴 `{oid}` | 无法获取信息")
        lines.append(f"\n🆔 **Owner ID**: `{app.manager.owner_id}`")

    await message.reply("\n".join(lines))


@tg.Client.bot_command("help", "显示帮助信息")
async def help_handler(client: tg.Client, message: tg.Message):
    """显示 Bot 帮助信息（所有用户可访问）"""
    asyncio.create_task(tg.delete_later(message))

    text = (
        "🤖 **人形脚本 - 帮助菜单**\n\n"
        "**Bot 指令:**\n"
        "  /start - 开始交互\n"
        "  /login - 绑定 Telegram 账号\n"
        "  /logout - 解绑当前账号\n"
        "  /accounts - 查看已绑定的账号\n"
        "  /status - 查看运行状态\n"
        "  /settings - 个人设置\n"
        "  /help - 显示此帮助\n"
        "  /userhelp - 查看 Userbot 功能汇总\n\n"
        "**Userbot 指令:**\n"
        "  使用指令前缀 (默认为 `.`) 调用 Userbot 功能。\n"
        "  例如: `.ping`, `.id`"
    )
    await message.reply(text)


@tg.Client.bot_command("userhelp", "查看 Userbot 功能汇总")
async def userhelp_handler(client: tg.Client, message: tg.Message):
    """显示 Userbot 插件功能汇总（所有用户可访问）"""
    asyncio.create_task(tg.delete_later(message))

    plugins_info = app.manager.get_user_plugin_info()

    if not plugins_info:
        await message.reply("📭 没有可用的 Userbot 插件。")
        return

    lines = ["📦 **Userbot 功能汇总**\n"]
    for info in plugins_info:
        status_icon = "✅" if info["enabled"] else "🚫"
        lines.append(
            f"  {status_icon} **{info['name']}**\n"
            f"      {info['description']}\n"
        )

    await message.reply("\n".join(lines))

"""
登录插件 - 支持多账号绑定

流程:
1. 用户发送 /login
2. 输入手机号
3. 输入验证码（支持两步验证）
4. 登录成功后验证身份 (get_me().id == message.from_user.id)
5. 保存到 UserAccount 表并启动 Userbot

权限:
- Bot Owner (第一个绑定的用户): 可以看到所有账号
- 普通用户: 只能绑定自己的账号
"""
import asyncio
from core import tg, db, app
from core.logger import logger


@tg.Client.bot_command("start", "开始交互", filters=tg.filters.private)
async def start_handler(client: tg.Client, message: tg.Message):
    """处理 /start 命令"""
    asyncio.create_task(tg.delete_later(message))

    # 检查是否已绑定账号
    user_id = message.from_user.id if message.from_user else 0
    if user_id and app.account_manager.get_account(user_id):
        await message.reply(
            "✅ 您已经绑定了账号。\n"
            "如需管理账号，请发送 /accounts 查看。"
        )
        return

    await message.reply(
        "🤖 **人形脚本登录辅助机器人**\n\n"
        "请发送 /login 开始绑定您的 Telegram 账号。\n"
        "绑定后，脚本将自动运行您授权的功能。"
    )


@tg.Client.bot_command("login", "登录 Userbot", filters=tg.filters.private)
async def login_handler(client: tg.Client, message: tg.Message):
    """处理 /login 命令 - 多账号登录流程"""
    asyncio.create_task(tg.delete_later(message))

    user_id = message.from_user.id if message.from_user else 0
    if not user_id:
        await message.reply("❌ 无法获取您的用户信息，请重试。")
        return

    chat_id = message.chat.id

    # 检查是否已绑定
    existing = app.account_manager.get_account(user_id)
    if existing:
        await message.reply(
            "✅ 您已经绑定了账号。\n"
            "如需重新绑定，请先发送 /logout 解绑当前账号。"
        )
        return

    # 1. 询问手机号
    ask_phone = await client.ask(
        chat_id, "📱 请输入您的手机号 (带国家代码，例如 +861234567890):"
    )
    if not ask_phone or not ask_phone.text:
        return
    phone_number = ask_phone.text.strip()

    try:
        # 2. 发送验证码
        temp_client = tg.Client(
            f"temp_login_{user_id}",
            api_id=app.API_ID,
            api_hash=app.API_HASH,
            in_memory=True,
        )
        await temp_client.connect()

        code_info = await temp_client.send_code(phone_number)
        phone_code_hash = code_info.phone_code_hash

        # 3. 询问验证码
        ask_code = await client.ask(chat_id, "验证码已发送，请输入：")
        if not ask_code or not ask_code.text:
            await temp_client.disconnect()
            return
        verification_code = ask_code.text.strip()

        try:
            # 4. 尝试登录
            await temp_client.sign_in(
                phone_number, phone_code_hash, verification_code
            )
        except Exception as e:
            # 处理需要二次验证的情况
            if "SESSION_PASSWORD_NEEDED" in str(e):
                ask_pwd = await client.ask(
                    chat_id, "🔐 检测到两步验证，请输入密码："
                )
                if not ask_pwd or not ask_pwd.text:
                    await temp_client.disconnect()
                    return
                password = ask_pwd.text.strip()
                await temp_client.check_password(password)
            else:
                raise e

        # 5. 获取登录后的用户信息（身份验证）
        me = await temp_client.get_me()

        # 6. **关键验证**：登录的账号 ID 必须与发消息的用户 ID 一致
        if me.id != user_id:
            error_msg = (
                "❌ **身份验证失败！**\n\n"
                f"您登录的账号 ID (`{me.id}`) 与当前 Telegram 账号 (`{user_id}`) 不匹配。\n\n"
                "请使用您当前 Telegram 账号对应的手机号重新登录。"
            )
            await message.reply(error_msg)
            await temp_client.disconnect()
            return

        # 7. 获取 Session String
        session_string = await temp_client.export_session_string()
        await temp_client.disconnect()

        # 8. 保存账号并启动 Userbot
        await message.reply(
            "✅ 登录成功！正在为您启动人形脚本..."
        )

        # 使用 account_manager 添加账号
        success = await app.account_manager.add_account(
            owner_id=me.id,
            session_string=session_string,
            phone=phone_number,
        )

        if success:
            # 如果是第一个绑定的账号，自动设为 Bot Owner
            if not app.manager.owner_id:
                await app.manager.set_owner_id(me.id)
                logger.info(f"已将 {me.id} 设为 Bot Owner (首个绑定账号)")

            prefix = app.manager.prefix
            success_msg = (
                "✅ **人形脚本已成功启动！**\n\n"
                f"🆔 **账号 ID**: `{me.id}`\n"
                f"👤 **用户名**: @{me.username or 'N/A'}\n"
                f"📱 **手机号**: `{phone_number}`\n"
                f"⌨️ **指令前缀**: `{prefix}`\n\n"
                "您现在可以开始使用它了。"
            )
            await message.reply(success_msg)
        else:
            await message.reply(
                "❌ 启动失败，但 Session 已保存。\n"
                "请稍后重试或联系管理员。"
            )

    except Exception as e:
        logger.exception(f"[{user_id}] 登录过程中出现异常")
        await message.reply(f"❌ 登录失败：{str(e)}")

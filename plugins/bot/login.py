import asyncio
from core import tg, db, app
from plugins.bot.settings import send_settings_menu

@tg.Client.bot_command("start", "开始交互", filters=tg.filters.private)
async def start_handler(client: tg.Client, message: tg.Message):
    # 60秒后自动删除指令消息
    asyncio.create_task(tg.delete_later(message))
    
    # 如果已登录，直接显示设置菜单
    if app.manager.session_string:
        await send_settings_menu(message)
        return
        
    # 只有 Assistant Bot 才会加载这个插件
    await message.reply("你好！我是登录辅助机器人。\n请发送 /login 开始获取 Session String 并启动人形脚本。")

@tg.Client.bot_command("login", "登录 Userbot", filters=tg.filters.private)
async def login_handler(client: tg.Client, message: tg.Message):
    # 60秒后自动删除指令消息
    asyncio.create_task(tg.delete_later(message))
    
    # 如果已登录，提示用户
    if app.manager.session_string:
        await message.reply("✅ 您已经登录过了。\n如需退出或切换账号，请前往 /settings 进行退出登录操作。")
        return

    chat_id = message.chat.id
    
    # 1. 询问手机号
    ask_phone = await client.ask(chat_id, "请输入你的手机号 (带国家代码，例如 +861234567890):")
    if not ask_phone or not ask_phone.text:
        return
    phone_number = ask_phone.text.strip()

    try:
        # 2. 发送验证码
        # 使用 in_memory=True 且不使用 ":memory:" 字符串作为名称
        temp_client = tg.Client("temp_login_session", api_id=app.API_ID, api_hash=app.API_HASH, in_memory=True)
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
            await temp_client.sign_in(phone_number, phone_code_hash, verification_code)
        except Exception as e:
            # 处理需要二次验证的情况
            if "SESSION_PASSWORD_NEEDED" in str(e):
                ask_pwd = await client.ask(chat_id, "检测到两步验证，请输入密码：")
                if not ask_pwd or not ask_pwd.text:
                    await temp_client.disconnect()
                    return
                password = ask_pwd.text.strip()
                await temp_client.check_password(password)
            else:
                raise e

        # 5. 获取 Session String
        session_string = await temp_client.export_session_string()
        await temp_client.disconnect()

        # 6. 自动更新配置并启动 Userbot
        await message.reply("登录成功！正在为您自动保存配置并启动人形脚本...")
        
        if await app.manager.start_userbot(session_string):
            # 获取当前前缀用于通知
            prefix = app.manager.prefix
            owner_id = app.manager.owner_id
            
            success_msg = (
                "✅ **人形脚本已成功启动并绑定！**\n\n"
                f"🆔 **Owner ID**: `{owner_id}`\n"
                f"⌨️ **指令前缀**: `{prefix}`\n\n"
                "您现在可以开始使用它了。"
            )
            await message.reply(success_msg)
            
            # 如果当前会话不是在私聊中，也给 Owner 发个私聊通知
            if message.chat.type != tg.enums.ChatType.PRIVATE:
                await client.send_message(owner_id, success_msg)
        else:
            await message.reply(f"❌ 自动启动失败，但 Session 已保存。请尝试重启程序。\n\nSession String:\n`{session_string}`")

    except Exception as e:
        app.logger.exception("登录过程中出现异常")
        await message.reply(f"❌ 登录失败：{str(e)}")

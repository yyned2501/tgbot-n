import asyncio
import os
import sys
import toml

# 将项目根目录添加到 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import tg, app

async def main():
    # 注意：这里使用 Bot 身份登录
    bot = tg.Client(
        "login_bot",
        api_id=app.API_ID,
        api_hash=app.API_HASH,
        bot_token=app.BOT_TOKEN,
        in_memory=True
    )

    @bot.on_message(tg.filters.command("start") & tg.filters.private)
    async def start_handler(client: tg.Client, message: tg.Message):
        await message.reply("你好！我是登录辅助机器人。\n请发送 /login 开始获取 Session String。")

    @bot.on_message(tg.filters.command("login") & tg.filters.private)
    async def login_handler(client: tg.Client, message: tg.Message):
        chat_id = message.chat.id
        
        # 1. 询问手机号
        _, ask_phone = await client.ask(chat_id, "请输入你的手机号 (带国家代码，例如 +861234567890):")
        phone_number = ask_phone.text.strip()

        try:
            # 2. 发送验证码
            # 使用 in_memory=True 且不使用 ":memory:" 字符串作为名称，有时能解决某些环境下的数据库错误
            temp_client = tg.Client("temp_login_session", api_id=app.API_ID, api_hash=app.API_HASH, in_memory=True)
            await temp_client.connect()
            
            code_info = await temp_client.send_code(phone_number)
            phone_code_hash = code_info.phone_code_hash
            
            # 3. 询问验证码
            _, ask_code = await client.ask(chat_id, "验证码已发送，请输入：")
            verification_code = ask_code.text.strip()

            try:
                # 4. 尝试登录
                await temp_client.sign_in(phone_number, phone_code_hash, verification_code)
            except Exception as e:
                # 处理需要二次验证的情况
                if "SESSION_PASSWORD_NEEDED" in str(e):
                    _, ask_pwd = await client.ask(chat_id, "检测到两步验证，请输入密码：")
                    password = ask_pwd.text.strip()
                    await temp_client.check_password(password)
                else:
                    raise e

            # 5. 获取 Session String
            session_string = await temp_client.export_session_string()
            
            # 自动更新配置 (注意：此处逻辑需要根据新架构重新实现)
            # if update_session_string(session_string):
            #     await message.reply(f"登录成功！\n\nSession String 已自动保存到 `config/config.toml`。\n\n你可以现在启动 `main.py` 了。")
            # else:
            await message.reply(f"登录成功！请手动复制 Session String 并保存到数据库或配置文件：\n\n`{session_string}`")
            
            await temp_client.disconnect()

        except Exception as e:
            app.logger.exception("登录失败")
            await message.reply(f"登录失败：{str(e)}")

    app.logger.info("登录辅助机器人启动中...")
    try:
        await bot.start()
    except Exception as e:
        app.logger.exception("启动失败")
        return
    app.logger.info("登录辅助机器人已启动...")
    await tg.idle()
    await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())

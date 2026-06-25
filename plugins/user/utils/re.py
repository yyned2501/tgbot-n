import asyncio
from core import tg, app

@tg.Client.on_message(tg.filters.me & tg.user_command("re"))
async def forward_to_group(client: tg.Client, message: tg.Message):
    """
    重复发送消息 (转发或复制)
    """
    await message.delete()
    if reply := message.reply_to_message:
        try:
            # 获取重复次数，默认为1
            re_times = (
                int(message.command[1])
                if len(message.command) >= 2 and message.command[1].isdigit()
                else 1
            )
        except (IndexError, ValueError):
            re_times = 1

        for _ in range(re_times):
            try:
                await asyncio.sleep(0.3)
                # 如果聊天没有保护内容，执行转发
                if not message.chat.has_protected_content:
                    await reply.forward(
                        message.chat.id, 
                        message_thread_id=message.message_thread_id
                    )
                else:
                    # 否则执行复制操作
                    await reply.copy(
                        message.chat.id,
                        message_thread_id=message.message_thread_id,
                    )
            except (tg.errors.Forbidden, tg.errors.FloodWait):
                break
            except Exception as e:
                app.logger.error(f"Repeat error: {e}")
                break

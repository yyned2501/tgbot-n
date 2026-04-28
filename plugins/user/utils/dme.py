import asyncio
import contextlib
from core import tg, app

"""
删除自己所发的消息
"""

@tg.Client.on_message(
    tg.filters.me & 
    tg.filters.command("dme", app.PREFIX)
)
async def self_delatemessage(client: tg.Client, message: tg.Message):
    """Deletes specific amount of messages you sent."""
    msgs = []
    count_buffer = 0
    
    if len(message.command) < 2:
        if not message.reply_to_message:
            return await message.edit(f"命令格式不对，请输入 `{app.PREFIX}dme [数量]`")
        count = 1 # 默认删一条？或者根据回复删
    
    try:
        count = int(message.command[1])
        await message.delete()
    except (ValueError, IndexError):
        if len(message.command) >= 2:
            await message.edit(f"删除数量错误，请输入正整数")
            return
        count = 1 # 默认值
        await message.delete()

    async for msg in client.get_chat_history(message.chat.id, limit=100):
        if count_buffer == count:
            break
        if msg.from_user and msg.from_user.is_self:
            msgs.append(msg.id)
            count_buffer += 1
            if len(msgs) == 100:
                await client.delete_messages(message.chat.id, msgs)
                msgs = []
    
    # 原代码中还有一段 search_messages，可能是为了处理更久远的消息
    if count_buffer < count:
        async for msg in client.search_messages(
            message.chat.id, from_user="me"
        ):
            if count_buffer == count:
                break
            if msg.id in msgs: # 避免重复
                continue
            msgs.append(msg.id)
            count_buffer += 1
            if len(msgs) == 100:
                await client.delete_messages(message.chat.id, msgs)
                msgs = []

    if msgs:
        await client.delete_messages(message.chat.id, msgs)   

    with contextlib.suppress(Exception):
        notification = await send_prune_notify(client, message, count_buffer, count)
        await asyncio.sleep(2)
        await notification.delete()

async def send_prune_notify(client: tg.Client, message: tg.Message, count_buffer, count):
    return await client.send_message(message.chat.id, f"已删除消息 {count_buffer} / {count}")

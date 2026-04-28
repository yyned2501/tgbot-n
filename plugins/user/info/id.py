import asyncio
from core import tg, app

@tg.Client.on_message(tg.filters.me & tg.filters.command("id", app.PREFIX))
async def get_id(client: tg.Client, message: tg.Message):
    """
    查询当前聊天或回复用户的 ID
    """
    msg = message.reply_to_message or message
    chat_id = msg.chat.id
    re_mess = ""

    if msg.from_user:
        re_mess = (
            f"**Chat ID:** `{chat_id}`\n"
            f"**User ID:** `{msg.from_user.id}`\n"
            f"**Name:** `{msg.from_user.first_name}`"
        )
    elif msg.sender_chat:
        re_mess = (
            f"**Chat ID:** `{chat_id}`\n"
            f"**Sender Chat ID:** `{msg.sender_chat.id}`\n"
            f"**Title:** `{msg.sender_chat.title}`"
        )
    elif msg.author_signature:
        re_mess = (
            f"**Chat ID:** `{chat_id}`\n"
            f"**Author:** `{msg.author_signature}`"
        )
    else:
        re_mess = f"**Chat ID:** `{chat_id}`"

    result = await message.edit(re_mess)
    
    # 20秒后自动删除
    await asyncio.sleep(20)
    try:
        await result.delete()
    except Exception:
        pass

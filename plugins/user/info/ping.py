import time
from core import Client, filters, Message, PREFIX

@Client.on_message(filters.command("ping", PREFIX) & filters.me)
async def ping(client: Client, message: Message):
    start = time.time()
    msg = await message.edit("Pinging...")
    end = time.time()
    duration = (end - start) * 1000
    await msg.edit(f"🏓 Pong!\n延迟: `{duration:.2f}ms`")

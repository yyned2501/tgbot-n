import time
from core import tg

@tg.Client.on_message(tg.user_command("ping") & tg.filters.me)
async def ping(client: tg.Client, message: tg.Message):
    start = time.time()
    msg = await message.edit("Pinging...")
    end = time.time()
    duration = (end - start) * 1000
    await msg.edit(f"🏓 Pong!\n延迟: `{duration:.2f}ms`")

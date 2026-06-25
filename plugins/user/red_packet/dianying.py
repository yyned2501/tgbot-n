"""
plugins/user/red_packet/dianying.py
癫影积分红包自动抢 — 按钮版
癫影小助手（bot ID 8704462066）在群组发积分红包，
消息正文含「积分红包」，按钮为数字编号（✅1 ✅2 … ✅9），
点任意未抢按钮抢一格，抢到一个即停止。
"""
import asyncio
import random
import re
import time
from core import tg, app
from scripts.filters import create_bot_filter
from scripts.notify import notify_owner

# ─── 常量 ───────────────────────────────────────────────
BOT_ID = 8704462066           # 癫影小助手
REDPACKET_CHAT = -1003907877852  # 癫影发红包的群
_CLICKED_TTL = 3600            # 去重 TTL（秒）

# ─── 去重缓存 ──────────────────────────────────────────
_clicked: dict[str, float] = {}  # "chat:msg" → timestamp


def _prune_clicked():
    now = time.time()
    stale = [k for k, ts in _clicked.items() if now - ts > _CLICKED_TTL]
    for k in stale:
        _clicked.pop(k, None)


def _find_available_buttons(message: tg.Message) -> list[tuple[int, int]]:
    """
    找出消息内联键盘中所有未抢的编号按钮。
    规则：含中文 = 管理员按钮 跳过
          ✅/☑ 开头 = 已抢 跳过
          末尾是数字 = 未抢 → 加入候选
    """
    result: list[tuple[int, int]] = []
    markup = getattr(message, "reply_markup", None)
    if not markup or not getattr(markup, "inline_keyboard", None):
        return result
    for r, row in enumerate(markup.inline_keyboard):
        for c, btn in enumerate(row):
            text = (getattr(btn, "text", "") or "").strip()
            if not text:
                continue
            if re.search(r"[\u4e00-\u9fff]", text):   # 含中文 → 管理员按钮
                continue
            if re.match(r"^[✅☑]", text):               # ✅/☑ 开头 → 已抢
                continue
            if re.search(r"\d$", text):                 # 末尾数字 → 未抢
                result.append((r, c))
    return result


def _is_already_taken(result_text: str) -> bool:
    """判断点击回调结果是否表示该格已被他人抢走。"""
    keywords = ("已经被抢走", "被抢", "已抢完", "已领完", "红包已过期")
    return any(k in result_text for k in keywords)


def _fire_notify(message: tg.Message, result_text: str, *, success: bool) -> None:
    """拼装通知字段并发射（fire-and-forget）。"""
    chat_title = getattr(message.chat, "title", "") if message.chat else ""
    msg_link = getattr(message, "link", "")
    asyncio.create_task(
        notify_owner(
            "癫影积分红包-已抢" if success else "癫影积分红包-未抢到",
            icon="🟡" if success else "❌",
            fields={
                "🏠 所在群组": f"{chat_title}\n   群ID: {message.chat.id}",
                "📩 抢包结果": result_text,
                "🔗 消息链接": msg_link,
            },
        )
    )


# ─── Handler ──────────────────────────────────────────
@tg.Client.on_message(
    tg.filters.chat(REDPACKET_CHAT)
    & tg.filters.regex(r"积分红包")
    & create_bot_filter(BOT_ID),
    group=-9,
)
async def snatch_dianyingpai_packet(client: tg.Client, message: tg.Message):
    """检测癫影积分红包，随机顺序尝试未抢按钮。"""
    # 去重
    key = f"{message.chat.id}:{message.id}"
    _prune_clicked()
    if key in _clicked:
        return
    _clicked[key] = time.time()

    # 找出可点按钮
    positions = _find_available_buttons(message)
    if not positions:
        app.logger.debug(f"[癫影红包] 无可点按钮，跳过 msg={message.id}")
        return

    app.logger.info(f"[癫影红包] 发现红包 msg={message.id}，可用按钮: {len(positions)}")

    # 随机打乱点击顺序，避免总是抢同一个位置
    random.shuffle(positions)

    # 逐个尝试
    for row, col in positions:
        try:
            result = await message.click(x=col, y=row, timeout=10)
            result_text = getattr(result, "message", None) or str(result)
            app.logger.info(f"[癫影红包] 点击({row},{col}) 结果={result_text}")

            if _is_already_taken(result_text):
                app.logger.debug(f"[癫影红包] 该格已被抢，尝试下一个")
                await asyncio.sleep(0.3)
                continue

            # 抢到了
            app.logger.info(f"[癫影红包] 🎉 抢到积分红包! chat={message.chat.id} msg={message.id}")
            _fire_notify(message, result_text, success=True)
            return

        except Exception as e:
            app.logger.warning(f"[癫影红包] 点击({row},{col})失败: {e}")
            continue

    # 所有可点按钮已被抢完
    app.logger.info(f"[癫影红包] 所有可点按钮已被抢完 msg={message.id}")
    _fire_notify(message, "所有格子已被抢完", success=False)

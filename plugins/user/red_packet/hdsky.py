"""
天空红包（拼手气红包）自动抢

天空小秘（bot ID 8907007783）在群组发拼手气红包，
消息含「拼手气红包」关键字，内联键盘有「抢红包」按钮，
点击按钮抢红包。

策略：
1. 检测到拼手气红包 → 立即算 gap（先于任何 auto_msg，避免 auto_msg 污染 last_id）
2. gap >= 阈值 → 不活跃，等待 x 秒后抢
3. gap < 阈值 → 活跃，立即抢
4. 可选：不活跃时自动发消息，拉近后续红包的活跃度

可配置项（模块级常量）：
  - AUTO_MSG: 监听 /red 指令时自动发送的文字（空=不发）
  - AUTO_GAP: auto_msg 触发阈值（msg_id 差）
  - INACTIVE_GAP: 不活跃阈值（msg_id 差）
  - INACTIVE_DELAY: 不活跃时等待秒数
  - CLICK_DELAY: 额外固定延迟秒数
  - ALLOWED_GROUPS: 限定群组 ID 列表（空 = 所有群）

读写策略：
  - 读取 gap 和 last_self_id 仅从本地内存缓存，零 IO 延迟。
  - 写入时同步写内存 + 数据库，保证重启后数据不丢失。
"""

import asyncio
import time
from core import tg, db, app
from scripts.filters import create_bot_filter
from scripts.notify import notify_owner

# ─── 常量 ───────────────────────────────────────────────
BOT_ID = 8907007783  # 天空小秘 HDSKY（拼手气红包/转赠）
_CLICKED_TTL = 3600  # 去重 TTL（秒）
ALLOWED_GROUPS: list[int] = [-1001326208894]  # 限定群组（空=所有群）
_DB_KEY_PREFIX = "hdsky_last_msg:"  # 数据库 key 前缀

# ─── 自动发言配置 ─────────────────────────────────────
AUTO_MSG = "有红包来啦，准备抢红包"  # /red 指令时自动发送的文字（空=不发）
AUTO_GAP = 15  # 自身 msg_id 差 >= 此值才发 auto_msg

# ─── 延迟策略配置 ─────────────────────────────────────
INACTIVE_GAP = 20  # msg_id 差超过此值则认为不活跃
INACTIVE_DELAY = 10.2  # 不活跃时等待秒数（0=不等待）
CLICK_DELAY = 0  # 额外固定延迟秒数

# ─── 去重缓存 ──────────────────────────────────────────
_clicked: dict[str, float] = {}  # "owner_id:chat_id:msg_id" → timestamp

# ─── 自身发言追踪（本地内存缓存）──────────────────────
_last_self_msg_id: dict[str, int] = {}  # "owner_id:chat_id" → msg_id


def _prune_clicked() -> None:
    """清理过期的去重记录。"""
    now = time.time()
    stale = [k for k, ts in _clicked.items() if now - ts > _CLICKED_TTL]
    for k in stale:
        _clicked.pop(k, None)


def _find_snatch_button(message: tg.Message) -> tuple[int, int] | None:
    """在消息内联键盘里找「抢红包」按钮，返回 (row, col) 或 None。"""
    markup = getattr(message, "reply_markup", None)
    if not markup or not getattr(markup, "inline_keyboard", None):
        return None
    for r, row in enumerate(markup.inline_keyboard):
        for c, btn in enumerate(row):
            text = getattr(btn, "text", "") or ""
            if (
                "抢红包" in text
                or "抢 红 包" in text
                or text.strip() in ("抢", "领取红包")
            ):
                return (r, c)
    return None


def _is_lucky_packet(message: tg.Message) -> bool:
    """判断是否为拼手气红包消息。"""
    text = message.text or message.caption or ""
    if "拼手气红包" in text:
        return True
    if "红包" in text and ("份数" in text or "总银元" in text or "总金额" in text):
        return True
    return False


# 拼手气红包消息过滤器
_lucky_packet_filter = tg.filters.create(lambda _, __, m: _is_lucky_packet(m))


async def _get_last_self_id(owner_id: int, chat_id: int) -> int:
    """获取最近一次自身发言的 msg_id，优先读内存，回退读 db（重启恢复）。"""
    key = f"{owner_id}:{chat_id}"
    last_id = _last_self_msg_id.get(key)
    if last_id is not None:
        return last_id
    # 重启后缓存丢失，从数据库恢复
    db_val = await db.get_setting(f"{_DB_KEY_PREFIX}{chat_id}", owner_id=owner_id)
    if db_val:
        try:
            last_id = int(db_val)
            _last_self_msg_id[key] = last_id
            return last_id
        except ValueError:
            pass
    return 0


# ─── 自身发言追踪 Handler ────────────────────────────
@tg.Client.on_message(
    tg.filters.group & tg.filters.chat(ALLOWED_GROUPS) & tg.filters.user("me"), group=-9
)
async def track_self_message(client: tg.Client, message: tg.Message):
    """追踪自身发言 msg_id，写内存 + 写数据库（防重启丢失）。"""
    owner_id = getattr(client, "_owner_id", 0)
    if not owner_id:
        return
    chat_id = message.chat.id
    key = f"{owner_id}:{chat_id}"
    _last_self_msg_id[key] = message.id
    await db.set_setting(
        f"{_DB_KEY_PREFIX}{chat_id}", str(message.id), owner_id=owner_id
    )
    app.logger.info(
        f"[天空红包] 记录自身发言 owner={owner_id} chat={chat_id} "
        f"msg_id={message.id}"
    )


# ─── /red 指令监听（发 auto_msg 拉近活跃度）──────────
@tg.Client.on_message(
    tg.filters.group
    & tg.filters.chat(ALLOWED_GROUPS)
    & ~tg.filters.bot
    & tg.filters.regex(r"/red\S*\s+\d+\s+\d+"),
    group=-9,
)
async def red_command_alert(client: tg.Client, message: tg.Message):
    """监听 /red 指令，gap >= AUTO_GAP 时发 auto_msg 拉近活跃度。"""
    owner_id = getattr(client, "_owner_id", 0)
    if not owner_id:
        return

    auto_msg = (AUTO_MSG or "").strip()
    if not auto_msg:
        return

    last_id = await _get_last_self_id(owner_id, message.chat.id)
    gap = message.id - last_id
    if gap < AUTO_GAP:
        app.logger.info(
            f"[天空红包] 已活跃 gap={gap} < AUTO_GAP={AUTO_GAP}，跳过 auto_msg"
        )
        return

    try:
        sent = await client.send_message(message.chat.id, auto_msg)
        key = f"{owner_id}:{message.chat.id}"
        _last_self_msg_id[key] = sent.id
        await db.set_setting(
            f"{_DB_KEY_PREFIX}{message.chat.id}", str(sent.id), owner_id=owner_id
        )
        client.delete_later(sent, 5)
        app.logger.info(
            f"[天空红包] 已响应 /red 发送 auto_msg (gap={gap} >= AUTO_GAP={AUTO_GAP}) "
            f"chat={message.chat.id} last_id={sent.id}"
        )
    except Exception:
        pass


# ─── 抢红包 Handler ──────────────────────────────────
@tg.Client.on_message(
    tg.filters.group
    & tg.filters.chat(ALLOWED_GROUPS)
    & create_bot_filter(BOT_ID)
    & _lucky_packet_filter,
    group=-9,
)
async def snatch_hdsky_red_packet(client: tg.Client, message: tg.Message):
    """检测拼手气红包并点击「抢红包」按钮。"""
    owner_id = getattr(client, "_owner_id", 0)
    if not owner_id:
        return

    btn_pos = _find_snatch_button(message)
    if not btn_pos:
        app.logger.info(
            f"[天空红包] 拼手气红包消息无「抢红包」按钮，跳过 msg={message.id}"
        )
        return

    # 去重（按账号隔离）
    key = f"{owner_id}:{message.chat.id}:{message.id}"
    _prune_clicked()
    if key in _clicked:
        return
    _clicked[key] = time.time()

    # ── 活跃度判定 ──
    last_id = await _get_last_self_id(owner_id, message.chat.id)
    gap = message.id - last_id

    if gap >= INACTIVE_GAP:
        if INACTIVE_DELAY > 0:
            app.logger.info(
                f"[天空红包] 不活跃 gap={gap} >= {INACTIVE_GAP}，"
                f"等 {INACTIVE_DELAY}s 后抢 owner={owner_id} "
                f"chat={message.chat.id} msg={message.id}"
            )
            await asyncio.sleep(INACTIVE_DELAY)
        else:
            app.logger.info(
                f"[天空红包] 不活跃 gap={gap} >= {INACTIVE_GAP}，立即抢 "
                f"owner={owner_id} chat={message.chat.id} msg={message.id}"
            )
    else:
        app.logger.info(
            f"[天空红包] 活跃 gap={gap} < {INACTIVE_GAP}，立即抢 "
            f"owner={owner_id} chat={message.chat.id} msg={message.id}"
        )

    # 额外固定延迟
    if CLICK_DELAY > 0:
        await asyncio.sleep(CLICK_DELAY)

    row, col = btn_pos
    chat_title = getattr(message.chat, "title", "") if message.chat else ""
    msg_link = getattr(message, "link", "")

    try:
        result = await message.click(x=col, y=row, timeout=10)
        result_text = getattr(result, "message", None) or str(result)
        app.logger.info(
            f"[天空红包] 已点击抢红包 chat={message.chat.id} "
            f"msg={message.id} 结果={result_text}"
        )

        asyncio.create_task(
            notify_owner(
                "天空红包-已抢",
                icon="🧧",
                owner_id=owner_id,
                fields={
                    "🏠 所在群组": f"{chat_title}\n   群ID: {message.chat.id}",
                    "📩 抢包结果": result_text,
                    "🔗 消息链接": msg_link,
                },
            )
        )
    except Exception as e:
        app.logger.warning(
            f"[天空红包] 点击失败 chat={message.chat.id} msg={message.id}: {e}"
        )
        asyncio.create_task(
            notify_owner(
                "天空红包-点击失败",
                icon="❌",
                owner_id=owner_id,
                fields={
                    "🏠 所在群组": f"{chat_title}\n   群ID: {message.chat.id}",
                    "⚠️ 错误信息": str(e),
                    "🔗 消息链接": msg_link,
                },
            )
        )

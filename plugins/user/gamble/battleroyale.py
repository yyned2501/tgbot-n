"""
大逃杀自动下注插件 — 带详细日志调试版

监听 @NextFunBot 的大逃杀/战争迷雾游戏，
实时跟踪各选项投票人数，在结算前约30秒
自动选择人少的那边下注（以少胜多规则）。
支持多圈：结算后自动重置状态进入下一圈投票跟踪。
"""
import asyncio, re
from datetime import datetime, timedelta
from core import tg, db, app
from scripts.filters import create_bot_filter

GROUPID = -1003808371287
BOTID = 8835151149
NOTIFY_USER_ID = 7662190723

L = app.logger  # 简写

class BattleRoyaleState:
    def __init__(self):
        self.options = []
        self.deadline = None
        self.votes = {}             # {选项: set(用户ID)}
        self.voted_users = set()    # 已投票用户ID
        self._counted_msg = set()   # 已统计的消息ID（防止双userbot重复）
        self.is_active = False
        self.bet_placed = False
        self.target_msg_id = None
        self.round = 0
        self._task = None
        self.user_vote_log = []     # [(圈数, 投的选项, 结果, 是否胜利)]
        L.info("[BR] __init__: 状态已初始化")

    def extract_deadline(self, text):
        text = str(text)
        m = re.search(r'(\d{1,2})[:.](\d{1,2})\s*[左右前後以]', text)
        if m:
            now = datetime.now()
            h, mi = int(m.group(1)), int(m.group(2))
            dl = now.replace(hour=h, minute=mi, second=0, microsecond=0)
            if dl < now:
                dl += timedelta(days=1)
            L.info(f"[BR] extract_deadline: h={h} mi={mi} → {dl}")
            return dl
        L.info(f"[BR] extract_deadline: 未匹配到时间, text={text[:80]}")
        return None

    def extract_options(self, text):
        """从消息提取选项，只取「参与口令」后面的部分"""
        text = str(text)
        # 先找"参与口令"后面的内容，避免拿到上一圈的结算结果
        idx = text.find("参与口令")
        if idx >= 0:
            try:
                text = text[idx:]
            except Exception:
                # text 可能不是纯字符串（如 Message 对象），兜底
                text = ""
        m = re.findall(r'「(.+?)」', text)
        opts = m[:2] if len(m) >= 2 else []
        L.info(f"[BR] extract_options: 匹配到 {len(m)} 个, 取前2={opts}")
        return opts
# 全局单例状态
_state = BattleRoyaleState()
_monitored_keywords: list[str] = []  # 当前圈监听的游戏关键词
_startup_resumed = False              # 启动时是否已扫描历史恢复


async def _resume_game_from_history(client):
    """启动时读取最近一条游戏消息，判断是否在下注窗口内"""
    global _state, _monitored_keywords, _startup_resumed
    state = _state
    L.info(f"[BR-startup] 扫描历史恢复游戏状态...")

    try:
        # 逐条拉取最近消息，跳过无法解码的
        bot_msgs = []
        last_id = None
        for _ in range(30):
            try:
                kwargs = {"limit": 1}
                if last_id:
                    kwargs["offset_id"] = last_id
                async for msg in client.get_chat_history(GROUPID, **kwargs):
                    last_id = msg.id
                    try:
                        if not msg.from_user or msg.from_user.id != BOTID:
                            break
                        try:
                            txt = msg.text or ""
                        except Exception:
                            break
                        txt = str(txt)
                        if txt:
                            bot_msgs.append(msg)
                            break
                        break
                    except Exception:
                        break
            except Exception:
                # 这条消息无法解码，跳过继续
                continue
            if len(bot_msgs) >= 5:
                break

        if not bot_msgs:
            L.info(f"[BR-startup] 未找到 NextBot 历史消息, 跳过恢复")
            return

        for msg in bot_msgs:
            try:
                text = msg.text or ""
            except Exception:
                text = ""
            text = str(text)

            # 游戏结束 → 后面不用看了
            if "游戏结束" in text:
                L.info(f"[BR-startup] 最后是游戏结束, 不恢复")
                return

            # 结算/平局 → 提取下圈信息
            if "结算" in text or "平局" in text:
                deadline = state.extract_deadline(text)
                options = state.extract_options(text)
                now = datetime.now()
                if deadline and deadline > now and options:
                    L.info(f"[BR-startup] 找到未结束的结算消息, options={options}, deadline={deadline}")
                    state.__init__()
                    state.is_active = True
                    rm = re.search(r'第(\d+)圈', text)
                    state.round = int(rm.group(1)) + 1 if rm else 1
                    state.target_msg_id = msg.id
                    state.deadline = deadline
                    state.options = options
                    _monitored_keywords = list(options)
                    L.info(f"[BR-startup] ✅ 恢复! round={state.round}, 距结算 {(deadline-now).total_seconds():.0f}秒")
                    state._task = asyncio.create_task(_countdown_loop())
                    return
                elif deadline and deadline <= now:
                    L.info(f"[BR-startup] 结算已过期, deadline={deadline}, 不恢复")
                    return
                else:
                    L.info(f"[BR-startup] 结算消息无有效选项或时间, 跳过")
                    continue

            # 游戏启动
            if "游戏启动" in text:
                deadline = state.extract_deadline(text)
                options = state.extract_options(text)
                now = datetime.now()
                if deadline and deadline > now and options:
                    L.info(f"[BR-startup] 找到进行中的游戏! options={options}, deadline={deadline}")
                    state.__init__()
                    state.is_active = True
                    state.round = 1
                    state.target_msg_id = msg.id
                    state.deadline = deadline
                    state.options = options
                    _monitored_keywords = list(options)
                    L.info(f"[BR-startup] ✅ 恢复! round=1, 距结算 {(deadline-now).total_seconds():.0f}秒")
                    state._task = asyncio.create_task(_countdown_loop())
                    return
                elif deadline and deadline <= now:
                    L.info(f"[BR-startup] 游戏启动已过期, deadline={deadline}")
                    # 可能出结算了但没看到, 继续往下翻
                    continue
                else:
                    continue

    except Exception as e:
        L.error(f"[BR-startup] ❌ 恢复失败: {e}", exc_info=True)
    finally:
        _startup_resumed = True


# 模块加载时启动后台任务, 等 userbot 就绪后扫描
async def _startup_scan():
    for _ in range(60):
        client = app.manager.user
        if client and client.is_connected:
            L.info(f"[BR-startup] userbot 就绪, 开始扫描")
            await _resume_game_from_history(client)
            return
        await asyncio.sleep(1)
    L.warning(f"[BR-startup] 超时未等到 userbot 就绪")

try:
    asyncio.create_task(_startup_scan())
except RuntimeError:
    # 无事件循环时（如测试环境）, 跳过启动扫描
    L.info("[BR-startup] 无可用的运行事件循环, 跳过后台扫描（tgbot-n 正式启动后会重新导入）")
    _startup_resumed = True


# ==================== Handler 1: NextBot 游戏消息 ====================


@tg.Client.on_message(
    tg.filters.chat(GROUPID)
    & create_bot_filter(BOTID)
    & tg.filters.text
)
async def battleroyale_game_handler(client, message):
    global _state
    try:
        text = ""
        try:
            text = message.text or ""
        except Exception:
            pass
        text = str(text)
        state = _state
        L.info(f"[BR-game] 收到 NextBot 消息 msg_id={message.id}: {text[:100]}")

        if "游戏启动" in text:
            L.info(f"[BR-game] ⚔️ 检测到游戏启动!")
            state.__init__()
            state.is_active = True
            state.target_msg_id = message.id
            state.deadline = state.extract_deadline(text)
            state.options = state.extract_options(text)
            state.round = 1
            _monitored_keywords.clear()
            _monitored_keywords.extend(state.options)
            L.info(f"[BR-game] 状态: round=1 options={state.options} deadline={state.deadline}")

            # 推送游戏开始通知
            opt_str = " / ".join(state.options)
            dl_str = state.deadline.strftime("%H:%M") if state.deadline else "?"
            await app.manager.send_bot_message(
                f"⚔️ **大逃杀游戏开始!**\n"
                f"🎯 选项: `{opt_str}`\n"
                f"⏱ 首圈结算: {dl_str}",
                target_id=NOTIFY_USER_ID,
            )

            if state.deadline:
                L.info(f"[BR-game] 启动倒计时任务")
                state._task = asyncio.create_task(_countdown_loop())
            else:
                L.warning(f"[BR-game] ⚠️ 无 deadline, 不启动倒计时")
            return

        if "结算" in text or "平局" in text:
            result = "?"
            rm = re.search(r'口令「(.+?)」胜利', text)
            if rm:
                result = rm.group(1)
            mut = "🧬" if "基因突变" in text else ""
            L.info(f"[BR-game] 🔄 结算! 第{state.round}圈 结果=「{result}」{mut}")
            L.info(f"[BR-game] 结算前投票: { {k:len(v) for k,v in state.votes.items()} }")

            # 计算用户是否胜利
            user_vote = None
            for opt, voters in state.votes.items():
                if NOTIFY_USER_ID in voters:
                    user_vote = opt
                    break

            vote_detail = ", ".join(f"{k}={len(v)}" for k,v in sorted(state.votes.items(), key=lambda x:-len(x[1])))
            is_win = False
            if result != "?":
                is_win = user_vote == result
                win_icon = "✅" if is_win else "❌"
                win_text = "胜利!" if is_win else "失败..."
                user_line = f"👤 你投了: `{user_vote}` → {win_icon} **{win_text}**" if user_vote else "👤 你未投票"
            else:
                user_line = f"👤 你投了: `{user_vote}`" if user_vote else "👤 你未投票"
            state.user_vote_log.append((state.round, user_vote or "-", result, is_win))

            await app.manager.send_bot_message(
                f"🔄 **第{state.round}圈结算** {mut}\n"
                f"🎯 结果: `{result}`\n"
                f"{user_line}\n"
                f"📊 {vote_detail}",
                target_id=NOTIFY_USER_ID,
            )

            state.round += 1
            state.bet_placed = False
            state.votes = {}
            state.voted_users = set()
            state._counted_msg = set()
            state.target_msg_id = message.id
            state.deadline = state.extract_deadline(text)
            state.options = state.extract_options(text)
            _monitored_keywords.clear()
            _monitored_keywords.extend(state.options)
            L.info(f"[BR-game] 下一圈: round={state.round} options={state.options} deadline={state.deadline}")

            if state.options and state.deadline:
                L.info(f"[BR-game] 启动下一圈倒计时")
                state._task = asyncio.create_task(_countdown_loop())
            else:
                if not state.options:
                    L.warning(f"[BR-game] ⚠️ 无选项, 跳过倒计时")
                if not state.deadline:
                    L.warning(f"[BR-game] ⚠️ 无 deadline, 跳过倒计时")
            return

        if "游戏结束" in text:
            L.info(f"[BR-game] 🏁 游戏结束! 共{state.round}圈. 最终投票: { {k:len(v) for k,v in state.votes.items()} }")
            state.is_active = False
            _monitored_keywords.clear()

            # 统计用户的成绩
            wins = sum(1 for _, _, _, w in state.user_vote_log if w)
            total = len(state.user_vote_log)
            played = sum(1 for _, v, _, _ in state.user_vote_log if v != "-")
            summary_lines = "\n".join(
                f"  • 第{r}圈: 「{v}」→「{res}」{'✅' if w else '❌'}"
                for r, v, res, w in state.user_vote_log
            )
            await app.manager.send_bot_message(
                f"🏁 **游戏结束!**\n"
                f"🔄 共 {state.round} 圈 | 你参与了 {played} 圈\n"
                f"📊 胜率: {wins}/{total} (其中未投票 {total - played} 圈自动计失败)\n"
                f"{summary_lines}",
                target_id=NOTIFY_USER_ID,
            )
            state.__init__()
            return

        L.info(f"[BR-game] 其他 NextBot 消息, 忽略")

    except Exception as e:
        L.error(f"[BR-game] ❌ 处理出错: {e}", exc_info=True)


@tg.Client.on_message(
    tg.filters.chat(GROUPID) & tg.filters.text
)
async def battleroyale_vote_tracker(client, message):
    global _state

    text = ""
    try:
        text = message.text or ""
    except Exception:
        pass
    text = str(text)
    if text not in _monitored_keywords:
        return

    state = _state
    sender = message.from_user
    uid = sender.id if sender else 0
    name = sender.first_name if sender else "?"
    msg_id = message.id

    # 消息ID去重（双userbot都会收到同一条消息）
    if msg_id in state._counted_msg:
        return
    state._counted_msg.add(msg_id)

    if not state.is_active:
        return

    if sender and sender.id == BOTID:
        return

    if uid in state.voted_users:
        return

    state.voted_users.add(uid)
    state.votes.setdefault(text, set()).add(uid)
    L.info(f"[BR-vote] ✅ {name}({uid})→{text} 当前: { {k:len(v) for k,v in state.votes.items()} }")


async def _get_user_client():
    c = app.manager.user
    if c and c.is_connected:
        L.info(f"[BR-bet] 获取到 userbot 账号: {c.me.id if c.me else '?'}")
        return c
    L.warning(f"[BR-bet] ⚠️ 无可用 userbot")
    return None


async def _countdown_loop():
    state = _state
    if not state.deadline:
        L.warning(f"[BR-countdown] ⚠️ 无 deadline, 退出")
        return

    remaining = (state.deadline - datetime.now()).total_seconds()
    L.info(f"[BR-countdown] 倒计时启动, round={state.round}, 距结算 {remaining:.0f}秒, deadline={state.deadline}")

    if remaining <= 30:
        L.info(f"[BR-countdown] 剩余不足30秒, 立即下注")
        await _execute_bet()
        return

    wait1 = max(remaining - 5, 1)
    L.info(f"[BR-countdown] 先等 {wait1:.0f}秒 (到结算前5秒)")
    await asyncio.sleep(wait1)
    L.info(f"[BR-countdown] 5秒点到达, state.active={state.is_active} state.bet_placed={state.bet_placed}")

    if not state.is_active or state.bet_placed:
        L.info(f"[BR-countdown] 游戏结束或已下注, 退出")
        return

    L.info(f"[BR-countdown] 最后等5秒收票...")
    await asyncio.sleep(5)
    L.info(f"[BR-countdown] 5秒到, 准备下注. 当前投票: { {k:len(v) for k,v in state.votes.items()} }")

    if state.is_active and not state.bet_placed:
        await _execute_bet()


async def _execute_bet():
    state = _state
    L.info(f"[BR-exec] 执行下注检查... bet_placed={state.bet_placed} votes={ {k:len(v) for k,v in state.votes.items()} }")

    if state.bet_placed:
        L.info(f"[BR-exec] 已下注, 跳过")
        return

    user_client = await _get_user_client()
    if not user_client or not state.target_msg_id:
        return

    # 确定选哪个
    if len(state.votes) >= 2:
        # 两边都有人投 → 选人少的
        sv = sorted(state.votes.items(), key=lambda x: len(x[1]))
        min_opt, min_cnt = sv[0]
        max_opt, max_cnt = sv[-1]
        detail = ", ".join(f"{k}={len(v)}" for k,v in sorted(state.votes.items(), key=lambda x:-len(x[1])))
    elif len(state.votes) == 1:
        # 只有一边有人投 → 押另一边（0票）
        opt_has = list(state.votes.keys())[0]
        min_opt = next((o for o in _monitored_keywords if o != opt_has), None)
        if not min_opt:
            L.info(f"[BR-exec] ⏭️ 无法确定对家, 跳过")
            return
        min_cnt = 0
        max_opt, max_cnt = opt_has, len(state.votes[opt_has])
        detail = f"{opt_has}={max_cnt}"
        L.info(f"[BR-exec] 🎯 一边0票, 投「{min_opt}」")
    else:
        L.info(f"[BR-exec] ⏭️ 无人投票, 跳过")
        return

    # 发到群里
    L.info(f"[BR-exec] 🎯 投「{min_opt}」({min_cnt}) | {detail}")
    await user_client.send_message(GROUPID, min_opt)
    state.bet_placed = True
    L.info(f"[BR-exec] ✅ 下注成功!")

    await app.manager.send_bot_message(
        f"🎯 **大逃杀自动下注**\n🔄 第{state.round}圈\n🎯 `{min_opt}`\n⚖️ {min_opt}({min_cnt}) < {max_opt}({max_cnt})\n📊 {detail}",
        target_id=NOTIFY_USER_ID,
    )
    L.info(f"[BR-exec] ✅ 下注流程完成")

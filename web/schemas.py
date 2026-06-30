"""
插件配置 Schema 定义

每个插件在此注册其可配置参数，Web 面板据此动态渲染配置表单。
存储格式：system_settings 表，key=f"plugin_config:{plugin_id}"，value=JSON blob。
"""

PLUGIN_SCHEMAS = [
    {
        "id": "hdsky",
        "name": "天空红包",
        "icon": "🧧",
        "description": "天空小秘（bot 8907007783）拼手气红包自动抢：检测「抢红包」按钮自动点击，auto_msg 拉近活跃度 + gap 判定不活跃延迟。",
        "module": "plugins.user.red_packet.hdsky",
        "per_account": True,
        "fields": [
            {
                "key": "enabled_groups",
                "type": "textarea",
                "default": "-1001326208894",
                "label": "监听群组",
                "section": "群组",
                "help": "要监听的群组 ID，每行一个。空 = 所有群。",
            },
            {
                "key": "auto_msg",
                "type": "string",
                "default": "红包来了",
                "label": "自动发送的文字",
                "section": "自动发言",
                "help": "群友发 /red 指令时自动发送此消息后删除，拉近自身活跃度。为空则不发送。",
            },
            {
                "key": "auto_gap",
                "type": "slider",
                "default": 15,
                "label": "自动发送阈值 (msg_id 差)",
                "min": 1, "max": 100, "step": 1,
                "section": "自动发言",
                "help": "群友发 /red 指令时，用此值与自身最后发言 msg_id 比，gap >= auto_gap 才发 auto_msg。值越小越敏感。",
            },
            {
                "key": "inactive_gap",
                "type": "slider",
                "default": 20,
                "label": "不活跃阈值 (msg_id 差)",
                "min": 5, "max": 100, "step": 5,
                "section": "延迟策略",
                "help": "红包 msg_id 与最近自身发言差值超过此值视为不活跃，等待 inactive_delay 秒后再抢。",
            },
            {
                "key": "inactive_delay",
                "type": "slider",
                "default": 5,
                "label": "不活跃时等待 (秒)",
                "min": 0, "max": 30, "step": 1,
                "section": "延迟策略",
                "help": "处于不活跃状态时（gap >= 阈值），等待 x 秒后再抢红包。活跃时立即抢。",
            },
            {
                "key": "click_delay",
                "type": "slider",
                "default": 0,
                "label": "额外固定延迟 (秒)",
                "min": 0, "max": 10, "step": 1,
                "section": "延迟策略",
                "help": "无论活跃与否，额外固定等待的秒数。",
            },
        ],
    },
    {
        "id": "dianying",
        "name": "癫影积分红包",
        "icon": "🟡",
        "description": "癫影小助手（bot 8704462066）积分红包自动抢，随机顺序尝试未抢按钮。",
        "module": "plugins.user.red_packet.dianying",
        "per_account": True,
        "fields": [
            {
                "key": "redpacket_chat",
                "type": "string",
                "default": "-1003907877852",
                "label": "红包群组 ID",
                "section": "群组",
                "help": "癫影发红包的群组 ID。",
            },
            {
                "key": "clicked_ttl",
                "type": "slider",
                "default": 3600,
                "label": "去重 TTL (秒)",
                "min": 60, "max": 7200, "step": 60,
                "section": "通用",
                "help": "已抢红包的去重时间，防止重复点击。",
            },
        ],
    },
    {
        "id": "battleroyale",
        "name": "大逃杀",
        "icon": "🎮",
        "description": "大逃杀自动下注系统。",
        "module": "plugins.user.gamble.battleroyale",
        "per_account": True,
        "fields": [],  # 复杂插件，后续扩展
    },
    {
        "id": "zhuque_redpacket",
        "name": "朱雀红包",
        "icon": "🐦",
        "description": "朱雀红包自动抢 + 派记录。",
        "module": "plugins.user.red_packet.zhuque",
        "per_account": True,
        "fields": [],
    },
]


def get_schema(plugin_id: str) -> dict | None:
    """根据 plugin_id 获取 schema"""
    for s in PLUGIN_SCHEMAS:
        if s["id"] == plugin_id:
            return s
    return None


def get_all_schemas() -> list[dict]:
    """获取所有 schema（精简版，不含 fields 详情）"""
    return [
        {
            "id": s["id"],
            "name": s["name"],
            "icon": s["icon"],
            "description": s["description"],
            "module": s["module"],
            "per_account": s["per_account"],
            "field_count": len(s["fields"]),
        }
        for s in PLUGIN_SCHEMAS
    ]

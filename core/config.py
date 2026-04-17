import os
import toml

def load_config():
    # 配置文件在项目根目录下的 config 目录中
    # 当前文件在 core/ 目录下，所以需要向上跳一级
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_path = os.path.join(base_path, "config", "default.toml")
    custom_path = os.path.join(base_path, "config", "config.toml")

    # 加载默认配置
    if not os.path.exists(default_path):
        raise FileNotFoundError(f"Default config not found at {default_path}")
    
    config = toml.load(default_path)

    # 如果存在自定义配置，则合并
    if os.path.exists(custom_path):
        custom_config = toml.load(custom_path)
        # 深度合并字典
        for section, values in custom_config.items():
            if section in config and isinstance(config[section], dict):
                config[section].update(values)
            else:
                config[section] = values
    
    return config

# 全局配置对象
CONFIG = load_config()
API_ID = CONFIG['api']['api_id']
API_HASH = CONFIG['api']['api_hash']
BOT_TOKEN = CONFIG['bot']['bot_token']
SESSION_STRING = CONFIG['userbot']['session_string']
PREFIX = CONFIG['userbot']['prefix']
OWNER_ID = CONFIG.get('bot', {}).get('owner_id', 0)

# 数据库配置
DATABASE_URL = CONFIG.get('database', {}).get('url', "")

# 代理配置
PROXY = CONFIG.get('proxy', {})

def update_session_string(session_string: str):
    """
    更新 config/config.toml 中的 session_string
    """
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    custom_path = os.path.join(base_path, "config", "config.toml")
    
    # 加载现有配置
    if os.path.exists(custom_path):
        data = toml.load(custom_path)
    else:
        data = {}
    
    if 'userbot' not in data:
        data['userbot'] = {}
    
    data['userbot']['session_string'] = session_string
    
    with open(custom_path, "w", encoding="utf-8") as f:
        toml.dump(data, f)
    
    # 同时更新当前运行时的全局变量
    global SESSION_STRING
    SESSION_STRING = session_string
    return True

def update_owner_id(owner_id: int):
    """
    更新 config/config.toml 中的 owner_id
    """
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    custom_path = os.path.join(base_path, "config", "config.toml")
    
    # 加载现有配置
    if os.path.exists(custom_path):
        data = toml.load(custom_path)
    else:
        data = {}
    
    if 'bot' not in data:
        data['bot'] = {}
    
    data['bot']['owner_id'] = owner_id
    
    with open(custom_path, "w", encoding="utf-8") as f:
        toml.dump(data, f)
    
    # 同时更新当前运行时的全局变量
    global OWNER_ID
    OWNER_ID = owner_id
    return True

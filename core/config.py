import os
import toml

def load_config():
    """
    加载配置文件 (config/default.toml 和 config/config.toml)
    """
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

# 全局配置对象 (静态配置)
CONFIG = load_config()

# 基础连接配置
API_ID = CONFIG.get('api', {}).get('api_id', 0)
API_HASH = CONFIG.get('api', {}).get('api_hash', "")
BOT_TOKEN = CONFIG.get('bot', {}).get('bot_token', "")

# 数据库配置
DATABASE_URL = CONFIG.get('database', {}).get('url', "")

# 代理配置
PROXY = CONFIG.get('proxy', {})

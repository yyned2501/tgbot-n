import logging
import sys
import os

# 配置日志格式：时间 - 级别 - [文件名:行号] - 消息
LOG_FORMAT = "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def setup_logger(name="Userbot"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # 防止重复添加 handler
    if not logger.handlers:
        # 1. 控制台输出
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        logger.addHandler(console_handler)

        # 2. 文件输出
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        file_handler = logging.FileHandler(os.path.join(log_dir, "bot.log"), encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        logger.addHandler(file_handler)
    
    return logger

# 全局 logger 实例
logger = setup_logger()

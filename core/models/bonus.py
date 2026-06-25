from sqlalchemy import Column, Integer, String, Numeric, DateTime, func, BigInteger
from .base import Base

class BonusLog(Base):
    """
    通用 PT 站点魔力值变动流水模型 (魔力日志)
    """
    __tablename__ = "bonus_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    create_time = Column(DateTime, server_default=func.now())  # 魔力变动发生时间
    
    website = Column(String(50), nullable=False)  # 站点名称，如 "zhuque", "ptvicomo", "redleaves"
    
    # 行为类型，如 "redpocket" (抢红包), "pie" (馅饼), "transfer_in" (转账收入),
    # "transfer_out" (转账支出), "lottery" (抽奖), "signin" (签到)
    action_type = Column(String(50), nullable=False, index=True)
    
    # 魔力值变动数额（正数为魔力值增加，负数为魔力值消耗）
    amount = Column(Numeric(16, 2), nullable=False)
    
    # 附加备注信息，如 "发包者: xxx", "备注: 恭喜发财" 等
    tag = Column(String(255), nullable=True)
    
    # 关联的 Telegram 消息 ID（可选，方便溯源）
    message_id = Column(BigInteger, nullable=True)
    
    # 所属账号的 Telegram User ID（多用户支持，区分各账号流水）
    owner_id = Column(BigInteger, nullable=False, index=True, comment="所属账号的 Telegram User ID")

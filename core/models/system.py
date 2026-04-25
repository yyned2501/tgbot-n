from sqlalchemy import Column, String
from .base import Base

class SystemSetting(Base):
    """
    通用系统设置模型
    """
    __tablename__ = "system_settings"
    key = Column(String(100), primary_key=True)
    value = Column(String(500))

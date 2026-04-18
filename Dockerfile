ARG PYTHON_VERSION=3.14 # 建议使用稳定版
FROM python:${PYTHON_VERSION}-slim

WORKDIR /app

# 环境变量与系统依赖 (极少变动)
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=Asia/Shanghai
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 预创建目录与脚本处理 (将环境相关的操作前移)
RUN mkdir -p /app/logs /config
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Python 依赖 (只有 requirements.txt 变动时才会更新)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 最后一步：放入业务代码 (最频繁变动)
COPY . .

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "main.py"]
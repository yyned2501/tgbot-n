# 使用轻量级 Python 镜像
ARG PYTHON_VERSION=3.14
FROM python:${PYTHON_VERSION}-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV TZ=Asia/Shanghai

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# --- 核心改进：独立挂载点与 Entrypoint ---
# 创建内部日志目录和外部配置挂载点
RUN mkdir -p /app/logs /config

# 准备 entrypoint 脚本
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# 使用 entrypoint 脚本处理配置同步
ENTRYPOINT ["docker-entrypoint.sh"]
# ------------------------------------

# 默认启动命令
CMD ["python", "main.py"]

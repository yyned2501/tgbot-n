#!/bin/sh
set -e

# 内部配置路径（程序读取路径）
APP_CONFIG_DIR="/app/config"
# 外部挂载路径（用户映射路径）
EXTERNAL_CONFIG_DIR="/config"

echo "--- Docker Entrypoint: Syncing Configuration ---"

# 1. 确保外部挂载目录存在
mkdir -p "$EXTERNAL_CONFIG_DIR"

# 2. 将镜像内的最新 example 同步到外部，方便用户查看
echo "[Config] Updating $EXTERNAL_CONFIG_DIR/config.example.toml"
cp "$APP_CONFIG_DIR/config.example.toml" "$EXTERNAL_CONFIG_DIR/config.example.toml"

# 3. 处理用户配置 config.toml
if [ -f "$EXTERNAL_CONFIG_DIR/config.toml" ]; then
    # 如果外部有配置，同步到内部供程序使用
    echo "[Config] Loading config.toml from $EXTERNAL_CONFIG_DIR"
    cp "$EXTERNAL_CONFIG_DIR/config.toml" "$APP_CONFIG_DIR/config.toml"
else
    # 如果外部没有配置，从内部 example 创建一个到外部
    echo "[Config] No config.toml found in $EXTERNAL_CONFIG_DIR, creating from example..."
    cp "$APP_CONFIG_DIR/config.example.toml" "$EXTERNAL_CONFIG_DIR/config.toml"
    # 同时同步到内部，确保本次启动能跑起来
    cp "$APP_CONFIG_DIR/config.example.toml" "$APP_CONFIG_DIR/config.toml"
fi

echo "--- Configuration Sync Complete ---"

# 执行传入的命令
exec "$@"

# tgbot-n: Telegram 人形脚本与辅助机器人系统

`tgbot-n` 是一个基于 [Pyrogram](https://github.com/pyrogram/pyrogram) 开发的 Telegram 人形脚本 (Userbot) 与 辅助机器人 (Assistant Bot) 双端管理系统。它旨在提供一个高度模块化、易于扩展且工程化规范的开发框架。

## ✨ 核心特性

- **🚀 双端管理**: 同时支持 Userbot (人形脚本) 和 Bot (辅助机器人) 实例，实现功能互补。
- **🧩 插件化架构**: 核心逻辑与业务功能完全解耦，支持递归加载插件，轻松扩展新功能。
- **⚡ 全异步驱动**: 基于 Pyrogram 和 SQLAlchemy 异步模式，确保在高并发场景下的流畅运行。
- **⚙️ 统一配置管理**: 使用 TOML 格式进行配置，支持代理设置、多端 Token 管理。
- **📊 结构化日志**: 统一的日志输出规范，支持控制台与文件记录，方便调试与审计。
- **🛠️ 交互式对话**: 内置 `ask` 方法，轻松实现与用户的交互式命令流程。
- **🐳 容器化支持**: 提供 Dockerfile，支持一键部署。

## 📂 项目结构

```text
tgbot-n/
├── main.py                 # 程序入口
├── core/                   # 核心框架 (Client 封装、配置、数据库、日志)
├── config/                 # 配置文件 (default.toml, config.toml)
├── plugins/                # 插件目录 (bot/ 机器人插件, user/ 人形脚本插件)
│   └── red_packet/         # 红包自动抢模块
├── scripts/                # 辅助脚本 (如登录工具)
├── utils/                  # 通用工具函数
└── ARCHITECTURE.md         # 详细架构文档
```

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/your-username/tgbot-n.git
cd tgbot-n
```

### 2. 安装依赖

推荐使用虚拟环境：

```bash
python -m venv .venv
# Windows
.\.venv\Scripts\Activate.ps1
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. 配置项目

1. 复制配置模板：
   ```bash
   cp config/config.example.toml config/config.toml
   ```
2. 编辑 `config/config.toml`，填写你的 `API_ID`、`API_HASH` 以及 `SESSION_STRING` 或 `BOT_TOKEN`。

### 4. 运行

```bash
python main.py
```

### 🐳 使用 Docker 部署

本项目支持 Docker 部署，并内置了配置自动初始化机制。

#### 方案 1: Docker CLI 直接运行

1. **运行容器**：
   ```bash
   docker run -d \
     --name tgbot-n \
     -v $(pwd)/config:/config \
     -v $(pwd)/logs:/app/logs \
     yyned2501/tgbot-n:latest
   ```

   **机制说明**：
   - **挂载路径**: 注意我们将宿主机的 `config` 目录挂载到了容器的 `/config`（独立挂载点），这样不会覆盖镜像内自带的默认配置。
   - **自动初始化**: 如果本地 `config` 目录为空，容器启动时会自动将 `config.example.toml` 复制到该目录，并生成一个初始的 `config.toml`。
   - **模板同步**: 每次启动都会自动更新本地的 `config.example.toml`，确保你看到的是最新的配置模板。

2. **配置项目**：
   编辑宿主机上自动生成的 `config/config.toml` 文件，填入必要信息，然后重启容器：
   ```bash
   docker restart tgbot-n
   ```

#### 方案 2: Docker Compose 编排部署（推荐）

1. **创建 `docker-compose.yml`**：
   ```yaml
   version: '3.8'

   services:
     tgbot-n:
       image: yyned2501/tgbot-n:latest
       container_name: tgbot-n
       restart: unless-stopped
       volumes:
         - ./config:/config
         - ./logs:/app/logs
       environment:
         - TZ=Asia/Shanghai
       # 可选：如果需要网络隔离
       # networks:
       #   - bot-network

   # networks:
   #   bot-network:
   #     driver: bridge
   ```

2. **启动服务**：
   ```bash
   docker-compose up -d
   ```

3. **查看日志**：
   ```bash
   docker-compose logs -f tgbot-n
   ```

4. **重启服务**：
   ```bash
   docker-compose restart
   ```

5. **停止并移除服务**：
   ```bash
   docker-compose down
   ```

#### 本地构建镜像

如需本地构建：

```bash
# 克隆项目
git clone https://github.com/yyned2501/tgbot-n.git
cd tgbot-n

# 构建镜像
docker build -t tgbot-n:latest .

# 运行容器
docker run -d \
  --name tgbot-n \
  -v $(pwd)/config:/config \
  -v $(pwd)/logs:/app/logs \
  tgbot-n:latest
```

## 🛠️ 插件开发示例

在 `plugins/user/` 下创建一个新文件 `hello.py`:

```python
from core import Client, filters, Message

@Client.on_message(filters.command("hello", prefixes=".") & filters.me)
async def hello_handler(client: Client, message: Message):
    await message.edit("Hello from tgbot-n!")
```

## 📜 开发规范

本项目遵循严格的开发规范，请在贡献代码前阅读 [ARCHITECTURE.md](ARCHITECTURE.md)。

- **统一入口**: 必须通过 `from core import ...` 引用核心组件。
- **严禁 print**: 请使用 `core.logger` 进行日志输出。
- **异步安全**: 数据库操作必须使用异步 Session。

## ⚖️ 免责声明

本项目仅供学习和研究使用。在使用人形脚本时，请遵守 Telegram 的服务条款。因使用本项目导致的任何账号封禁或法律问题，作者概不负责。

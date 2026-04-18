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

### 🐳 使用 Docker 运行

1. 构建镜像：
   ```bash
   docker build -t tgbot-n .
   ```
2. 运行容器：
   ```bash
   docker run -d --name tgbot-n -v $(pwd)/config:/app/config -v $(pwd)/logs:/app/logs tgbot-n
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

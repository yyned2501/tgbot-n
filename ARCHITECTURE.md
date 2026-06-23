# Project Architecture

本项目是一个基于 Pyrogram 的 Telegram 人形脚本 (Userbot) 与 辅助机器人 (Assistant Bot) 双端管理系统。

## 1. 文件树结构

```text
tgbot-n/
├── main.py                 # 程序入口，负责启动和协调双端 Client
├── core/                   # 核心框架包
│   ├── __init__.py         # 统一导出接口，插件引用的唯一入口
│   ├── client.py           # 封装 Pyrogram Client，增加 ask、命令注册等功能
│   ├── keyboard.py         # 键盘工厂，提供链式调用与自适应布局
│   ├── config.py           # 配置加载与持久化管理 (TOML)
│   ├── database.py         # 数据库管理 (SQLAlchemy 异步)
│   ├── logger.py           # 统一日志工具，支持控制台与文件输出
│   └── manager.py          # 应用管理器，负责双端生命周期、插件预加载
├── config/                 # 配置文件目录
│   ├── default.toml        # 默认配置模板
│   └── config.toml         # 用户自定义配置 (私密，不提交)
├── plugins/                # 插件目录
│   ├── bot/                # 辅助机器人插件
│   │   ├── auth/           # 登录授权类 (如 login)
│   │   ├── admin/          # 管理配置类 (如 settings)
│   │   └── info/           # 状态信息类 (如 status)
│   └── user/               # 人形脚本插件
│       ├── info/           # 信息查询类 (如 id、ping)
│       ├── utils/          # 工具类 (如 dme、re、getmsg)
│       ├── custom/         # 特定功能/第三方插件 (如 zhuque 压大小)
│       └── red_packet/     # 红包自动抢模块 (癫影按钮红包、红雀红包等)
├── scripts/                # 独立辅助脚本 (如初始登录工具)
├── utils/                  # 通用工具函数
├── logs/                   # 日志文件存放目录
└── requirements.txt        # 项目依赖
```

## 2. 模块职责

| 模块 | 职责 (Responsibility) | 非职责 (Non-Responsibility) |
| :--- | :--- | :--- |
| `main.py` | 程序生命周期起始、全局异常捕获、启动通知 | 具体的业务逻辑、Client 初始化细节 |
| `core/manager.py` | 管理 User/Bot 实例、插件预加载、管理动态配置 (Database-based) | 具体的 Telegram 协议处理 |
| `core/client.py` | 封装 Pyrogram 接口、实现交互式 `ask`、自动处理代理 | 业务逻辑分发 (由插件负责) |
| `core/keyboard.py` | 提供 InlineKeyboardMarkup 的对象化封装、链式构建及自适应布局逻辑 | 具体的业务按钮定义 (由插件负责) |
| `core/config.py` | 读取静态 TOML 配置、提供基础连接变量 | 验证配置的业务有效性、管理动态设置 |
| `core/database.py` | 管理 SQLAlchemy 异步引擎、Session 生命周期、自动建表、处理数据库降级与自动迁移 | 定义具体的业务模型 (由插件或单独模型文件负责) |
| `core/logger.py` | 格式化日志输出、维护日志文件、行号追踪 | 决定哪些信息该记录 (由调用者决定) |
| `plugins/` | 实现具体的业务功能 (命令处理器、事件监听) | 管理 Client 状态、读写核心配置文件 |

## 3. 引用拓扑图 (Reference Topology)

```mermaid
graph TD
    Main[main.py] --> Manager[core/manager.py]
    Main --> Logger[core/logger.py]
    Main --> Database[core/database.py]
    
    Manager --> Client[core/client.py]
    Manager --> Config[core/config.py]
    Manager --> Database
    Manager --> Logger
    
    Database --> Config
    Database --> Logger
    
    Client --> Config
    Client --> Logger
    
    Plugins[plugins/*] --> CoreInit[core/__init__.py]
    CoreInit --> TG[core/tg.py]
    CoreInit --> DB[core/db.py]
    CoreInit --> APP[core/app.py]
    
    TG --> Client[core/client.py]
    TG --> Keyboard[core/keyboard.py]
    DB --> Database[core/database.py]
    DB --> Models[core/models/*]
    APP --> Manager[core/manager.py]
    APP --> Config[core/config.py]
    APP --> Logger[core/logger.py]
    
    Scripts[scripts/*] --> CoreInit
```

## 4. 修改协议 (Modification Protocol)
在进行任何代码修改前，如果涉及模块间的调用关系变化，**必须**先更新本文件中的“引用拓扑图”部分。

## 5. 子门面导出规范 (Sub-facade Export)
为了避免 `core/__init__.py` 过度臃肿，采用分组导出模式：
- `core.tg`: 包含 Client, filters, types, enums, Keyboards 等 Telegram 相关组件。
- `core.db`: 包含数据库 Session, 模型, 设置读写函数。
- `core.app`: 包含管理器 (manager), 配置常量, 日志工具。

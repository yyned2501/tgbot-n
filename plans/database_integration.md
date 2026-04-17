# 数据库集成实施方案 (SQLAlchemy + PostgreSQL)

## 1. 目标
在项目中集成 SQLAlchemy 异步支持，使用 PostgreSQL 作为后端存储，并采用 `async_scoped_session` 进行会话管理，确保配置管理符合现有规范。

## 2. 实施步骤

### 第一阶段：架构与文档 (Architecture First)
1.  **更新 `ARCHITECTURE.md`**:
    *   在文件树中添加 `core/database.py`。
    *   在模块职责表中添加 `core/database.py`。
    *   更新引用拓扑图，增加 `core/database.py` 与 `core/config.py`、`core/logger.py` 及 `core/__init__.py` 的关联。

### 第二阶段：依赖与配置
1.  **更新 `requirements.txt`**:
    *   添加 `sqlalchemy>=2.0.0`
    *   添加 `asyncpg` (PostgreSQL 异步驱动)
2.  **更新 `config/default.toml`**:
    *   添加 `[database]` 节点。
    *   设置 `url = "postgresql+asyncpg://user:password@localhost:5432/dbname"`。
3.  **更新 `core/config.py`**:
    *   从 `CONFIG['database']['url']` 读取并导出 `DATABASE_URL`。

### 第三阶段：核心模块实现 (`core/database.py`)
1.  **实现自定义 Session 类**:
    *   继承 `sqlalchemy.ext.asyncio.AsyncSession`。
    *   重写 `begin()` 方法以支持嵌套事务。
2.  **配置异步引擎**:
    *   使用 `create_async_engine(DATABASE_URL)`。
    *   针对 PostgreSQL 配置连接池 (`pool_size`, `max_overflow` 等)。
3.  **配置 `async_scoped_session`**:
    *   使用 `asyncio.current_task` 作为作用域。
4.  **定义 `Base` 与 `init_db`**:
    *   `Base = declarative_base()`。
    *   `init_db()` 执行 `Base.metadata.create_all`。

### 第四阶段：统一导出与集成
1.  **更新 `core/__init__.py`**:
    *   导出 `Base`, `async_session` (即 `async_scoped_session` 实例), `init_db`。
2.  **更新 `main.py`**:
    *   在 `main()` 函数启动 Client 之前，调用 `await init_db()`。

## 3. 引用关系变更
- `core/database.py` 引用 `core/config.py` 获取连接字符串。
- `core/database.py` 引用 `core/logger.py` 记录数据库初始化日志。
- `core/__init__.py` 引用 `core/database.py` 进行统一导出。
- `plugins/` 通过 `from core import async_session` 获取数据库会话。

## 4. 注意事项
- 必须使用 `postgresql+asyncpg://` 协议头。
- `async_scoped_session` 确保在同一个 task 中共享同一个 session。

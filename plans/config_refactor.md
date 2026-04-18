# 配置管理重构计划 (Config to Database) - V2

## 1. 目标
将所有动态配置项（`owner_id`, `prefix`, `session_string`）从 `config.toml` 移至数据库存储，实现配置的完全云端化管理（除基础连接信息外）。

## 2. 配置文件调整 (`config/config.toml`)
仅保留以下基础静态配置：
- `[api]`: `api_id`, `api_hash`
- `[bot]`: `bot_token`
- `[proxy]`: 代理相关设置
- `[database]`: 数据库 URL

**移除项**:
- `[bot]`: `owner_id`
- `[userbot]`: `prefix`, `session_string`

## 3. 数据库设计
利用 `system_settings` 表存储：
- `owner_id`: 绑定的 Owner Telegram ID。
- `prefix`: Userbot 的指令前缀（默认 `.`）。
- `session_string`: Userbot 的登录会话字符串。

## 4. 核心模块重构

### 4.1 `core/config.py`
- 移除 `OWNER_ID`, `PREFIX`, `SESSION_STRING` 的全局定义。
- 移除 `update_owner_id` 和 `update_session_string` 函数。
- 仅保留对 TOML 文件的静态读取。

### 4.2 `core/manager.py`
- 增加 `owner_id`, `prefix`, `session_string` 属性。
- 实现 `load_settings()`：从数据库加载上述所有配置。
- 实现对应的 `set_xxx` 方法，同步更新数据库和内存。
- 修改 `init_apps()`：不再直接从 `config` 读取 `SESSION_STRING`，而是使用 `manager.session_string`。

### 4.3 `main.py`
- 调整启动顺序：
    1. `init_db()`
    2. `manager.load_settings()`
    3. `manager.init_apps()`
    4. `manager.start_all()`

## 5. 插件功能增强

### 5.1 `plugins/bot/login.py`
- 登录成功后，调用 `manager.set_session_string(session_string)`。
- 调用 `manager.set_owner_id(me.id)`。
- 发送绑定成功通知。

### 5.2 `plugins/bot/settings.py`
- 增加前缀管理功能。

## 6. 任务清单
1. [ ] 修改 `core/config.py` 移除动态配置读写。
2. [ ] 修改 `core/manager.py` 实现数据库配置加载与管理。
3. [ ] 修改 `main.py` 调整初始化流程。
4. [ ] 修改 `plugins/bot/login.py` 适配数据库存储。
5. [ ] 修改 `plugins/bot/settings.py` 增加前缀管理。
6. [ ] 清理配置文件。
7. [ ] 验证功能。

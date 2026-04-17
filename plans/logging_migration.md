# 引入统一日志管理系统计划

## 1. 目标
- 建立统一的日志管理模块，替换全项目的 `print` 语句。
- 规范日志输出格式，支持不同级别（INFO, ERROR, DEBUG 等）。
- 将日志规范写入 `.clinerules`。

## 2. 实施步骤

### 第一阶段：基础设施
1.  **创建 `core/logger.py`**: 封装标准 `logging` 模块或 `loguru`（如果可用）。
2.  **更新 `core/__init__.py`**: 导出 `logger` 实例。

### 第二阶段：规范集成
1.  **更新 `.clinerules`**: 
    - 明确禁止使用 `print`。
    - 规定必须使用 `core.logger`。

### 第三阶段：代码重构
1.  **更新 `core/config.py`**: 将 `print` 替换为 `logger`。
2.  **更新 `core/manager.py`**: 将 `print` 替换为 `logger`。
3.  **更新 `main.py`**: 将 `print` 替换为 `logger`。
4.  **更新 `plugins/bot/login.py`**: 将 `print` 替换为 `logger`。
5.  **更新 `scripts/login_bot.py`**: 将 `print` 替换为 `logger`。

## 3. 预期效果
- 控制台输出更专业、带时间戳和级别。
- 方便未来将日志持久化到文件。
- 统一 AI 开发时的输出行为。

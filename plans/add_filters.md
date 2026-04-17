# 添加自定义过滤器模块并应用计划

## 1. 目标
在 `scripts/` 目录下新建 `filters.py` 模块，并将其应用到现有的 `zhuque` 插件中，以规范 Bot 消息的过滤方式。

## 2. 内容实现
在 `scripts/filters.py` 中实现：
- `reply_to_me` 过滤器。
- `create_bot_filter(bot_id)` 工厂函数。

## 3. 实施步骤
1. 创建 `scripts/filters.py` 文件并编写逻辑。
2. 修改 `plugins/user/zhuque.py`：
    - 导入 `from scripts.filters import create_bot_filter`。
    - 将 `@Client.on_message(filters.chat(-1002262543959) & filters.user(5697370563))` 
      修改为 `@Client.on_message(filters.chat(-1002262543959) & create_bot_filter(5697370563))`。
3. 验证代码逻辑。

## 4. 注意事项
- 确保 `scripts` 目录在 Python 路径中（通常项目根目录运行没问题）。
- 遵循“以后 bot id 都用这个 filter 来创建”的原则。

# Zhuque 插件开发计划 (最终版)

## 1. 目标
新建一个名为 `zhuque` 的 Userbot 插件，用于自动记录特定群组中特定 Bot 发送的压大小结果到数据库。

## 2. 数据库模型设计
在 `plugins/user/zhuque.py` 中定义 `ZhuqueResult` 模型：
- `id`: 主键，自增
- `final_result`: 最终结果 (Integer, 1 为大, 0 为小)
- `big_total`: 押大的合计金额 (BigInteger)
- `small_total`: 押小的合计金额 (BigInteger)
- `created_at`: 创建时间 (DateTime)
- `settlement_time`: 结算时间 (DateTime)

## 3. 消息解析逻辑
使用正则表达式从消息文本中提取：
- **最终结果**：匹配 `已结算: 结果为 \d+ (大|小)`。
- **押大合计**：提取 `押大:` 下方的所有金额并求和。
- **押小合计**：提取 `押小:` 下方的所有金额并求和。
- **时间**：匹配 `创建时间: ...` 和 `结算时间: ...`。

## 4. 实施步骤
1. 修改 `main.py`：将 `init_db()` 的调用移动到 `manager.init_apps()` 之后，以确保插件中定义的模型能被自动创建。
2. 创建 `plugins/user/zhuque.py`：
    - 导入必要的库和核心组件。
    - 定义 `ZhuqueResult` 模型。
    - 实现 `zhuque_handler` 消息处理器，过滤群组 `-1002262543959` 和用户 `5697370563`。
    - 在处理器中解析文本：
        - 提取 `final_result` (大->1, 小->0)。
        - 提取并计算 `big_total` 和 `small_total`。
        - 提取 `created_at` 和 `settlement_time`。
    - 将解析后的数据保存到数据库。
3. 验证功能。

## 5. 注意事项
- 按照用户要求，**不记录** `chat_id` 和 `message_id`。
- 金额可能包含逗号（如 `100,000`），解析时需处理。
- 使用 `BigInteger` 存储金额，防止溢出。
- 遵循项目规范，使用 `from core import ...`。

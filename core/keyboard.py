from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Union, Optional

class KeyboardFactory:
    """
    Telegram InlineKeyboardMarkup 构建工厂
    支持链式调用和静态常用模板，用于统一管理和简化按钮构建逻辑。
    """
    
    def __init__(self):
        self._rows = []
        self._current_row = []

    def add_button(self, text: str, callback_data: Optional[str] = None, url: Optional[str] = None) -> "KeyboardFactory":
        """
        添加一个按钮到当前行
        
        :param text: 按钮文本
        :param callback_data: 回调数据
        :param url: 链接 URL
        :return: self 支持链式调用
        """
        self._current_row.append(InlineKeyboardButton(text, callback_data=callback_data, url=url))
        return self

    def row(self) -> "KeyboardFactory":
        """
        显式结束当前行，后续添加的按钮将进入新的一行
        
        :return: self 支持链式调用
        """
        if self._current_row:
            self._rows.append(self._current_row)
            self._current_row = []
        return self

    def build(self) -> Optional[InlineKeyboardMarkup]:
        """
        构建并返回 InlineKeyboardMarkup 对象
        
        :return: InlineKeyboardMarkup 对象或 None（如果没有按钮）
        """
        if self._current_row:
            self._rows.append(self._current_row)
            self._current_row = []
        
        if not self._rows:
            return None
        return InlineKeyboardMarkup(self._rows)

    @staticmethod
    def create(buttons: List[Union[InlineKeyboardButton, List[InlineKeyboardButton]]]) -> Optional[InlineKeyboardMarkup]:
        """
        静态方法：快速从按钮列表或嵌套列表创建键盘
        
        :param buttons: 按钮列表，可以是 [btn1, btn2] (单行) 或 [[btn1], [btn2]] (多行)
        :return: InlineKeyboardMarkup 对象
        """
        if not buttons:
            return None
        
        processed_rows = []
        for item in buttons:
            if isinstance(item, list):
                processed_rows.append(item)
            else:
                processed_rows.append([item])
        
        return InlineKeyboardMarkup(processed_rows)

    # --- 基础组件 ---

    @staticmethod
    def button(text: str, callback_data: Optional[str] = None, url: Optional[str] = None) -> InlineKeyboardButton:
        """快捷创建单个按钮对象"""
        return InlineKeyboardButton(text, callback_data=callback_data, url=url)

    @staticmethod
    def back_button(callback_data: str = "back", text: str = "⬅️ 返回") -> InlineKeyboardButton:
        """返回按钮对象"""
        return InlineKeyboardButton(text, callback_data=callback_data)

    @staticmethod
    def close_button(callback_data: str = "close_message", text: str = "❌ 关闭") -> InlineKeyboardButton:
        """返回关闭按钮对象"""
        return InlineKeyboardButton(text, callback_data=callback_data)

    # --- 常用键盘模板 ---

    @staticmethod
    def main_menu(callback_data: str = "back_to_main", text: str = "🏠 返回主菜单") -> InlineKeyboardMarkup:
        """返回包含“返回主菜单”按钮的键盘"""
        return InlineKeyboardMarkup([[InlineKeyboardButton(text, callback_data=callback_data)]])

    @staticmethod
    def back(callback_data: str = "back", text: str = "⬅️ 返回") -> InlineKeyboardMarkup:
        """返回包含“返回”按钮的键盘"""
        return InlineKeyboardMarkup([[InlineKeyboardButton(text, callback_data=callback_data)]])

    @staticmethod
    def confirm_action(data: str, text: str = "确认操作") -> InlineKeyboardMarkup:
        """快速创建一个确认按钮键盘"""
        return InlineKeyboardMarkup([[InlineKeyboardButton(text, callback_data=data)]])

    @staticmethod
    def confirm_cancel(confirm_data: str, cancel_data: str, 
                       confirm_text: str = "✅ 确认", cancel_text: str = "❌ 取消") -> InlineKeyboardMarkup:
        """快速创建 确认/取消 键盘（单行两列）"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(confirm_text, callback_data=confirm_data),
                InlineKeyboardButton(cancel_text, callback_data=cancel_data)
            ]
        ])

    @staticmethod
    def arrange(buttons: List[InlineKeyboardButton], max_cols: int = 3, max_width: int = 40) -> List[List[InlineKeyboardButton]]:
        """
        根据按钮文本长度自适应排列按钮行
        
        :param buttons: 按钮对象列表
        :param max_cols: 每行最大按钮数
        :param max_width: 每行最大字符宽度（中文计2，英文计1）
        :return: 嵌套列表（多行按钮）
        """
        if not buttons:
            return []
            
        rows = []
        current_row = []
        current_width = 0
        
        for btn in buttons:
            # 计算文本宽度
            text_width = 0
            for char in btn.text:
                # 非 ASCII 字符计为 2
                text_width += 2 if ord(char) > 127 else 1
            
            # 按钮的基础宽度（考虑边框和间距）
            btn_width = text_width + 2
            
            # 判断是否需要换行：
            # 1. 当前行已达到最大按钮数
            # 2. 加入当前按钮后超过最大宽度（且当前行不为空）
            if len(current_row) >= max_cols or (current_width + btn_width > max_width and current_row):
                rows.append(current_row)
                current_row = [btn]
                current_width = btn_width
            else:
                current_row.append(btn)
                current_width += btn_width
                
        if current_row:
            rows.append(current_row)
            
        return rows

    def add_buttons(self, buttons: List[InlineKeyboardButton], auto_arrange: bool = True, **kwargs) -> "KeyboardFactory":
        """
        批量添加按钮，并可选自动排列
        """
        if not auto_arrange:
            for btn in buttons:
                self._current_row.append(btn)
        else:
            if self._current_row:
                self.row()
            # 默认使用类定义的 arrange 逻辑
            arranged_rows = self.arrange(buttons, **kwargs)
            self._rows.extend(arranged_rows)
        return self

    @staticmethod
    def pagination(current_page: int, total_pages: int, callback_prefix: str) -> List[InlineKeyboardButton]:
        """
        创建分页按钮行
        
        :param current_page: 当前页码
        :param total_pages: 总页数
        :param callback_prefix: 回调数据前缀，格式为 {prefix}:{page}
        :return: 按钮列表（一行）
        """
        buttons = []
        if current_page > 1:
            buttons.append(InlineKeyboardButton("⬅️", callback_data=f"{callback_prefix}:{current_page - 1}"))
        
        buttons.append(InlineKeyboardButton(f"{current_page}/{total_pages}", callback_data="noop"))
        
        if current_page < total_pages:
            buttons.append(InlineKeyboardButton("➡️", callback_data=f"{callback_prefix}:{current_page + 1}"))
            
        return buttons

# 别名，方便外部通过 Keyboards.xxx 调用
Keyboards = KeyboardFactory

"""
协议生成模块 - Protocol Generator

将 Intent 对象转换为协议格式消息。

协议格式：
<@BOT_ID> [MESSAGE_TYPE|REQUEST_ID|SENDER] CONTENT
"""

import re
from datetime import datetime
from typing import Optional


class ProtocolGenerator:
    """
    协议生成器

    负责：
    1. 生成 RequestID（YYYYMMDD-NNN 格式）
    2. 将 Intent 转换为协议格式
    3. Bot ID 映射管理
    """

    # 消息类型
    MSG_TYPE_ASK = "ASK"           # 询问（小小谦→Worker）
    MSG_TYPE_DO = "DO"             # 任务（小小谦→Worker）
    MSG_TYPE_FORWARD = "FORWARD"   # 转发（小小谦→Worker）
    MSG_TYPE_CONFIRM = "CONFIRM"   # 确认（Worker→小小谦）
    MSG_TYPE_REPORT = "REPORT"     # 汇报（Worker→小小谦）
    MSG_TYPE_DONE = "DONE"         # 完成（Worker→小小谦）
    MSG_TYPE_FAIL = "FAIL"         # 失败（Worker→小小谦）

    # Bot ID 映射表
    BOT_ID_MAP = {
        "小小谦": "1483335704590155786",
        "场控": "1479053473038467212",
        "运营": "1479047738371870730",
        "渠道": "1483334000109162586",
        "美工": "1479055713220431995",
        "编导": "1479060596648312942",
        "剪辑": "1479054512114368512",
        "客服": "1479061563737641095",
    }

    # 反向映射（ID → 名称）
    BOT_NAME_MAP = {v: k for k, v in BOT_ID_MAP.items()}

    # 意图类型到消息类型的映射
    INTENT_TO_MSG_TYPE = {
        "inquiry": MSG_TYPE_ASK,
        "task": MSG_TYPE_DO,
        "forward": MSG_TYPE_FORWARD,
        "status": MSG_TYPE_ASK,  # 状态查询也是询问
        "chat": MSG_TYPE_ASK,    # 闲聊默认当询问处理
    }

    def __init__(self, counter_file: Optional[str] = None):
        """
        初始化协议生成器

        Args:
            counter_file: RequestID 计数器文件路径（可选）
        """
        self.counter_file = counter_file or "data/request_id_counter.json"
        self._counter = {}
        self._load_counter()

    def _load_counter(self):
        """加载计数器"""
        import json
        import os

        if os.path.exists(self.counter_file):
            try:
                with open(self.counter_file, "r", encoding="utf-8") as f:
                    self._counter = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._counter = {}

    def _save_counter(self):
        """保存计数器"""
        import json
        import os

        os.makedirs(os.path.dirname(self.counter_file), exist_ok=True)
        with open(self.counter_file, "w", encoding="utf-8") as f:
            json.dump(self._counter, f, ensure_ascii=False, indent=2)

    def generate_request_id(self) -> str:
        """
        生成 RequestID

        格式：YYYYMMDD-NNN
        - YYYYMMDD: 日期
        - NNN: 当日序号，从 001 开始

        Returns:
            RequestID 字符串
        """
        today = datetime.now().strftime("%Y%m%d")

        if today not in self._counter:
            # 新的一天，重置计数器
            self._counter = {k: v for k, v in self._counter.items()
                           if k != today}  # 清理旧数据
            self._counter[today] = 0

        self._counter[today] += 1
        request_id = f"{today}-{self._counter[today]:03d}"

        # 保存到文件
        self._save_counter()

        return request_id

    def generate(
        self,
        target_bot: str,
        msg_type: str,
        content: str,
        sender: str = "小小谦",
        request_id: Optional[str] = None
    ) -> str:
        """
        生成协议格式消息

        Args:
            target_bot: 目标 Bot 名称（如"场控"）
            msg_type: 消息类型（ASK/DO/FORWARD 等）
            content: 消息内容
            sender: 发送者名称（默认"小小谦"）
            request_id: 请求 ID（可选，不传则自动生成）

        Returns:
            协议格式字符串

        Example:
            >>> generator = ProtocolGenerator()
            >>> generator.generate("场控", "ASK", "在不在？")
            '<@1479053473038467212> [ASK|20260416-001|XiaoXiaoQian] 在不在？'
        """
        # 获取 Bot ID
        bot_id = self.get_bot_id(target_bot)
        if not bot_id:
            raise ValueError(f"未知的 Bot 名称：{target_bot}")

        # 生成 RequestID
        if not request_id:
            request_id = self.generate_request_id()

        # 格式化消息
        return f"<@{bot_id}> [{msg_type}|{request_id}|{sender}] {content}"

    def generate_from_intent(
        self,
        intent,
        sender: str = "小小谦",
        request_id: Optional[str] = None
    ) -> str:
        """
        从 Intent 生成协议消息

        Args:
            intent: Intent 对象
            sender: 发送者名称
            request_id: 请求 ID

        Returns:
            协议格式字符串
        """
        # 确定消息类型
        msg_type = self.INTENT_TO_MSG_TYPE.get(
            intent.intent_type,
            self.MSG_TYPE_ASK
        )

        return self.generate(
            target_bot=intent.target_bot,
            msg_type=msg_type,
            content=intent.content,
            sender=sender,
            request_id=request_id
        )

    def generate_response(
        self,
        target_bot_id: str,
        msg_type: str,
        content: str,
        request_id: str,
        bot_name: str
    ) -> str:
        """
        生成响应协议消息（Worker Bot 回复用）

        Args:
            target_bot_id: 目标 Bot ID（通常是小小谦的 ID）
            msg_type: 消息类型（CONFIRM/DONE/FAIL/REPORT）
            content: 消息内容
            request_id: 原请求 ID（继承）
            bot_name: Bot 名称

        Returns:
            协议格式字符串
        """
        return f"<@{target_bot_id}> [{msg_type}|{request_id}|{bot_name}] {content}"

    def get_bot_id(self, bot_name: str) -> Optional[str]:
        """
        根据 Bot 名称获取 ID

        Args:
            bot_name: Bot 名称

        Returns:
            Bot ID 字符串，未知返回 None
        """
        return self.BOT_ID_MAP.get(bot_name)

    def get_bot_name(self, bot_id: str) -> Optional[str]:
        """
        根据 Bot ID 获取名称

        Args:
            bot_id: Bot ID

        Returns:
            Bot 名称，未知返回 None
        """
        return self.BOT_NAME_MAP.get(bot_id)

    def list_bots(self) -> dict:
        """
        列出所有 Bot 映射

        Returns:
            Bot 映射字典
        """
        return self.BOT_ID_MAP.copy()

    def reset_counter(self, date: Optional[str] = None):
        """
        重置计数器（用于测试或手动维护）

        Args:
            date: 日期字符串（YYYYMMDD），不传则使用今天
        """
        if not date:
            date = datetime.now().strftime("%Y%m%d")

        self._counter[date] = 0
        self._save_counter()


# 快捷函数
def generate_protocol(
    target_bot: str,
    msg_type: str,
    content: str,
    sender: str = "小小谦"
) -> str:
    """快捷函数：生成协议消息"""
    generator = ProtocolGenerator()
    return generator.generate(target_bot, msg_type, content, sender)


# 命令行测试
if __name__ == "__main__":
    import sys

    generator = ProtocolGenerator()

    print("=" * 60)
    print("协议生成测试")
    print("=" * 60)

    # 测试 RequestID 生成
    print("\n1. RequestID 生成:")
    for i in range(3):
        rid = generator.generate_request_id()
        print(f"   {rid}")

    # 测试协议生成
    print("\n2. 协议消息生成:")
    test_cases = [
        ("场控", "ASK", "在不在？"),
        ("运营", "DO", "分析昨天的直播数据"),
        ("剪辑", "FORWARD", "用户问：直播间可以点歌吗？"),
    ]

    for bot, msg_type, content in test_cases:
        protocol = generator.generate(bot, msg_type, content)
        print(f"\n   目标：{bot}, 类型：{msg_type}")
        print(f"   协议：{protocol}")

    # 测试 Bot ID 映射
    print("\n3. Bot ID 映射:")
    for bot_name, bot_id in generator.list_bots().items():
        print(f"   {bot_name}: <@{bot_id}>")

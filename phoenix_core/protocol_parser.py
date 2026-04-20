"""
协议解析模块 - Protocol Parser

解析协议格式消息为结构化对象。

协议格式：
<@BOT_ID> [MESSAGE_TYPE|REQUEST_ID|SENDER] CONTENT
"""

import re
from dataclasses import dataclass
from typing import Optional, Set


@dataclass
class ProtocolMessage:
    """协议消息对象"""

    message_type: str     # ASK | DO | CONFIRM | REPORT | DONE | FAIL
    request_id: str       # 20260416-001
    sender: str           # XiaoXiaoQian | 场控 | 运营 | ...
    target_bot_id: str    # 目标 Bot ID
    content: str          # 消息内容

    @property
    def is_termination(self) -> bool:
        """是否终止消息（不需要回复）"""
        return self.message_type in {"CONFIRM", "DONE", "FAIL"}

    @property
    def is_from_controller(self) -> bool:
        """是否来自总控（小小谦）"""
        return self.sender in {"XiaoXiaoQian", "小小谦"}

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "message_type": self.message_type,
            "request_id": self.request_id,
            "sender": self.sender,
            "target_bot_id": self.target_bot_id,
            "content": self.content,
            "is_termination": self.is_termination,
        }


class ProtocolParser:
    """
    协议解析器

    负责：
    1. 解析协议格式消息
    2. 验证字段格式
    3. 识别终止消息
    """

    # 协议格式正则表达式
    # <@BOT_ID> [MESSAGE_TYPE|REQUEST_ID|SENDER] CONTENT
    PROTOCOL_PATTERN = re.compile(
        r"<@(\d+)>\s*"           # BOT_ID (18 位数字)
        r"\[(\w+)\|"             # MESSAGE_TYPE
        r"(\d{8}-\d{3})\|"       # REQUEST_ID (YYYYMMDD-NNN)
        r"([^\]]+)\]\s*"         # SENDER
        r"(.+)"                  # CONTENT
    )

    # 消息类型白名单
    VALID_MSG_TYPES = {
        "ASK", "DO", "FORWARD",    # 小小谦→Worker
        "CONFIRM", "REPORT", "DONE", "FAIL"  # Worker→小小谦
    }

    # 终止消息类型
    TERMINATION_TYPES = {"CONFIRM", "DONE", "FAIL"}

    def __init__(self):
        """初始化解析器"""
        pass

    def parse(self, text: str) -> Optional[ProtocolMessage]:
        """
        解析协议格式消息

        Args:
            text: 协议格式字符串

        Returns:
            ProtocolMessage 对象，解析失败返回 None

        Example:
            >>> parser = ProtocolParser()
            >>> text = "<@1479053473038467212> [ASK|20260416-001|XiaoXiaoQian] 在不在？"
            >>> result = parser.parse(text)
            >>> result.message_type
            'ASK'
            >>> result.request_id
            '20260416-001'
        """
        if not text or not isinstance(text, str):
            return None

        match = self.PROTOCOL_PATTERN.match(text.strip())
        if not match:
            return None

        bot_id = match.group(1)
        msg_type = match.group(2)
        request_id = match.group(3)
        sender = match.group(4)
        content = match.group(5)

        # 验证消息类型
        if msg_type not in self.VALID_MSG_TYPES:
            return None

        # 验证 Bot ID（18 位数字）
        if not self._validate_bot_id(bot_id):
            return None

        # 验证 RequestID 格式
        if not self._validate_request_id(request_id):
            return None

        return ProtocolMessage(
            message_type=msg_type,
            request_id=request_id,
            sender=sender,
            target_bot_id=bot_id,
            content=content.strip()
        )

    def parse_or_raise(self, text: str) -> ProtocolMessage:
        """
        解析协议消息，失败则抛出异常

        Args:
            text: 协议格式字符串

        Returns:
            ProtocolMessage 对象

        Raises:
            ProtocolParseError: 解析失败
        """
        result = self.parse(text)
        if result is None:
            raise ProtocolParseError(f"无法解析协议消息：{text[:50]}...")
        return result

    def is_valid_protocol(self, text: str) -> bool:
        """
        检查是否是有效的协议消息

        Args:
            text: 待检查的文本

        Returns:
            是否有效
        """
        return self.parse(text) is not None

    def is_termination_message(self, text: str) -> bool:
        """
        检查是否是终止消息

        Args:
            text: 协议消息

        Returns:
            是否是终止消息
        """
        parsed = self.parse(text)
        if not parsed:
            return False
        return parsed.is_termination

    def extract_request_id(self, text: str) -> Optional[str]:
        """
        从协议消息中提取 RequestID

        Args:
            text: 协议消息

        Returns:
            RequestID，无法提取返回 None
        """
        parsed = self.parse(text)
        return parsed.request_id if parsed else None

    def _validate_bot_id(self, bot_id: str) -> bool:
        """验证 Bot ID 格式"""
        # Discord ID 通常是 17-19 位数字
        return bot_id.isdigit() and 17 <= len(bot_id) <= 19

    def _validate_request_id(self, request_id: str) -> bool:
        """
        验证 RequestID 格式

        格式：YYYYMMDD-NNN
        """
        if not request_id or len(request_id) != 12:
            return False

        if request_id[8] != "-":
            return False

        date_part = request_id[:8]
        seq_part = request_id[9:]

        # 验证日期部分
        if not date_part.isdigit():
            return False

        # 验证序号部分
        if not seq_part.isdigit():
            return False

        return True


class ProtocolParseError(Exception):
    """协议解析异常"""
    pass


# 快捷函数
def parse_protocol(text: str) -> Optional[ProtocolMessage]:
    """快捷函数：解析协议消息"""
    parser = ProtocolParser()
    return parser.parse(text)


def is_termination(text: str) -> bool:
    """快捷函数：检查是否是终止消息"""
    parser = ProtocolParser()
    return parser.is_termination_message(text)


# 命令行测试
if __name__ == "__main__":
    parser = ProtocolParser()

    print("=" * 60)
    print("协议解析测试")
    print("=" * 60)

    # 有效消息
    valid_messages = [
        "<@1479053473038467212> [ASK|20260416-001|XiaoXiaoQian] 在不在？",
        "<@1479047738371870730> [DO|20260416-002|XiaoXiaoQian] 分析昨天的直播数据",
        "<@1483335704590155786> [CONFIRM|20260416-001|场控] 在的！刚完成灯光检查，随时待命~",
        "<@1483335704590155786> [DONE|20260416-005|剪辑] 视频已交付，共 3 个切片",
        "<@1483335704590155786> [FAIL|20260416-007|剪辑] 无法完成，源视频文件损坏",
    ]

    print("\n1. 有效消息解析:")
    for msg in valid_messages:
        result = parser.parse(msg)
        if result:
            print(f"\n   原始：{msg[:50]}...")
            print(f"   类型：{result.message_type}")
            print(f"   RequestID: {result.request_id}")
            print(f"   发送者：{result.sender}")
            print(f"   目标 ID: {result.target_bot_id}")
            print(f"   内容：{result.content[:30]}...")
            print(f"   终止消息：{result.is_termination}")
        else:
            print(f"\n   解析失败：{msg}")

    # 无效消息
    invalid_messages = [
        "@场控 在不在",  # 没有协议格式
        "<@123> [ASK|20260416-001|XiaoXiaoQian] 在不在？",  # Bot ID 太短
        "<@1479053473038467212> [INVALID|20260416-001|XiaoXiaoQian] 在不在？",  # 无效消息类型
        "<@1479053473038467212> [ASK|2026041-001|XiaoXiaoQian] 在不在？",  # RequestID 格式错误
    ]

    print("\n2. 无效消息（应解析失败）:")
    for msg in invalid_messages:
        result = parser.parse(msg)
        status = "✓ 解析失败（符合预期）" if result is None else "✗ 解析成功（不符合预期）"
        print(f"   {msg[:40]}... -> {status}")

    # 终止消息检查
    print("\n3. 终止消息检查:")
    test_msgs = [
        ("<@1483335704590155786> [CONFIRM|20260416-001|场控] 在的！", True),
        ("<@1483335704590155786> [DONE|20260416-005|剪辑] 完成", True),
        ("<@1483335704590155786> [FAIL|20260416-007|剪辑] 失败", True),
        ("<@1479053473038467212> [ASK|20260416-001|XiaoXiaoQian] 在不在？", False),
    ]

    for msg, expected in test_msgs:
        result = parser.is_termination_message(msg)
        status = "✓" if result == expected else "✗"
        print(f"   {status} {msg[:50]}... -> {result} (期望：{expected})")

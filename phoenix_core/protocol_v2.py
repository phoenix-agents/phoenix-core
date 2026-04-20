#!/usr/bin/env python3
"""
Phoenix Core Protocol v1.3 - 支持结构化 Handoff 上下文

协议格式:
<@BOT_ID> [TYPE|VERSION|REQUEST_ID|SUB_TASK_ID|SENDER|FLAGS] CONTENT

协议 v1.3 新增:
- HandoffPayload 数据结构，支持完整上下文传递
- essential_entities 字段，快速传递关键实体
- conversation_context 压缩机制

消息类型:
- ASK, RESPONSE, HANDOFF, CANCEL, ALERT, DISCUSS (基础类型)
- REGISTER_SKILL, UNREGISTER_SKILL, QUERY_SKILL, SKILL_FEEDBACK (技能管理)
"""

import re
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any

PROTOCOL_VERSION = "1.3"

# 协议消息类型常量
MSG_TYPE_ASK = "ASK"
MSG_TYPE_RESPONSE = "RESPONSE"
MSG_TYPE_HANDOFF = "HANDOFF"
MSG_TYPE_CANCEL = "CANCEL"
MSG_TYPE_ALERT = "ALERT"
MSG_TYPE_DISCUSS = "DISCUSS"

# 技能管理协议类型
MSG_TYPE_REGISTER_SKILL = "REGISTER_SKILL"
MSG_TYPE_UNREGISTER_SKILL = "UNREGISTER_SKILL"
MSG_TYPE_QUERY_SKILL = "QUERY_SKILL"
MSG_TYPE_SKILL_FEEDBACK = "SKILL_FEEDBACK"


@dataclass
class HandoffPayload:
    """
    Handoff 数据载体 - 用于 Bot 之间交接时传递完整上下文

    设计灵感：OpenAI Agents SDK Handoff + Phoenix Core 实际需求
    """
    from_bot: str                    # 移交方 Bot
    to_bot: str                      # 接收方 Bot
    original_request: str            # 用户原始请求
    handoff_reason: str              # 交接原因
    essential_entities: Dict[str, str] = field(default_factory=dict)  # 关键实体 {"order_id": "123", "user": "张三"}
    conversation_context: List[str] = field(default_factory=list)     # 最近对话历史（压缩后）
    constraints: Dict[str, Any] = field(default_factory=dict)         # 约束条件 {"budget": 10000, "deadline": "2026-04-25"}
    expectations: str = ""           # 期望输出
    return_channel: str = ""         # 结果返回给谁（Coordinator ID）
    deadline_seconds: Optional[int] = None  # 期望完成时间（秒）

    def to_json(self) -> str:
        """序列化为 JSON"""
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "HandoffPayload":
        """从 JSON 反序列化"""
        data = json.loads(json_str)
        return cls(**data)

    def truncate_context(self, max_messages: int = 5, max_chars: int = 1000):
        """截断对话历史，防止 Token 超限"""
        if len(self.conversation_context) > max_messages:
            self.conversation_context = self.conversation_context[-max_messages:]

        # 限制总字符数
        total_chars = sum(len(c) for c in self.conversation_context)
        if total_chars > max_chars:
            # 从最早的消息开始截断
            truncated = []
            remaining = max_chars
            for msg in reversed(self.conversation_context):
                # 预留 3 个字符给 "..."
                if len(msg) + 3 <= remaining:
                    truncated.insert(0, msg)
                    remaining -= len(msg)
                else:
                    # 截断并添加 "..."
                    cut_len = max(0, remaining - 3)
                    if cut_len > 0:
                        truncated.insert(0, msg[:cut_len] + "...")
                    remaining = 0
                    break
            self.conversation_context = truncated


@dataclass
class ProtocolMessage:
    """协议消息对象"""
    target_bot: str          # 目标 Bot 的 Discord ID
    msg_type: str            # ASK, RESPONSE, HANDOFF, CANCEL, ALERT, DISCUSS
    version: str
    request_id: str          # 请求 ID (格式：user_id-date-seq)
    sub_task_id: str         # 子任务 ID (单任务为 "main")
    sender: str              # 发送者名称或 ID
    flags: set = field(default_factory=set)  # {"FINAL", "PROGRESS"}
    content: str = ""        # 自然语言内容

    @classmethod
    def parse(cls, raw: str) -> Optional["ProtocolMessage"]:
        """解析原始消息为 ProtocolMessage"""
        # 支持可选 FLAGS 字段
        # 格式：<@BOT_ID> [TYPE|VERSION|REQ_ID|SUB_ID|SENDER(|FLAGS)] CONTENT
        pattern = r"<@(\d+)> \[(\w+)\|([^\|]+)\|([^\|]+)\|([^\|]+)\|([^\]]+?)(?:\|([^\]]+))?\] (.*)"
        match = re.match(pattern, raw, re.DOTALL)
        if not match:
            return None

        target, msg_type, version, req_id, sub_id, sender, flags_str, content = match.groups()
        flags = set(flags_str.split(",")) if flags_str else set()

        return cls(
            target_bot=target,
            msg_type=msg_type,
            version=version,
            request_id=req_id,
            sub_task_id=sub_id,
            sender=sender.strip(),
            flags=flags,
            content=content.strip()
        )

    def to_string(self) -> str:
        """将 ProtocolMessage 转为字符串"""
        flags_str = ",".join(sorted(self.flags)) if self.flags else ""
        header = f"<@{self.target_bot}> [{self.msg_type}|{self.version}|{self.request_id}|{self.sub_task_id}|{self.sender}"
        if flags_str:
            header += f"|{flags_str}"
        header += f"] {self.content}"
        return header

    @property
    def is_final(self) -> bool:
        """是否是最终回复"""
        return "FINAL" in self.flags

    @property
    def is_progress(self) -> bool:
        """是否是进度汇报"""
        return "PROGRESS" in self.flags


# ============ 便捷构建函数 ============

def create_ask(
    target_bot: str,
    request_id: str,
    sub_task_id: str,
    sender: str,
    content: str
) -> str:
    """构建 ASK 协议消息"""
    msg = ProtocolMessage(
        target_bot=target_bot,
        msg_type="ASK",
        version=PROTOCOL_VERSION,
        request_id=request_id,
        sub_task_id=sub_task_id,
        sender=sender,
        flags=set(),
        content=content
    )
    return msg.to_string()


def create_response(
    target_bot: str,
    request_id: str,
    sub_task_id: str,
    sender: str,
    content: str,
    is_final: bool = False,
    is_progress: bool = False
) -> str:
    """构建 RESPONSE 协议消息"""
    flags = set()
    if is_final:
        flags.add("FINAL")
    if is_progress:
        flags.add("PROGRESS")
    msg = ProtocolMessage(
        target_bot=target_bot,
        msg_type="RESPONSE",
        version=PROTOCOL_VERSION,
        request_id=request_id,
        sub_task_id=sub_task_id,
        sender=sender,
        flags=flags,
        content=content
    )
    return msg.to_string()


def create_handoff(
    target_bot: str,
    request_id: str,
    sub_task_id: str,
    sender: str,
    from_bot: str,
    to_bot: str,
    original_request: str,
    handoff_reason: str,
    essential_entities: Dict[str, str] = None,
    conversation_context: List[str] = None,
    constraints: Dict[str, Any] = None,
    expectations: str = "",
    return_channel: str = "",
    deadline_seconds: Optional[int] = None
) -> str:
    """
    构建 HANDOFF 协议消息（v1.3 增强版）

    Args:
        target_bot: 目标 Bot ID
        request_id: 请求 ID
        sub_task_id: 子任务 ID
        sender: 发送者
        from_bot: 移交方 Bot 名称
        to_bot: 接收方 Bot 名称
        original_request: 用户原始请求
        handoff_reason: 交接原因
        essential_entities: 关键实体字典
        conversation_context: 对话历史
        constraints: 约束条件
        expectations: 期望输出
        return_channel: 结果返回渠道
        deadline_seconds: 截止时间（秒）

    Returns:
        协议消息字符串
    """
    payload = HandoffPayload(
        from_bot=from_bot,
        to_bot=to_bot,
        original_request=original_request,
        handoff_reason=handoff_reason,
        essential_entities=essential_entities or {},
        conversation_context=conversation_context or [],
        constraints=constraints or {},
        expectations=expectations,
        return_channel=return_channel,
        deadline_seconds=deadline_seconds
    )

    # 截断上下文防止超限
    payload.truncate_context(max_messages=5, max_chars=1000)

    content = f"[HANDOFF] {payload.to_json()}"
    msg = ProtocolMessage(
        target_bot=target_bot,
        msg_type="HANDOFF",
        version=PROTOCOL_VERSION,
        request_id=request_id,
        sub_task_id=sub_task_id,
        sender=sender,
        flags=set(),
        content=content
    )
    return msg.to_string()


def parse_handoff(msg: ProtocolMessage) -> Optional[HandoffPayload]:
    """
    从 HANDOFF 消息中解析 HandoffPayload

    Args:
        msg: ProtocolMessage 对象

    Returns:
        HandoffPayload 对象，如果解析失败则返回 None
    """
    if msg.msg_type != MSG_TYPE_HANDOFF:
        return None

    content = msg.content.strip()
    if not content.startswith("[HANDOFF]"):
        return None

    json_str = content[len("[HANDOFF]"):].strip()
    try:
        return HandoffPayload.from_json(json_str)
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        # 降级处理：如果是旧格式，返回基本 payload
        return HandoffPayload(
            from_bot=msg.sender,
            to_bot="",
            original_request=content,
            handoff_reason="未指定",
            essential_entities={},
            conversation_context=[],
            constraints={},
            expectations="",
            return_channel=""
        )


def create_cancel(
    target_bot: str,
    request_id: str,
    sub_task_id: str,
    sender: str,
    reason: str = ""
) -> str:
    """构建 CANCEL 协议消息"""
    content = f"[CANCEL] 任务已取消"
    if reason:
        content += f" | 原因：{reason}"
    msg = ProtocolMessage(
        target_bot=target_bot,
        msg_type="CANCEL",
        version=PROTOCOL_VERSION,
        request_id=request_id,
        sub_task_id=sub_task_id,
        sender=sender,
        flags=set(),
        content=content
    )
    return msg.to_string()


def create_alert(
    target_bot: str,
    request_id: str,
    sub_task_id: str,
    sender: str,
    severity: str,
    message: str
) -> str:
    """构建 ALERT 协议消息"""
    content = f"[ALERT|{severity}] {message}"
    msg = ProtocolMessage(
        target_bot=target_bot,
        msg_type="ALERT",
        version=PROTOCOL_VERSION,
        request_id=request_id,
        sub_task_id=sub_task_id,
        sender=sender,
        flags=set(),
        content=content
    )
    return msg.to_string()


# ============ 技能管理协议 ============

def create_register_skill(
    bot_name: str,
    skill_name: str,
    description: str,
    capabilities: list = None
) -> str:
    """
    构建 REGISTER_SKILL 协议消息
    Bot 向大脑注册新技能
    """
    caps = ",".join(capabilities) if capabilities else ""
    content = f"{skill_name}|{description}"
    if caps:
        content += f"|{caps}"

    msg = ProtocolMessage(
        target_bot="brain",
        msg_type=MSG_TYPE_REGISTER_SKILL,
        version=PROTOCOL_VERSION,
        request_id=f"skill_reg-{skill_name}-{int(time.time())}",
        sub_task_id="main",
        sender=bot_name,
        flags=set(),
        content=content
    )
    return msg.to_string()


def create_unregister_skill(
    bot_name: str,
    skill_name: str,
    reason: str = ""
) -> str:
    """
    构建 UNREGISTER_SKILL 协议消息
    Bot 注销技能
    """
    content = f"{skill_name}"
    if reason:
        content += f"|{reason}"

    msg = ProtocolMessage(
        target_bot="brain",
        msg_type=MSG_TYPE_UNREGISTER_SKILL,
        version=PROTOCOL_VERSION,
        request_id=f"skill_unreg-{skill_name}-{int(time.time())}",
        sub_task_id="main",
        sender=bot_name,
        flags=set(),
        content=content
    )
    return msg.to_string()


def create_query_skill(
    task_description: str,
    sender: str = "gateway"
) -> str:
    """
    构建 QUERY_SKILL 协议消息
    查询能处理某任务的 Bot
    """
    msg = ProtocolMessage(
        target_bot="brain",
        msg_type=MSG_TYPE_QUERY_SKILL,
        version=PROTOCOL_VERSION,
        request_id=f"skill_query-{int(time.time())}",
        sub_task_id="main",
        sender=sender,
        flags=set(),
        content=task_description
    )
    return msg.to_string()


def create_skill_feedback(
    task_id: str,
    bot_name: str,
    skill_name: str,
    rating: int,  # 1-5 分
    feedback: str = ""
) -> str:
    """
    构建 SKILL_FEEDBACK 协议消息
    对技能执行结果进行评价
    """
    content = f"{task_id}|{bot_name}|{skill_name}|{rating}"
    if feedback:
        content += f"|{feedback}"

    msg = ProtocolMessage(
        target_bot="brain",
        msg_type=MSG_TYPE_SKILL_FEEDBACK,
        version=PROTOCOL_VERSION,
        request_id=f"skill_fb-{task_id}-{int(time.time())}",
        sub_task_id="main",
        sender=sender,
        flags=set(),
        content=content
    )
    return msg.to_string()


# ============ 测试 ============

if __name__ == "__main__":
    # 测试 ASK 消息
    ask_msg = create_ask(
        target_bot="123456789",
        request_id="user123-20260417-001",
        sub_task_id="sub-001",
        sender="gateway",
        content="查询订单 #12345"
    )
    print(f"ASK: {ask_msg}")

    # 测试 RESPONSE 消息 (带 FINAL)
    resp_msg = create_response(
        target_bot="gateway",
        request_id="user123-20260417-001",
        sub_task_id="sub-001",
        sender="order_bot",
        content="订单 #12345 已签收",
        is_final=True
    )
    print(f"RESPONSE: {resp_msg}")

    # 测试解析
    parsed = ProtocolMessage.parse(ask_msg)
    print(f"\nParsed ASK: {parsed}")
    print(f"is_final: {parsed.is_final}")

    parsed2 = ProtocolMessage.parse(resp_msg)
    print(f"\nParsed RESPONSE: {parsed2}")
    print(f"is_final: {parsed2.is_final}")

#!/usr/bin/env python3
"""
Phoenix Core Channel Plugin API

渠道插件抽象基类 - 所有平台连接器必须实现此接口

设计原则:
1. 统一消息格式 - 所有平台消息转换为统一 Message 对象
2. 插件化架构 - 新增平台只需实现 ChannelPlugin 接口
3. 异步优先 - 所有 I/O 操作使用 async/await
4. 安全内置 - 每个渠道内置 DM 配对、Allowlist 检查

Usage:
    class MyChannel(ChannelPlugin):
        @property
        def id(self) -> str: return "mychannel"

        async def connect(self, config: ChannelConfig) -> bool:
            # 实现连接逻辑
            pass
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, AsyncIterator, List, Tuple
from enum import Enum
from datetime import datetime


class MessageRole(Enum):
    """消息角色"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Attachment:
    """消息附件"""
    type: str  # image, video, file, audio
    url: Optional[str] = None
    file_path: Optional[str] = None
    filename: Optional[str] = None
    size: Optional[int] = None
    mime_type: Optional[str] = None


@dataclass
class Message:
    """
    统一消息格式

    所有渠道插件必须将平台特定消息转换为此格式
    """
    id: str                              # 平台消息 ID
    channel_id: str                      # 渠道/会话 ID
    user_id: str                         # 发送者 ID
    content: str                         # 消息内容
    timestamp: float                     # Unix 时间戳
    role: MessageRole = MessageRole.USER  # 消息角色

    # 可选字段
    username: Optional[str] = None       # 发送者显示名称
    attachments: List[Attachment] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 引用回复
    in_reply_to: Optional[str] = None    # 回复的消息 ID
    reply_to_user: Optional[str] = None  # 回复的用户 ID

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "user_id": self.user_id,
            "content": self.content,
            "timestamp": self.timestamp,
            "role": self.role.value,
            "username": self.username,
            "attachments": [
                {"type": a.type, "url": a.url, "file_path": a.file_path}
                for a in self.attachments
            ],
            "metadata": self.metadata,
            "in_reply_to": self.in_reply_to,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """从字典创建"""
        return cls(
            id=data["id"],
            channel_id=data["channel_id"],
            user_id=data["user_id"],
            content=data["content"],
            timestamp=data["timestamp"],
            role=MessageRole(data.get("role", "user")),
            username=data.get("username"),
            attachments=[
                Attachment(**a) if isinstance(a, dict) else a
                for a in data.get("attachments", [])
            ],
            metadata=data.get("metadata", {}),
            in_reply_to=data.get("in_reply_to"),
        )


@dataclass
class ChannelConfig:
    """
    渠道配置

    所有敏感凭证应通过环境变量引用
    """
    id: str                              # 渠道 ID
    name: str                            # 渠道显示名称
    enabled: bool = True                 # 是否启用

    # 凭证 (敏感信息，建议通过环境变量引用)
    credentials: Dict[str, str] = field(default_factory=dict)

    # 平台特定设置
    settings: Dict[str, Any] = field(default_factory=dict)

    # 安全设置
    dm_policy: str = "pairing"           # "pairing" | "open" | "closed"
    allow_from: List[str] = field(default_factory=list)  # 允许的用户/频道 ID
    deny_from: List[str] = field(default_factory=list)   # 拒绝的用户/频道 ID

    def get_credential(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """获取凭证 (支持 ${ENV_VAR} 语法)"""
        value = self.credentials.get(key, default)
        if value and value.startswith("${") and value.endswith("}"):
            import os
            env_var = value[2:-1]
            return os.environ.get(env_var)
        return value

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典 (不包含敏感凭证)"""
        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "settings": self.settings,
            "dm_policy": self.dm_policy,
            "allow_from": self.allow_from,
            "deny_from": self.deny_from,
        }


class SecurityCheckResult(Enum):
    """安全检查结果"""
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    PAIRING_REQUIRED = "pairing_required"


@dataclass
class SecurityContext:
    """安全检查上下文"""
    message: Message
    config: ChannelConfig

    # 检查结果
    result: SecurityCheckResult = SecurityCheckResult.ALLOWED
    reason: str = ""
    pairing_code: Optional[str] = None  # 如果需要配对

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result": self.result.value,
            "reason": self.reason,
            "pairing_code": self.pairing_code,
        }


class ChannelPlugin(ABC):
    """
    渠道插件基类

    所有平台连接器必须继承此类并实现所有抽象方法
    """

    def __init__(self):
        self._config: Optional[ChannelConfig] = None
        self._connected = False
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._pairing_store: Dict[str, str] = {}  # user_id -> pairing_code

    @property
    @abstractmethod
    def id(self) -> str:
        """渠道 ID (小写字母，无空格): discord, wechat, telegram..."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """渠道显示名称"""
        pass

    @property
    def connected(self) -> bool:
        """是否已连接"""
        return self._connected

    @property
    def config(self) -> Optional[ChannelConfig]:
        """当前配置"""
        return self._config

    # ==================== 生命周期管理 ====================

    @abstractmethod
    async def connect(self, config: ChannelConfig) -> bool:
        """
        连接到平台

        Args:
            config: 渠道配置

        Returns:
            是否连接成功
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接"""
        pass

    # ==================== 消息发送 ====================

    @abstractmethod
    async def send_message(
        self,
        to: str,
        content: str,
        in_reply_to: Optional[str] = None,
        attachments: Optional[List[Attachment]] = None,
    ) -> bool:
        """
        发送消息

        Args:
            to: 目标频道/会话 ID
            content: 消息内容
            in_reply_to: 回复的消息 ID (可选)
            attachments: 附件列表 (可选)

        Returns:
            是否发送成功
        """
        pass

    async def send_typing(self, to: str) -> None:
        """发送打字状态 (可选实现)"""
        pass

    # ==================== 消息接收 ====================

    @abstractmethod
    def incoming_messages(self) -> AsyncIterator[Message]:
        """
        接收消息流

        Yield:
            Message: 统一格式的消息对象
        """
        pass

    async def _queue_message(self, message: Message) -> None:
        """内部方法：将消息加入队列"""
        await self._message_queue.put(message)

    # ==================== 安全检查 ====================

    async def apply_security(self, message: Message) -> SecurityContext:
        """
        应用安全检查

        默认实现：
        1. DM Pairing 检查
        2. Allowlist/Denylist 检查

        子类可以重写此方法添加平台特定检查
        """
        ctx = SecurityContext(message=message, config=self._config or ChannelConfig(id="unknown", name="Unknown"))

        if not self._config:
            ctx.result = SecurityCheckResult.BLOCKED
            ctx.reason = "Channel not configured"
            return ctx

        # 1. 检查是否在 denylist 中
        if message.user_id in self._config.deny_from:
            ctx.result = SecurityCheckResult.BLOCKED
            ctx.reason = "User is in deny list"
            return ctx

        # 2. 检查 allowlist (如果配置了)
        if self._config.allow_from:
            if message.user_id not in self._config.allow_from:
                # 检查是否是 DM 且需要配对
                if self._is_dm_message(message):
                    if self._config.dm_policy == "pairing":
                        return await self._handle_dm_pairing(ctx)
                    elif self._config.dm_policy == "closed":
                        ctx.result = SecurityCheckResult.BLOCKED
                        ctx.reason = "DM closed"
                        return ctx

                if self._config.dm_policy != "open":
                    ctx.result = SecurityCheckResult.BLOCKED
                    ctx.reason = "User not in allow list"
                    return ctx

        ctx.result = SecurityCheckResult.ALLOWED
        ctx.reason = "OK"
        return ctx

    def _is_dm_message(self, message: Message) -> bool:
        """判断是否是私聊消息"""
        # 默认实现：检查 metadata 中的 is_dm 标志
        return message.metadata.get("is_dm", False)

    async def _handle_dm_pairing(self, ctx: SecurityContext) -> SecurityContext:
        """处理 DM 配对"""
        user_id = ctx.message.user_id

        # 检查是否已配对
        if user_id in self._pairing_store:
            ctx.result = SecurityCheckResult.ALLOWED
            ctx.reason = "User already paired"
            return ctx

        # 生成配对码
        import random
        pairing_code = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=6))
        self._pairing_store[user_id] = pairing_code

        ctx.result = SecurityCheckResult.PAIRING_REQUIRED
        ctx.pairing_code = pairing_code
        ctx.reason = f"Please use !pair {pairing_code} to approve"
        return ctx

    async def approve_pairing(self, user_id: str, pairing_code: str) -> bool:
        """批准配对"""
        if user_id in self._pairing_store:
            if self._pairing_store[user_id] == pairing_code:
                del self._pairing_store[user_id]
                # 添加到 allowlist
                if self._config:
                    self._config.allow_from.append(user_id)
                return True
        return False

    # ==================== 工具方法 ====================

    def get_credential(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """获取凭证"""
        if self._config:
            return self._config.get_credential(key, default)
        return default

    async def initialize(self) -> None:
        """初始化渠道 (可选的异步初始化)"""
        pass

    async def cleanup(self) -> None:
        """清理资源 (在 disconnect 时调用)"""
        pass


# ==================== 工具函数 ====================

def normalize_user_id(user_id: str) -> str:
    """标准化用户 ID (移除平台特定前缀)"""
    return user_id.strip().lower()


def generate_pairing_code() -> str:
    """生成配对码"""
    import random
    return "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=6))


# ==================== 注册表 ====================

class ChannelRegistry:
    """渠道注册表 - 管理所有可用的渠道插件"""

    _instance: Optional["ChannelRegistry"] = None
    _channels: Dict[str, type] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, channel_class: type) -> type:
        """注册一个渠道插件"""
        if not issubclass(channel_class, ChannelPlugin):
            raise TypeError(f"{channel_class} must be a subclass of ChannelPlugin")

        # 通过实例获取 ID
        instance = channel_class()
        cls._channels[instance.id] = channel_class
        return channel_class

    @classmethod
    def get(cls, channel_id: str) -> Optional[type]:
        """获取渠道插件类"""
        return cls._channels.get(channel_id)

    @classmethod
    def list_channels(cls) -> List[str]:
        """列出所有已注册的渠道"""
        return list(cls._channels.keys())

    @classmethod
    def create(cls, channel_id: str) -> Optional[ChannelPlugin]:
        """创建渠道插件实例"""
        channel_class = cls.get(channel_id)
        if channel_class:
            return channel_class()
        return None

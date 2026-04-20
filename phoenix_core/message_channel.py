#!/usr/bin/env python3
"""
Phoenix Core Message Channel Adapter

平台无关的消息通道抽象接口

与 ChannelPlugin 的区别：
- ChannelPlugin: 渠道层接口，支持多频道/DM/安全策略
- MessageChannel: 简化的平台适配器接口，用于 Gateway 注入

Usage:
    class MyPlatformChannel(MessageChannel):
        async def connect(self) -> bool: ...
        async def send_message(self, target: str, content: str) -> bool: ...
        async def on_message(self, callback) -> None: ...
"""

import asyncio
import re
from abc import ABC, abstractmethod
from typing import Callable, Dict, Any, Optional
from dataclasses import dataclass

# 兼容两种导入路径
try:
    from channels.base import Message, Attachment, MessageRole
except ImportError:
    from phoenix_core.channels.base import Message, Attachment, MessageRole


@dataclass
class PlatformMessage:
    """
    平台统一消息格式

    简化版，用于平台适配器与 Gateway 之间的通信
    """
    platform: str          # 平台名称：discord, feishu, dingtalk
    content: str           # 消息内容
    author_id: str         # 发送者 ID
    author_name: str       # 发送者名称
    channel_id: str        # 频道/会话 ID
    timestamp: float       # Unix 时间戳
    is_mention: bool = False  # 是否@了 Bot
    raw: Any = None        # 平台原始消息对象


class MessageChannel(ABC):
    """
    平台消息通道抽象基类

    Gateway 通过此接口与底层平台通信，完全平台无关
    """

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """平台名称：discord, feishu, dingtalk"""
        pass

    @abstractmethod
    async def connect(self) -> bool:
        """
        建立平台连接

        Returns:
            bool: 是否连接成功
        """
        pass

    @abstractmethod
    async def send_message(self, target: str, content: str, **kwargs) -> bool:
        """
        发送消息到指定目标

        Args:
            target: 目标用户 ID 或频道 ID
            content: 消息内容
            **kwargs: 平台特定参数

        Returns:
            bool: 是否发送成功
        """
        pass

    @abstractmethod
    async def on_message(self, callback: Callable[[PlatformMessage], None]) -> None:
        """
        注册消息接收回调

        Args:
            callback: 消息回调函数，接收 PlatformMessage 对象
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """断开平台连接"""
        pass

    async def send_typing(self, target: str) -> None:
        """发送打字状态（可选实现）"""
        pass

    def normalize_mention(self, content: str) -> tuple[str, bool]:
        """
        标准化@mention 格式，提取 Bot 是否被@

        Returns:
            (清理后的内容，是否@了 Bot)
        """
        is_mention = False
        cleaned = content

        # Discord: <@123456789>
        import re
        discord_mention = re.search(r'<@!?(\d+)>', cleaned)
        if discord_mention:
            is_mention = True
            cleaned = re.sub(r'<@!?(\d+)>', '', cleaned).strip()

        # 飞书：@user
        feishu_mention = re.search(r'@(\S+)', cleaned)
        if feishu_mention:
            is_mention = True
            cleaned = re.sub(r'@(\S+)', '', cleaned).strip()

        return cleaned, is_mention


# ==================== Discord 适配器 ====================

class DiscordMessageChannel(MessageChannel):
    """
    Discord 平台适配器

    基于 discord.py，实现 MessageChannel 接口
    """

    def __init__(self, token: str, channel_id: Optional[str] = None):
        self.token = token
        self.channel_id = channel_id
        self.client = None
        self._message_callback: Optional[Callable[[PlatformMessage], None]] = None
        self._ready = asyncio.Event()

    @property
    def platform_name(self) -> str:
        return "discord"

    async def connect(self) -> bool:
        try:
            import discord
            from discord.ext import commands

            intents = discord.Intents.default()
            intents.message_content = True
            intents.members = True

            self.client = commands.Bot(command_prefix='!', intents=intents)

            @self.client.event
            async def on_ready():
                print(f"Discord 已连接：{self.client.user}")
                self._ready.set()

            @self.client.event
            async def on_message(message):
                if self._message_callback and message.author != self.client.user:
                    # 转换为 PlatformMessage
                    platform_msg = PlatformMessage(
                        platform="discord",
                        content=message.content,
                        author_id=str(message.author.id),
                        author_name=message.author.name,
                        channel_id=str(message.channel.id),
                        timestamp=message.created_at.timestamp(),
                        is_mention=self.client.user in message.mentions,
                        raw=message
                    )
                    await self._message_callback(platform_msg)

            # 启动客户端
            asyncio.create_task(self._start_client())

            # 等待连接完成
            try:
                await asyncio.wait_for(self._ready.wait(), timeout=30.0)
                return True
            except asyncio.TimeoutError:
                return False

        except Exception as e:
            print(f"Discord 连接失败：{e}")
            return False

    async def _start_client(self):
        """后台启动 Discord 客户端"""
        await self.client.start(self.token)

    async def send_message(self, target: str, content: str, **kwargs) -> bool:
        if not self.client:
            return False

        try:
            channel = self.client.get_channel(int(target))
            if not channel:
                channel = await self.client.fetch_channel(int(target))

            if channel:
                await channel.send(content)
                return True
            return False
        except Exception as e:
            print(f"Discord 发送失败：{e}")
            return False

    async def on_message(self, callback: Callable[[PlatformMessage], None]) -> None:
        self._message_callback = callback

    async def disconnect(self) -> None:
        if self.client:
            await self.client.close()


# ==================== 工厂函数 ====================

def get_channel(platform: str, **kwargs) -> Optional[MessageChannel]:
    """
    根据平台名称获取对应的 Channel 实例

    Args:
        platform: 平台名称 (discord, feishu, dingtalk)
        **kwargs: 平台特定参数

    Returns:
        MessageChannel 实例或 None
    """
    platforms = {
        "discord": DiscordMessageChannel,
        # "feishu": FeishuMessageChannel,  # TODO
        # "dingtalk": DingtalkMessageChannel,  # TODO
    }

    channel_class = platforms.get(platform)
    if channel_class:
        return channel_class(**kwargs)
    return None

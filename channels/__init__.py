"""
Phoenix Core Channels - 多平台连接器

渠道插件系统允许 Phoenix Core 连接到多个消息平台：
- Discord
- 企业微信
- Telegram
- Slack
- 钉钉
- 飞书

Usage:
    from channels import ChannelRegistry, ChannelConfig

    # 获取可用的渠道
    print(ChannelRegistry.list_channels())

    # 创建渠道实例
    channel = ChannelRegistry.create("discord")
"""

from .base import (
    # 核心类
    ChannelPlugin,
    ChannelConfig,
    ChannelRegistry,

    # 消息类型
    Message,
    MessageRole,
    Attachment,

    # 安全类型
    SecurityContext,
    SecurityCheckResult,

    # 工具函数
    normalize_user_id,
    generate_pairing_code,
)

from .manager import ChannelManager

__all__ = [
    # 核心类
    "ChannelPlugin",
    "ChannelConfig",
    "ChannelRegistry",
    "ChannelManager",

    # 消息类型
    "Message",
    "MessageRole",
    "Attachment",

    # 安全类型
    "SecurityContext",
    "SecurityCheckResult",

    # 工具函数
    "normalize_user_id",
    "generate_pairing_code",
]

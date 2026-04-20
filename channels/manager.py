#!/usr/bin/env python3
"""
Channel Manager - 渠道管理器

统一管理所有渠道插件的生命周期、消息路由和状态监控

功能:
1. 加载和初始化所有配置的渠道
2. 消息路由：渠道 -> Gateway -> AI Agent -> 渠道
3. 状态监控和健康检查
4. 跨渠道消息同步

Usage:
    from channels.manager import ChannelManager

    manager = ChannelManager(bot_name="运营")
    await manager.initialize()
    await manager.start_listening()
"""

import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any
from pathlib import Path
from datetime import datetime

from .base import (
    ChannelPlugin,
    ChannelConfig,
    ChannelRegistry,
    Message,
    MessageRole,
    SecurityCheckResult,
)
from .config_loader import load_channel_configs
from .discord_channel import DiscordChannel, setup_discord_commands

# 尝试导入飞书通道（可选依赖）
try:
    from .feishu_channel import FeishuChannel
    HAS_FEISHU = True
except ImportError:
    HAS_FEISHU = False

logger = logging.getLogger(__name__)


class ChannelManager:
    """渠道管理器 - Gateway 的内置组件"""

    def __init__(
        self,
        workspace: str,
        message_callback: Optional[Callable] = None,
        bot_name: str = "Phoenix",
    ):
        """
        初始化渠道管理器

        Args:
            workspace: 工作区目录
            message_callback: 消息处理回调 (Gateway._handle_message)
            bot_name: Bot 名称
        """
        self.workspace = Path(workspace)
        self.message_callback = message_callback
        self.bot_name = bot_name

        # 渠道实例
        self.channels: Dict[str, ChannelPlugin] = {}

        # 渠道配置
        self.configs: Dict[str, ChannelConfig] = {}

        # 消息处理任务
        self._listen_tasks: Dict[str, asyncio.Task] = {}

        # 运行状态
        self._running = False

        # 配置目录
        self.config_dir = self.workspace / "channels"

        # Discord 客户端引用 (用于命令注册)
        self.discord_client = None

    async def initialize(self) -> bool:
        """
        初始化所有渠道

        Returns:
            是否至少有一个渠道连接成功
        """
        logger.info(f"Initializing channels for {self.bot_name}...")

        # 加载配置
        config_file = self.config_dir / "channels.yaml"
        if not config_file.exists():
            config_file = self.config_dir / "channels.json"

        configs = load_channel_configs(str(config_file))

        if not configs:
            logger.warning("No channel configs found, using default Discord config")
            configs = [self._create_default_discord_config()]

        # 连接所有渠道
        success_count = 0
        for config in configs:
            try:
                success = await self._connect_channel(config)
                if success:
                    success_count += 1
            except Exception as e:
                logger.error(f"Failed to connect channel {config.id}: {e}")

        logger.info(f"Connected {success_count}/{len(configs)} channels")
        return success_count > 0

    def _create_default_discord_config(self) -> ChannelConfig:
        """创建默认 Discord 配置"""
        from .config_loader import create_default_config
        return create_default_config("discord", self.bot_name)

    async def _connect_channel(self, config: ChannelConfig) -> bool:
        """连接单个渠道"""
        logger.info(f"Connecting to {config.name} ({config.id})...")

        # 创建渠道实例
        channel = ChannelRegistry.create(config.id)

        if channel is None:
            # 尝试直接导入已知渠道
            if config.id == "discord":
                channel = DiscordChannel()
            elif config.id == "feishu" and HAS_FEISHU:
                channel = FeishuChannel()
            else:
                logger.warning(f"Channel plugin not found: {config.id}")
                return False

        # 连接
        success = await channel.connect(config)

        if success:
            self.channels[config.id] = channel
            self.configs[config.id] = config
            logger.info(f"Connected to {config.name}")

            # 如果是 Discord，设置命令
            if config.id == "discord" and self.discord_client:
                setup_discord_commands(self.discord_client, channel)
        else:
            logger.error(f"Failed to connect to {config.name}")

        return success

    async def start_listening(self):
        """启动所有渠道的消息监听"""
        if self._running:
            logger.warning("Already listening")
            return

        self._running = True
        logger.info("Starting channel listeners...")

        for channel_id, channel in self.channels.items():
            task = asyncio.create_task(self._listen_loop(channel_id, channel))
            self._listen_tasks[channel_id] = task
            logger.info(f"Started listener for {channel.name}")

    async def stop_listening(self):
        """停止所有渠道的消息监听"""
        self._running = False

        # 取消所有监听任务
        for channel_id, task in self._listen_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._listen_tasks.clear()
        logger.info("Stopped all channel listeners")

    async def _listen_loop(self, channel_id: str, channel: ChannelPlugin):
        """渠道消息监听循环"""
        try:
            async for message in channel.incoming_messages():
                if not self._running:
                    break

                # 调用 Gateway 回调
                # Gateway 会自己发送响应，这里不需要再发送
                # 重要：在独立协程中处理，避免阻塞消息队列
                if self.message_callback:
                    try:
                        asyncio.create_task(self.message_callback(message, channel))
                    except Exception as e:
                        logger.error(f"Gateway callback error: {e}")

        except asyncio.CancelledError:
            logger.debug(f"Listener cancelled for {channel_id}")
        except Exception as e:
            logger.error(f"Listener error for {channel_id}: {e}")

    async def _send_response(
        self,
        channel: ChannelPlugin,
        original_message: Message,
        response: str,
    ):
        """发送响应到渠道"""
        await channel.send_message(
            to=original_message.channel_id,
            content=response,
            in_reply_to=original_message.id,
        )

    async def send_message(
        self,
        channel_id: str,
        to: str,
        content: str,
        in_reply_to: Optional[str] = None,
    ) -> bool:
        """
        通过指定渠道发送消息

        Args:
            channel_id: 渠道 ID
            to: 目标频道/会话 ID
            content: 消息内容
            in_reply_to: 回复的消息 ID

        Returns:
            是否发送成功
        """
        if channel_id not in self.channels:
            logger.error(f"Channel {channel_id} not found")
            return False

        channel = self.channels[channel_id]
        return await channel.send_message(to, content, in_reply_to)

    async def broadcast(
        self,
        content: str,
        exclude_channels: Optional[List[str]] = None,
    ) -> Dict[str, bool]:
        """
        广播消息到所有渠道

        Args:
            content: 消息内容
            exclude_channels: 排除的渠道 ID 列表

        Returns:
            各渠道发送结果
        """
        results = {}
        exclude = exclude_channels or []

        for channel_id, channel in self.channels.items():
            if channel_id in exclude:
                continue

            # 广播到所有已配置的频道 (需要从配置获取)
            config = self.configs.get(channel_id)
            if config:
                # 这里需要知道广播到哪些具体频道
                # 暂时跳过，需要额外的配置支持
                pass

        return results

    def get_channel(self, channel_id: str) -> Optional[ChannelPlugin]:
        """获取渠道实例"""
        return self.channels.get(channel_id)

    def get_config(self, channel_id: str) -> Optional[ChannelConfig]:
        """获取渠道配置"""
        return self.configs.get(channel_id)

    def list_channels(self) -> List[Dict[str, Any]]:
        """列出所有渠道状态"""
        result = []
        for channel_id, channel in self.channels.items():
            config = self.configs.get(channel_id)
            result.append({
                "id": channel_id,
                "name": channel.name,
                "connected": channel.connected,
                "config": config.to_dict() if config else None,
            })
        return result

    async def health_check(self) -> Dict[str, bool]:
        """健康检查"""
        results = {}
        for channel_id, channel in self.channels.items():
            results[channel_id] = channel.connected
        return results

    async def cleanup(self):
        """清理资源"""
        await self.stop_listening()

        for channel_id, channel in self.channels.items():
            try:
                await channel.cleanup()
            except Exception as e:
                logger.error(f"Cleanup error for {channel_id}: {e}")

        for channel_id, channel in self.channels.items():
            try:
                await channel.disconnect()
            except Exception as e:
                logger.error(f"Disconnect error for {channel_id}: {e}")

        self.channels.clear()
        self.configs.clear()
        logger.info("Channel manager cleaned up")


# ==================== Gateway 集成 ====================

async def default_gateway_callback(
    message: Message,
    channel: ChannelPlugin,
) -> Optional[str]:
    """
    默认 Gateway 回调

    这里应该调用 Phoenix Core Gateway 处理消息
    当前是占位实现
    """
    logger.info(f"Received message from {channel.name}: {message.content[:50]}...")
    # TODO: 调用 Gateway 处理
    return None


# ==================== 主程序 ====================

async def main():
    """测试主程序"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    manager = ChannelManager(bot_name="运营")

    # 初始化
    success = await manager.initialize()
    if not success:
        logger.error("Failed to initialize channels")
        return

    # 启动监听
    await manager.start_listening()

    # 运行直到中断
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await manager.cleanup()


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Discord Channel Plugin for Phoenix Core

Discord 渠道连接器 - 只负责 Discord API 对接
- 接收 Discord 消息并转换为统一 Message 格式
- 发送响应到 Discord
- 不处理任何业务逻辑
"""

import asyncio
import logging
import os
from typing import Optional, AsyncIterator, List

import discord
from discord.ext import commands

from channels.base import (
    ChannelPlugin,
    ChannelConfig,
    Message,
    MessageRole,
    Attachment,
    SecurityContext,
    SecurityCheckResult,
)

logger = logging.getLogger(__name__)


class DiscordChannel(ChannelPlugin):
    """Discord 渠道插件"""

    @property
    def id(self) -> str:
        return "discord"

    @property
    def name(self) -> str:
        return "Discord"

    def __init__(self, gateway=None):
        """
        初始化 Discord 渠道

        Args:
            gateway: PhoenixCoreGateway 实例 (可选)
        """
        super().__init__()
        self.client: Optional[commands.Bot] = None
        self._ready = asyncio.Event()
        self.gateway = gateway  # 引用 Gateway 用于消息处理

    async def connect(self, config: ChannelConfig) -> bool:
        """连接到 Discord"""
        self._config = config

        token = self.get_credential("bot_token")
        if not token:
            logger.error("Discord bot token not found")
            return False

        # 配置 Intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.presences = True

        # 从环境变量读取代理配置 (支持 HTTPS_PROXY 或 http_proxy)
        proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")

        if proxy_url:
            logger.info(f"Using proxy from environment: {proxy_url}")
        else:
            logger.info("No proxy configured, connecting directly")

        self.client = commands.Bot(
            command_prefix="!",
            intents=intents,
            help_command=None,
            proxy=proxy_url if proxy_url else None,
        )

        # 注册事件处理器
        @self.client.event
        async def on_ready():
            logger.info(f"Discord logged in as {self.client.user}")
            self._ready.set()

        @self.client.event
        async def on_message(message: discord.Message):
            await self._handle_message(message)

        # 启动客户端
        try:
            asyncio.create_task(self._run_client(token))
            async with asyncio.timeout(30):
                await self._ready.wait()

            self._connected = True
            logger.info("Discord channel connected")
            return True

        except asyncio.TimeoutError:
            logger.error("Timeout waiting for Discord ready event")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Discord: {e}")
            return False

    async def _run_client(self, token: str):
        """运行 Discord 客户端"""
        # 从环境变量获取代理 (与 connect 中保持一致)
        proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
        await self.client.start(token, proxy=proxy_url if proxy_url else None)

    async def disconnect(self) -> None:
        """断开 Discord 连接"""
        if self.client:
            await self.client.close()
        self._connected = False
        logger.info("Discord channel disconnected")

    async def _handle_message(self, message: discord.Message):
        """
        处理 Discord 消息

        流程：
        1. 忽略自己发的消息
        2. 检查是否 @了当前 bot (只响应被 @的消息)
        3. 如果是其他 bot @自己，允许处理 (bot 间协作)
        4. 转换为统一 Message 格式
        5. 如果有 Gateway，调用 Gateway 处理
        6. 加入消息队列
        """
        # 忽略自己发的消息
        if message.author == self.client.user:
            return

        # 只响应 @了当前 bot 的消息
        if not self.client.user:
            return
        bot_mention = f"<@{self.client.user.id}>"
        if bot_mention not in message.content:
            return

        # 如果是其他 bot @自己，允许处理 (bot 间协作)
        # 如果是用户消息，继续处理
        # 忽略 bot 消息的情况：没有 @当前 bot 且不是允许 bot 的情况
        if message.author.bot:
            # 已经检查过 @mention，如果是 @当前 bot 则允许处理
            # 这是为了支持 bot 间协作
            pass

        # 转换为统一 Message 格式
        unified_msg = self._to_unified_message(message)

        # 安全检查 (如果配置了 channel config)
        if self._config:
            security_ctx = await self.apply_security(unified_msg)

            if security_ctx.result == SecurityCheckResult.BLOCKED:
                logger.warning(f"Message blocked: {security_ctx.reason}")
                return

            if security_ctx.result == SecurityCheckResult.PAIRING_REQUIRED:
                await message.channel.send(
                    f"🔐 {message.author.mention} {security_ctx.reason}\n"
                    f"请使用 `!pair {security_ctx.pairing_code}` 批准访问"
                )
                return

        # 如果有 Gateway，调用 Gateway 处理
        if self.gateway:
            try:
                # Gateway 负责业务逻辑处理和响应发送
                # channel 只负责 API 对接
                await self.gateway._handle_message_from_channel(unified_msg, self)
            except Exception as e:
                logger.error(f"Gateway processing error: {e}")

        # 加入消息队列 (供外部监听)
        await self._queue_message(unified_msg)

        # 保存消息到 Bot 工作区日志（用于记忆中心监控）
        await self._save_message_to_bot_log(unified_msg, message)

    async def _save_message_to_bot_log(self, message: Message, discord_msg: discord.Message):
        """保存 Discord 消息到 Bot 工作区日志"""
        try:
            from datetime import datetime
            from pathlib import Path

            # 获取 Bot 名称（从 gateway）
            bot_name = getattr(self.gateway, 'bot_name', 'unknown')
            if not bot_name or bot_name == 'unknown':
                return  # 没有 Bot 名称，不保存

            # Bot 工作区日志目录
            bot_logs_dir = Path(f"workspaces/{bot_name}/shared_memory/logs")
            bot_logs_dir.mkdir(parents=True, exist_ok=True)

            # 今天的日志文件
            today = datetime.now().strftime("%Y-%m-%d")
            log_file = bot_logs_dir / f"{today}.md"

            # 格式化消息
            timestamp = datetime.fromtimestamp(message.timestamp).strftime("%H:%M")
            user_name = message.username or str(message.user_id)

            # 追加到日志文件
            log_entry = f"\n### [{timestamp}] {user_name}\n- **内容**: {message.content}\n"

            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)

        except Exception as e:
            logger.debug(f"Failed to save message to bot log: {e}")

    def _to_unified_message(self, message: discord.Message) -> Message:
        """将 Discord 消息转换为统一格式"""
        attachments = []
        for att in message.attachments:
            attachments.append(Attachment(
                type=self._guess_attachment_type(att.filename),
                url=att.url,
                filename=att.filename,
                size=att.size,
                mime_type=att.content_type,
            ))

        is_dm = isinstance(message.channel, discord.DMChannel)

        return Message(
            id=str(message.id),
            channel_id=str(message.channel.id),
            user_id=str(message.author.id),
            content=message.content,
            timestamp=message.created_at.timestamp(),
            role=MessageRole.USER,
            username=f"{message.author.name}#{message.author.discriminator}"
                     if hasattr(message.author, 'discriminator')
                     else message.author.name,
            attachments=attachments,
            metadata={
                "guild_id": str(message.guild.id) if message.guild else None,
                "is_dm": is_dm,
                "platform": "discord",
            },
            in_reply_to=str(message.reference.message_id) if message.reference else None,
        )

    def _guess_attachment_type(self, filename: str) -> str:
        """猜测附件类型"""
        if not filename:
            return "file"
        ext = filename.split(".")[-1].lower()
        if ext in ["png", "jpg", "jpeg", "gif", "webp", "bmp"]:
            return "image"
        elif ext in ["mp4", "webm", "mov", "avi"]:
            return "video"
        elif ext in ["mp3", "wav", "ogg", "flac"]:
            return "audio"
        else:
            return "file"

    async def send_message(
        self,
        to: str,
        content: str,
        in_reply_to: Optional[str] = None,
        attachments: Optional[List[Attachment]] = None,
    ) -> bool:
        """发送消息到 Discord"""
        if not self.client:
            logger.error("Discord client not connected")
            return False

        try:
            channel = self.client.get_channel(int(to))
            if not channel:
                channel = await self.client.fetch_channel(int(to))

            if not channel:
                logger.error(f"Channel {to} not found")
                return False

            reference = None
            if in_reply_to:
                try:
                    ref_msg = await channel.fetch_message(int(in_reply_to))
                    reference = ref_msg
                except discord.NotFound:
                    logger.warning(f"Reference message {in_reply_to} not found")

            if attachments:
                files = []
                for att in attachments:
                    if att.file_path:
                        files.append(discord.File(att.file_path))
                    elif att.url:
                        import aiohttp
                        async with aiohttp.ClientSession() as session:
                            async with session.get(att.url) as resp:
                                if resp.status == 200:
                                    data = await resp.read()
                                    files.append(discord.File(data, filename=att.filename))
                await channel.send(content, reference=reference, files=files)
            else:
                await channel.send(content, reference=reference)

            return True

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def send_typing(self, to: str) -> None:
        """发送打字状态 - 触发一次 typing"""
        if not self.client:
            return
        try:
            channel = self.client.get_channel(int(to))
            if channel:
                # 直接调用 HTTP API 发送 typing
                await channel._state.http.send_typing(channel.id)
        except Exception as e:
            logger.debug(f"Could not send typing indicator: {e}")

    def clean_protocol_markers(self, content: str) -> str:
        """清理协议标记，如 [ASK|...]、[CONFIRM|...] 等"""
        import re
        # Remove protocol markers like [ASK|req-xxx|BotName]
        content = re.sub(r'\[(ASK|CONFIRM|TASK|REPLY)\|[^\]]+\]', '', content)
        # Remove extra spaces caused by marker removal
        content = re.sub(r'\s+', ' ', content).strip()
        return content

    async def incoming_messages(self) -> AsyncIterator[Message]:
        """接收消息流"""
        while True:
            msg = await self._message_queue.get()
            yield msg

    def _is_dm_message(self, message: Message) -> bool:
        """判断是否是 DM 消息"""
        return message.metadata.get("is_dm", False)


# ==================== Discord 特定命令 ====================

def setup_discord_commands(bot: commands.Bot, channel: DiscordChannel):
    """设置 Discord 特定命令"""

    @bot.command(name="pair")
    async def pair_command(ctx: commands.Context, code: str):
        """配对命令：!pair <code>"""
        user_id = str(ctx.author.id)
        success = await channel.approve_pairing(user_id, code.upper())
        if success:
            await ctx.send("✅ 配对成功！您现在可以与我对话了")
        else:
            await ctx.send("❌ 配对码无效，请检查后重试")

    @bot.command(name="ping")
    async def ping_command(ctx: commands.Context):
        """测试命令：!ping"""
        await ctx.send(f"Pong! Latency: {round(bot.latency * 1000)}ms")

    logger.info("Discord commands registered")

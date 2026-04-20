#!/usr/bin/env python3
"""
Discord Channel Plugin - Phoenix Core Discord 连接器

将 Discord Bot 功能封装为 ChannelPlugin 接口

功能:
1. 接收 Discord 消息并转换为统一 Message 格式
2. 发送消息、回复、附件到 Discord
3. 支持 DM 配对、Allowlist 安全检查
4. 支持 @mention 识别

Usage:
    from channels.discord_channel import DiscordChannel

    channel = DiscordChannel()
    config = ChannelConfig(
        id="discord",
        name="Discord",
        credentials={"bot_token": "${DISCORD_BOT_TOKEN}"},
    )
    await channel.connect(config)
"""

import asyncio
import logging
from typing import Optional, AsyncIterator, List
from datetime import datetime

import discord
from discord.ext import commands

from .base import (
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

    def __init__(self):
        super().__init__()
        self.client: Optional[commands.Bot] = None
        self._ready = asyncio.Event()

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

        self.client = commands.Bot(
            command_prefix="!",
            intents=intents,
            help_command=None,  # 禁用默认帮助命令
        )

        # 注册事件处理器
        @self.client.event
        async def on_ready():
            logger.info(f"Discord logged in as {self.client.user} (ID: {self.client.user.id})")
            self._ready.set()

        @self.client.event
        async def on_message(message: discord.Message):
            await self._handle_message(message)

        # 启动客户端
        try:
            # 在后台任务中运行
            asyncio.create_task(self._run_client(token))

            # 等待 ready 事件
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
        await self.client.start(token)

    async def disconnect(self) -> None:
        """断开 Discord 连接"""
        if self.client:
            await self.client.close()
        self._connected = False
        logger.info("Discord channel disconnected")

    async def _handle_message(self, message: discord.Message):
        """处理 Discord 消息"""
        # 记录所有消息用于调试
        logger.info(f"[DISCORD] 作者={message.author} 频道={message.channel} 内容={message.content[:100]}")

        # 忽略自己发的消息
        if message.author == self.client.user:
            logger.info(f"忽略自己消息")
            return

        # 检查是否是 bot 消息
        is_bot_message = message.author.bot

        # 忽略 bot 消息 (可配置)
        if is_bot_message:
            # 例外：允许 [ASK|...] 和 [RESPONSE|...] 协议消息通过（用于 Bot 之间协作）
            import re
            has_ask_protocol = re.search(r'\[(ASK|DO|REQUEST|RESPONSE)\|', message.content)
            if has_ask_protocol:
                logger.info(f"Processing ASK/RESPONSE protocol from bot: {message.content[:50]}")
            elif not self._config or not self._config.settings.get("allow_bots", False):
                logger.info(f"Ignoring bot message")
                return

            # 检查是否是协议确认消息 ([CONFIRM|...], [DONE|...], [REPORT|...], [FAIL|...])
            # 这类消息不需要触发 AI 响应，只用于记录状态
            protocol_pattern = r'\[(CONFIRM|DONE|REPORT|FAIL)\|'
            if re.search(protocol_pattern, message.content):
                logger.info(f"Ignoring protocol confirmation message: {message.content[:50]}")
                return

            # 检查是否是 bot 上线/报到消息（自动发送的，不需要回复）
            # 这类消息通常包含"已上线"、"报到"等关键词，且没有 RequestID
            if any(keyword in message.content for keyword in ["已上线", "报到", "ready", "online"]):
                if not re.search(r'\[.*\|.*\|', message.content):  # 没有协议格式
                    logger.info(f"Ignoring bot startup message: {message.content[:50]}")
                    return

            # allow_bots=true 时，放过所有 bot 消息，不检查@mention
            # 让 Bot 自己的 SOUL.md 决定是否需要@自己
            logger.info(f"Processing bot message from {message.author}")
        else:
            # 人类消息：Worker Bot 应该只响应协议格式消息
            # 检查 Bot 名称是否是 Worker Bot（场控、运营等）
            import os
            bot_name = os.environ.get("BOT_NAME", "").lower()
            worker_bots = {"场控", "运营", "渠道", "美工", "编导", "剪辑", "客服"}

            if bot_name in worker_bots:
                # Worker Bot：响应协议格式消息 或 直接@它的消息
                import re
                has_protocol = re.search(r'\[(ASK|DO|REQUEST)\|', message.content)
                # 检查是否有@mention
                bot_mention = f"<@{self.client.user.id}>" if self.client.user else ""
                has_mention = bot_mention and bot_mention in message.content

                if not has_protocol and not has_mention:
                    logger.info(f"Ignoring human message (Worker Bot only responds to protocol or @mention): {message.content[:50]}")
                    return
                logger.info(f"Processing message (protocol={has_protocol}, mention={has_mention}): {message.content[:50]}")
            else:
                # 控制器 Bot（小小谦）：只响应@它的消息
                if not self.client.user:
                    logger.info("Discord client user not ready, ignoring message")
                    return
                bot_mention = f"<@{self.client.user.id}>"
                # 只处理@小小谦的消息
                if bot_mention not in message.content:
                    logger.info(f"Ignoring message (no @mention for controller): looking for '{bot_mention}'")
                    return
                logger.info(f"Controller bot mentioned, processing: {message.content[:50]}")

        # 转换为统一 Message 格式
        unified_msg = self._to_unified_message(message)
        logger.debug(f"Converted to unified message: {unified_msg.id}")

        # 安全检查
        security_ctx = await self.apply_security(unified_msg)

        if security_ctx.result == SecurityCheckResult.BLOCKED:
            logger.warning(f"Message blocked: {security_ctx.reason}")
            return

        if security_ctx.result == SecurityCheckResult.PAIRING_REQUIRED:
            # 发送配对提示
            await message.channel.send(
                f"🔐 {message.author.mention} {security_ctx.reason}\n"
                f"请使用 `!pair {security_ctx.pairing_code}` 批准访问"
            )
            return

        # 加入消息队列
        await self._queue_message(unified_msg)
        logger.info(f"Message queued: {unified_msg.id} from {message.author}")

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

        # 判断是否是 DM
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
                "channel_name": str(message.channel) if not is_dm else None,
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
        auto_delete: bool = False,
    ) -> bool:
        """发送消息到 Discord

        Args:
            to: 目标频道 ID
            content: 消息内容
            in_reply_to: 回复的消息 ID
            attachments: 附件列表
            auto_delete: 是否自动删除消息（用于协议消息）

        Returns:
            是否发送成功
        """
        if not self.client:
            logger.error("Discord client not connected")
            return False

        try:
            channel = self.client.get_channel(int(to))
            if not channel:
                # 尝试获取频道
                channel = await self.client.fetch_channel(int(to))

            if not channel:
                logger.error(f"Channel {to} not found")
                return False

            # 处理回复
            reference = None
            if in_reply_to:
                try:
                    ref_msg = await channel.fetch_message(int(in_reply_to))
                    reference = ref_msg
                except discord.NotFound:
                    logger.warning(f"Reference message {in_reply_to} not found")
                except Exception as e:
                    logger.warning(f"Failed to fetch reference message: {e}")

            # 发送消息
            sent_msg = None
            if attachments:
                files = []
                for att in attachments:
                    if att.file_path:
                        files.append(discord.File(att.file_path))
                    elif att.url:
                        # 从 URL 下载
                        import aiohttp
                        async with aiohttp.ClientSession() as session:
                            async with session.get(att.url) as resp:
                                if resp.status == 200:
                                    data = await resp.read()
                                    files.append(discord.File(data, filename=att.filename or "attachment"))

                sent_msg = await channel.send(content, reference=reference, files=files)
            else:
                sent_msg = await channel.send(content, reference=reference)

            # 自动删除消息（用于协议消息）
            # 暂时禁用删除功能
            # if auto_delete and sent_msg:
            #     try:
            #         await asyncio.sleep(2)
            #         await sent_msg.delete()
            #         logger.debug(f"Protocol message auto-deleted: {sent_msg.id}")
            #     except Exception as e:
            #         logger.warning(f"Failed to auto-delete message: {e}")

            logger.debug(f"Message sent to channel {to}")
            return True

        except Exception as e:
            logger.error(f"Failed to send message: {e}", exc_info=True)
            return False

    async def send_typing(self, to: str) -> None:
        """发送打字状态"""
        if not self.client:
            return

        channel = self.client.get_channel(int(to))
        if channel:
            try:
                # discord.py 2.0+: typing() returns a context manager
                # Use a short timeout to trigger typing then exit
                async with channel.typing():
                    await asyncio.sleep(0.1)  # Brief typing trigger
            except Exception as e:
                logger.debug(f"Could not send typing indicator: {e}")

    async def incoming_messages(self) -> AsyncIterator[Message]:
        """接收消息流"""
        while True:
            msg = await self._message_queue.get()
            yield msg

    def clean_protocol_markers(self, content: str) -> str:
        """清理协议标记，如 [ASK|...]、[CONFIRM|...] 等"""
        import re
        # Remove protocol markers like [ASK|req-xxx|BotName]
        content = re.sub(r'\[(ASK|CONFIRM|TASK|REPLY|RESPONSE)\|[^\]]+\]', '', content)
        # Remove extra spaces caused by marker removal
        content = re.sub(r'\s+', ' ', content).strip()
        return content

    def _is_dm_message(self, message: Message) -> bool:
        """判断是否是 DM 消息"""
        return message.metadata.get("is_dm", False)

    async def approve_pairing(self, user_id: str, pairing_code: str) -> bool:
        """批准 DM 配对"""
        success = await super().approve_pairing(user_id, pairing_code)
        if success and self._config:
            # 保存到配置
            if user_id not in self._config.allow_from:
                self._config.allow_from.append(user_id)
            logger.info(f"Approved pairing for user {user_id}")
        return success


# ==================== 命令支持 ====================

def setup_discord_commands(bot: commands.Bot, channel: DiscordChannel):
    """设置 Discord 命令"""

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

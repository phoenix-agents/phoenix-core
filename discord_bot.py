#!/usr/bin/env python3
"""
Phoenix Core Discord Bot

每个 Bot 独立的 Discord 连接器：
1. 从 workspace/.env 读取 DISCORD_BOT_TOKEN
2. 接收消息并路由到 Gateway
3. 发送响应回 Discord
4. 支持 @mention 识别

Usage:
    python3 discord_bot.py --bot 编导
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands

# Add Phoenix Core to path
sys.path.insert(0, str(Path(__file__).parent))

from phoenix_core_gateway import PhoenixCoreGateway

# Load Bot ID mapping
BOT_IDS_FILE = Path(__file__).parent / "bot_ids.json"
BOT_IDS = {}
if BOT_IDS_FILE.exists():
    with open(BOT_IDS_FILE, "r", encoding="utf-8") as f:
        BOT_IDS = json.load(f)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class DiscordBot:
    """
    Phoenix Core Discord Bot - 每个 Bot 独立的 Discord 连接器
    """

    # Discord 消息限制
    MAX_MESSAGE_LENGTH = 2000

    def __init__(self, bot_name: str):
        self.bot_name = bot_name
        self.workspace_dir = Path(f"workspaces/{bot_name}")
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        # Shared memory directory (all bots share this)
        self.shared_memory_dir = Path("shared_memory")
        self.shared_memory_dir.mkdir(parents=True, exist_ok=True)

        # Load bot config from .env
        self.bot_config = self._load_bot_config()

        # Get Discord token
        self.token = self.bot_config.get("DISCORD_BOT_TOKEN")
        if not self.token:
            raise ValueError(f"DISCORD_BOT_TOKEN not found in {self.workspace_dir}/.env")

        # Get client ID
        self.client_id = self.bot_config.get("DISCORD_CLIENT_ID")

        # Initialize Discord client
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        self.client = commands.Bot(
            command_prefix="!",
            intents=intents,
            client_id=int(self.client_id) if self.client_id else None
        )

        # Initialize Gateway
        self.gateway = PhoenixCoreGateway(bot_name)
        self.gateway.start()

        # Dedup cache
        self._seen_messages: dict[str, float] = {}
        self._SEEN_TTL = 300  # 5 minutes
        self._SEEN_MAX = 2000

        # Discussion turn control - each bot replies ONCE per round
        self._discussion_turns: dict[str, int] = {}  # channel_id -> turn count
        self._bot_replied_this_round: dict[str, set] = {}  # channel_id -> set of bot names that replied
        self._waiting_confirmation: set[str] = set()  # channels waiting for user confirmation

        # Bot ID mapping for cross-bot communication
        self.bot_ids = BOT_IDS.copy()

        # Setup event handlers
        self._setup_handlers()

    def _load_bot_config(self) -> dict:
        """Load bot configuration from .env file."""
        env_file = self.workspace_dir / ".env"
        config = {}

        if env_file.exists():
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        config[key.strip()] = value.strip()

        return config

    def _setup_handlers(self):
        """Setup Discord event handlers."""

        @self.client.event
        async def on_ready():
            logger.info(f"[{self.bot_name}] Discord bot ready!")
            logger.info(f"Bot ID: {self.client.user.id}")
            logger.info(f"Bot Name: {self.client.user.name}")
            logger.info(f"Connected to {len(self.client.guilds)} guilds")

            # Bot 上线后主动读取今日任务和共享上下文
            await self._on_startup()

        @self.client.event
        async def on_message(message: discord.Message):
            # Dedup: Discord RESUME replays events after reconnects
            msg_id = str(message.id)
            now = time.time()
            if msg_id in self._seen_messages:
                return
            self._seen_messages[msg_id] = now
            if len(self._seen_messages) > self._SEEN_MAX:
                cutoff = now - self._SEEN_TTL
                self._seen_messages = {
                    k: v for k, v in self._seen_messages.items()
                    if v > cutoff
                }

            # Ignore our own messages
            if message.author == self.client.user:
                return

            # Ignore Discord system messages
            if message.type not in (discord.MessageType.default, discord.MessageType.reply):
                return

            # Bot message filtering - 允许 Bot 间的@mention 消息通过
            if message.author.bot:
                # 检查是否是 Bot 间的@mention 通信
                bot_mentioned = self.client.user in message.mentions
                if not bot_mentioned:
                    return  # 非@mention 的 Bot 消息忽略
                # 允许@mention 的 Bot 消息通过（用于 Bot 间协作）

            # Check if bot was mentioned
            bot_mentioned = False
            if isinstance(message.channel, discord.DMChannel):
                bot_mentioned = True
            elif isinstance(message.channel, (discord.TextChannel, discord.Thread)):
                if self.client.user in message.mentions:
                    bot_mentioned = True

            if not bot_mentioned:
                await self.client.process_commands(message)
                return

            # Discussion turn control - check if bot should reply
            channel_id = str(message.channel.id)

            # Initialize channel state if needed
            if channel_id not in self._bot_replied_this_round:
                self._bot_replied_this_round[channel_id] = set()

            # Human user message = new discussion round, reset all states
            if not message.author.bot:
                self._discussion_turns[channel_id] = 0
                self._bot_replied_this_round[channel_id] = set()
                self._waiting_confirmation.discard(channel_id)

            # Check if this channel is waiting for user confirmation (after a full round)
            if channel_id in self._waiting_confirmation:
                logger.debug(f"[{self.bot_name}] Skipping - waiting for user confirmation")
                return

            # Check if this bot already replied in this round
            if self.bot_name in self._bot_replied_this_round[channel_id]:
                logger.debug(f"[{self.bot_name}] Already replied in this round")
                return

            # Process the message through Gateway
            await self._process_message(message, channel_id)

    async def _process_message(self, message: discord.Message, channel_id: str = None):
        """Process a Discord message through the Gateway."""
        logger.info(f"[{self.bot_name}] Received message from {message.author}: {message.content[:50]}...")

        try:
            # Get message content
            user_message = message.content

            # Remove @mention prefix
            if self.client.user in message.mentions:
                user_message = user_message.replace(f"<@{self.client.user.id}>", "").strip()
                user_message = user_message.replace(f"<@!{self.client.user.id}>", "").strip()

            if not user_message:
                return

            # Step 1: Add reaction to acknowledge receipt (👀 or 👌)
            try:
                await message.add_reaction("👀")
            except Exception as e:
                logger.debug(f"[{self.bot_name}] Could not add reaction: {e}")

            # Step 2: Show typing indicator
            async with message.channel.typing():
                # Process through Gateway (run in thread to avoid blocking event loop)
                response = await asyncio.to_thread(self.gateway.process_message, user_message)

            # Step 3: Send response (may include @other bots)
            if response:
                send_success = False
                try:
                    await self._send_response(message.channel, response, message)
                    send_success = True
                except Exception as e:
                    logger.error(f"[{self.bot_name}] Failed to send response: {e}")
                    # Still mark as replied to prevent duplicate replies
                    # Network failure shouldn't cause bot to reply again

                # Mark this bot as having replied in this round (regardless of send success)
                if channel_id:
                    self._bot_replied_this_round[channel_id].add(self.bot_name)
                    self._discussion_turns[channel_id] += 1

                    # Check if all mentioned bots have replied - if so, lock the channel
                    mentioned_bot_names = set()
                    for bot in message.mentions:
                        bot_name = bot.name
                        # Map Discord bot name to our bot names
                        for name in ["编导", "剪辑", "美工", "场控", "客服", "运营", "渠道", "小小谦"]:
                            if name in bot_name or bot_name == name:
                                mentioned_bot_names.add(name)

                    # If all mentioned bots have replied, enter confirmation-waiting state
                    if mentioned_bot_names <= self._bot_replied_this_round[channel_id]:
                        self._waiting_confirmation.add(channel_id)
                        logger.info(f"[{self.bot_name}] All mentioned bots replied, waiting for user confirmation")

                # Log to shared context (only if send succeeded)
                if send_success:
                    await self._log_to_shared_context(message, response)

            logger.info(f"[{self.bot_name}] Sent response: {response[:50]}...")

        except Exception as e:
            logger.error(f"[{self.bot_name}] Error processing message: {e}", exc_info=True)

    async def _send_response(self, channel, response: str, original_message: discord.Message = None):
        """Send response, handling @Bot mentions by routing to other bots."""
        chunks = self._split_message(response)

        for chunk in chunks:
            # Check if this chunk contains @Bot mentions (e.g., @运营，@编导)
            bot_mentions = self._extract_bot_mentions(chunk)

            if bot_mentions:
                # Send as message with proper Discord mentions
                mentioned_discord_ids = []
                for bot_name in bot_mentions:
                    bot_id = self.bot_ids.get(bot_name)
                    if bot_id:
                        mentioned_discord_ids.append(f"<@{bot_id}>")

                # Replace Chinese bot names with Discord IDs
                discord_chunk = chunk
                for bot_name in bot_mentions:
                    bot_id = self.bot_ids.get(bot_name)
                    if bot_id:
                        discord_chunk = discord_chunk.replace(f"@{bot_name}", f"<@{bot_id}>")

                await channel.send(discord_chunk)
            else:
                await channel.send(chunk)

    def _extract_bot_mentions(self, text: str) -> list:
        """Extract bot names from text like '@运营', '@编导'."""
        import re
        # Match @ followed by Chinese characters (bot names)
        matches = re.findall(r'@([\u4e00-\u9fa5]+)', text)
        # Filter to only known bot names
        return [m for m in matches if m in self.bot_ids]

    async def _log_to_shared_context(self, message: discord.Message, response: str):
        """Log important interactions to shared context."""
        # Skip ack-only responses
        if len(response) < 20 or response in ["收到", "在的", "好的", "明白"]:
            return

        # Skip if message is from another bot (bot-to-bot coordination)
        if message.author.bot:
            return

        # Log to shared log file
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self.shared_memory_dir / "logs" / f"{today}.md"

        # Ensure directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Prepare log entry
        time_str = datetime.now().strftime("%H:%M")
        user_name = message.author.name
        bot_name = self.bot_name
        response_preview = response[:100] + "..." if len(response) > 100 else response

        log_entry = f"\n### [{time_str}] {user_name} → {bot_name}\n- **内容**: {response_preview}\n"

        # Append to log file
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            logger.debug(f"[{self.bot_name}] Could not write to shared log: {e}")

        # Also log to database for cross-Bot querying
        try:
            from memory_share import share_memory
            share_memory(
                bot_name=bot_name,
                content=response_preview,
                visibility="public",
                tags=f"channel:{message.channel.id}",
                channel_id=str(message.channel.id)
            )
            logger.debug(f"[{self.bot_name}] Logged to shared memory database")
        except Exception as e:
            logger.debug(f"[{self.bot_name}] Could not log to shared memory database: {e}")

    async def _on_startup(self):
        """Bot startup routine - read daily tasks and shared context."""
        logger.info(f"[{self.bot_name}] Running startup routine...")

        # Read daily tasks
        task_file = self.shared_memory_dir / "今日任务.md"
        if task_file.exists():
            content = task_file.read_text(encoding="utf-8")
            logger.info(f"[{self.bot_name}] Loaded daily tasks ({len(content)} chars)")

        # Read streamer profile
        profile_file = self.shared_memory_dir / "主播资料.md"
        if profile_file.exists():
            content = profile_file.read_text(encoding="utf-8")
            logger.info(f"[{self.bot_name}] Loaded streamer profile ({len(content)} chars)")

        # Read team memory
        memory_file = self.shared_memory_dir / "MEMORY.md"
        if memory_file.exists():
            content = memory_file.read_text(encoding="utf-8")
            logger.info(f"[{self.bot_name}] Loaded team memory ({len(content)} chars)")

        # Read today's log
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self.shared_memory_dir / "logs" / f"{today}.md"
        if log_file.exists():
            content = log_file.read_text(encoding="utf-8")
            logger.info(f"[{self.bot_name}] Loaded today's log ({len(content)} chars)")

        logger.info(f"[{self.bot_name}] Startup routine completed")

        # Send startup message to Discord channel
        await self._send_startup_message()

    async def _send_startup_message(self):
        """Send a startup status message to Discord."""
        # Find the main text channel
        for channel in self.client.get_all_channels():
            if isinstance(channel, discord.TextChannel):
                # Load bot identity files for the status message
                soul_file = self.workspace_dir / "SOUL.md"
                identity_file = self.workspace_dir / "IDENTITY.md"
                agents_file = self.workspace_dir / "AGENTS.md"
                tools_file = self.workspace_dir / "TOOLS.md"

                identity_info = []
                if soul_file.exists():
                    identity_info.append("🎭 SOUL.md - 行为准则")
                if identity_file.exists():
                    identity_info.append("🆔 IDENTITY.md - 我是谁")
                if agents_file.exists():
                    identity_info.append("📋 AGENTS.md - 工作手册")
                if tools_file.exists():
                    identity_info.append("🛠️ TOOLS.md - 工具指南")

                # Load shared context info
                profile_file = self.shared_memory_dir / "主播资料.md"
                task_file = self.shared_memory_dir / "今日任务.md"
                memory_file = self.shared_memory_dir / "MEMORY.md"

                shared_info = []
                if profile_file.exists():
                    shared_info.append("📺 主播资料 - 谦总（谦歌行 277）完整档案")
                if task_file.exists():
                    shared_info.append("📋 今日任务")
                if memory_file.exists():
                    shared_info.append("🧠 团队共享记忆")

                status_message = f"""**{self.bot_name} 已上线** ✅

**已加载内容：**

🎭 **身份与角色**
{chr(10).join(identity_info)}

🎯 **工作信息**
{chr(10).join(shared_info)}
- 约 300 首歌单（草原/民族 25%、经典老歌 20%、流行情歌 25%、古风 15%、励志 10%）
- 招牌歌曲：《九儿》《可可托海的牧羊人》《套马杆》
- 粉丝画像：25-45 岁为主，女性略多

📊 **团队协作**
- 8 个 Bot 分工与协作规则
- Discord @mention 替换规则
- 反 Loop 规则

💡 **我可以做什么**
- 直播场控 - 监控数据、调节气氛、引导互动
- 数据分析 - 读取仪表盘、分析流量模式
- 记忆管理 - 记录直播数据、提炼流量密码
- 团队协作 - 与编导、运营、美工等配合

---
有什么需要我协助的吗？ 🎤"""

                try:
                    await channel.send(status_message)
                    logger.info(f"[{self.bot_name}] Sent startup message")
                    return  # Only send to first channel
                except Exception as e:
                    logger.debug(f"[{self.bot_name}] Could not send startup message: {e}")
                    return

    def _split_message(self, text: str) -> list:
        """Split a message into chunks that fit Discord's character limit."""
        if len(text) <= self.MAX_MESSAGE_LENGTH:
            return [text]

        chunks = []
        while len(text) > self.MAX_MESSAGE_LENGTH:
            split_point = text.rfind('\n', 0, self.MAX_MESSAGE_LENGTH)
            if split_point == -1:
                split_point = text.rfind(' ', 0, self.MAX_MESSAGE_LENGTH)
            if split_point == -1:
                split_point = self.MAX_MESSAGE_LENGTH

            chunks.append(text[:split_point].strip())
            text = text[split_point:].strip()

        if text:
            chunks.append(text)

        return chunks

    async def run(self):
        """Start the Discord bot."""
        logger.info(f"[{self.bot_name}] Starting Discord bot...")
        await self.client.start(self.token)

    def stop(self):
        """Stop the bot and cleanup."""
        logger.info(f"[{self.bot_name}] Stopping...")
        self.gateway.stop()


def main():
    parser = argparse.ArgumentParser(description="Phoenix Core Discord Bot")
    parser.add_argument("--bot", type=str, required=True, help="Bot name (e.g., 编导，剪辑)")
    args = parser.parse_args()

    bot = DiscordBot(args.bot)

    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info(f"[{args.bot}] Interrupted by user")
    finally:
        bot.stop()


if __name__ == "__main__":
    main()

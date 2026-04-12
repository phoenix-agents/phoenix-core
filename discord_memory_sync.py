#!/usr/bin/env python3
"""
Discord 记忆同步工具

自动从 Discord 获取聊天记录并保存到共享记忆目录，
让 bot 能够读取和理解上下文。

Usage:
    python3 discord_memory_sync.py --sync         # 同步最新消息
    python3 discord_memory_sync.py --full         # 完整同步所有历史
    python3 discord_memory_sync.py --status       # 查看同步状态
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import discord
from discord.ext import commands

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))

SHARED_MEMORY_DIR = Path(__file__).parent / "shared_memory")
DISCORD_HISTORY_DIR = SHARED_MEMORY_DIR / "discord_history"
PROJECTS_DIR = SHARED_MEMORY_DIR / "projects"
LOGS_DIR = SHARED_MEMORY_DIR / "logs"

# 确保目录存在
for d in [SHARED_MEMORY_DIR, DISCORD_HISTORY_DIR, PROJECTS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


class DiscordMemorySync:
    """Discord 记忆同步器"""

    def __init__(self, token: str, channel_id: int):
        self.token = token
        self.channel_id = channel_id
        self.client = commands.Bot(
            command_prefix="!",
            intents=discord.Intents.all()
        )
        self.channel = None
        self.last_sync_file = DISCORD_HISTORY_DIR / "last_sync.json"

    def load_last_sync(self) -> dict:
        """Load last sync info."""
        if self.last_sync_file.exists():
            with open(self.last_sync_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "last_message_id": None,
            "last_sync_time": None,
            "total_messages_synced": 0
        }

    def save_last_sync(self, info: dict):
        """Save last sync info."""
        with open(self.last_sync_file, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

    async def fetch_messages(self, limit: int = 100, after_message_id: int = None) -> list:
        """Fetch messages from Discord."""
        messages = []
        logger.info(f"Fetching messages from channel {self.channel_id}...")

        if after_message_id:
            # 增量同步：只获取新消息
            after = discord.Object(id=after_message_id)
            async for message in self.channel.history(limit=limit, after=after, oldest_first=True):
                messages.append(self._message_to_dict(message))
        else:
            # 完整同步
            async for message in self.channel.history(limit=limit, oldest_first=True):
                messages.append(self._message_to_dict(message))

        logger.info(f"Fetched {len(messages)} messages")
        return messages

    def _message_to_dict(self, message) -> dict:
        """Convert Discord message to dict."""
        return {
            "id": message.id,
            "timestamp": message.created_at.isoformat(),
            "author": {
                "id": message.author.id,
                "name": message.author.name,
                "bot": message.author.bot,
                "discriminator": message.author.discriminator
            },
            "content": message.content,
            "attachments": [
                {"url": str(att.url), "filename": att.filename}
                for att in message.attachments
            ],
            "mentions": [
                {"id": m.id, "name": m.name}
                for m in message.mentions
            ],
            "channel_id": message.channel.id
        }

    def save_to_daily_log(self, messages: list):
        """Save messages to daily shared log."""
        if not messages:
            return

        # Group messages by date
        by_date = {}
        for msg in messages:
            date = msg["timestamp"][:10]  # YYYY-MM-DD
            if date not in by_date:
                by_date[date] = []
            by_date[date].append(msg)

        # Save to daily log files
        for date, msgs in by_date.items():
            log_file = LOGS_DIR / f"{date}.md"

            # Build content
            content = f"# Discord 共享日志 - {date}\n\n"
            content += f"_共 {len(msgs)} 条消息_\n\n---\n\n"

            for msg in msgs:
                author = msg["author"]["name"]
                time = msg["timestamp"][11:16]  # HH:MM
                message_content = msg["content"]

                if message_content:
                    content += f"### [{time}] {author}\n"
                    content += f"{message_content}\n\n"

            # Append to file
            existing = ""
            if log_file.exists():
                with open(log_file, "r", encoding="utf-8") as f:
                    existing = f.read()

            # Only add if not already present
            if content not in existing:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write("\n" + content)

            logger.info(f"Saved {len(msgs)} messages to {log_file}")

    def save_to_projects(self, messages: list, category: str = "general"):
        """Save categorized messages to projects directory."""
        if not messages:
            return

        # Map keywords to categories
        keyword_map = {
            "生日": "生日方案",
            "生日会": "生日方案",
            "生日庆": "生日方案",
            "流量": "流量密码",
            "涨粉": "流量密码",
            "转粉": "流量密码",
            "歌单": "内容策划",
            "歌曲": "内容策划",
            "直播": "直播运营",
            "开播": "直播运营",
            "用户画像": "用户画像",
            "粉丝": "用户画像",
        }

        # Group messages by category
        by_category = {category: []}

        for msg in messages:
            content = msg["content"] or ""
            for keyword, cat in keyword_map.items():
                if keyword in content:
                    if cat not in by_category:
                        by_category[cat] = []
                    by_category[cat].append(msg)
                    break

        # Save to project files
        for cat, msgs in by_category.items():
            if not msgs:
                continue

            project_file = PROJECTS_DIR / f"Discord 历史 - {cat}.md"

            # Build content
            file_content = f"# Discord 历史记录 - {cat}\n\n"
            file_content += f"_更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}_\n\n"
            file_content += f"_共 {len(msgs)} 条相关消息_\n\n---\n\n"

            for msg in msgs:
                time = msg["timestamp"][:16].replace("T", " ")
                author = msg["author"]["name"]
                content = msg["content"]

                if content:
                    file_content += f"## {time} {author}\n\n"
                    file_content += f"{content}\n\n---\n\n"

            # Append to file
            existing = ""
            if project_file.exists():
                with open(project_file, "r", encoding="utf-8") as f:
                    existing = f.read()

            # Check if this content is already present (avoid duplicates)
            if file_content not in existing:
                with open(project_file, "a", encoding="utf-8") as f:
                    f.write("\n" + file_content)

            logger.info(f"Saved {len(msgs)} messages to {project_file}")

    async def sync(self, limit: int = 100, incremental: bool = True):
        """Sync Discord messages to shared memory."""
        @self.client.event
        async def on_ready():
            await self.run_sync(limit=limit, incremental=incremental)

        await self.client.start(self.token)

    async def run_sync(self, limit: int = 100, incremental: bool = True):
        """Run sync after client is ready."""
        await self.client.wait_until_ready()

        self.channel = self.client.get_channel(self.channel_id)
        if not self.channel:
            # Try to fetch
            try:
                self.channel = await self.client.fetch_channel(self.channel_id)
            except Exception as e:
                logger.error(f"Channel not found: {e}")
                await self.client.close()
                return

        logger.info(f"Connected to channel: #{self.channel.name}")

        # Load last sync info
        last_sync = self.load_last_sync()

        if incremental and last_sync.get("last_message_id"):
            # Incremental sync
            logger.info(f"Incremental sync from message {last_sync['last_message_id']}")
            messages = await self.fetch_messages(
                limit=limit,
                after_message_id=last_sync["last_message_id"]
            )
        else:
            # Full sync
            logger.info("Full sync")
            messages = await self.fetch_messages(limit=limit)

        if messages:
            # Save to daily logs
            self.save_to_daily_log(messages)

            # Save to projects (categorized)
            self.save_to_projects(messages)

            # Update last sync info
            last_sync["last_message_id"] = messages[-1]["id"]
            last_sync["last_sync_time"] = datetime.now().isoformat()
            last_sync["total_messages_synced"] += len(messages)
            self.save_last_sync(last_sync)

            logger.info(f"Sync complete: {len(messages)} new messages")
        else:
            logger.info("No new messages")

        await self.client.close()


async def main():
    parser = argparse.ArgumentParser(description="Discord Memory Sync")
    parser.add_argument("--sync", action="store_true", help="Sync recent messages")
    parser.add_argument("--full", action="store_true", help="Full sync all history")
    parser.add_argument("--limit", type=int, default=100, help="Message limit")
    parser.add_argument("--status", action="store_true", help="Show sync status")

    args = parser.parse_args()

    # Load token from env or bot config
    token = os.getenv("DISCORD_BOT_TOKEN", "")
    channel_id = int(os.getenv("DISCORD_CHANNEL_ID", "0"))

    # Try to load from bot config if not in env
    if not token or channel_id == 0:
        bot_config = Path(__file__).parent / "workspaces/场控/.env")
        if bot_config.exists():
            with open(bot_config, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("DISCORD_BOT_TOKEN="):
                        token = line.split("=", 1)[1].strip()
                    elif line.startswith("DISCORD_CHANNEL_ID="):
                        channel_id = int(line.split("=", 1)[1].strip())

    if not token:
        logger.error("DISCORD_BOT_TOKEN not found")
        return

    syncer = DiscordMemorySync(token, channel_id)

    if args.status:
        last_sync = syncer.load_last_sync()
        print(f"=== Discord Memory Sync Status ===")
        print(f"Last sync: {last_sync.get('last_sync_time', 'Never')}")
        print(f"Total messages synced: {last_sync.get('total_messages_synced', 0)}")
        print(f"Last message ID: {last_sync.get('last_message_id', 'N/A')}")
        return

    if args.sync or args.full:
        await syncer.sync(limit=args.limit, incremental=not args.full)


if __name__ == "__main__":
    asyncio.run(main())

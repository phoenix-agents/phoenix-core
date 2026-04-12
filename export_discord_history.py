#!/usr/bin/env python3
"""
Discord 历史记录自动导出工具

定期将 Discord 频道消息导出到 JSON 文件，支持增量更新。

Usage:
    python3 export_discord_history.py
    python3 export_discord_history.py --full  # 完整导出
    python3 export_discord_history.py --incremental  # 增量导出
"""

import argparse
import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import discord
from discord.ext import commands

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# 配置
DISCORD_HISTORY_FILE = Path("discord_channel_history.json")
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))


class DiscordHistoryExporter:
    """Discord 历史记录导出器"""

    def __init__(self, token: str, channel_id: int):
        self.token = token
        self.channel_id = channel_id
        self.client = commands.Bot(command_prefix="!", intents=discord.Intents.default())
        self.channel = None

    async def fetch_message_history(self, limit: int = 10000) -> list:
        """Fetch message history from Discord channel."""
        messages = []
        logger.info(f"Fetching up to {limit} messages from channel {self.channel_id}...")

        async for message in self.channel.history(limit=limit, oldest_first=True):
            msg_data = {
                "id": message.id,
                "timestamp": message.created_at.isoformat(),
                "author": {
                    "id": message.author.id,
                    "name": message.author.name,
                    "bot": message.author.bot
                },
                "content": message.content,
                "attachments": [
                    {
                        "url": att.url,
                        "filename": att.filename
                    } for att in message.attachments
                ],
                "mentions": [
                    {
                        "id": m.id,
                        "name": m.name
                    } for m in message.mentions
                ],
                "reactions": [
                    {
                        "emoji": str(r.emoji),
                        "count": r.count
                    } for r in message.reactions
                ]
            }
            messages.append(msg_data)

            if len(messages) % 500 == 0:
                logger.info(f"Fetched {len(messages)} messages...")

        logger.info(f"Fetched {len(messages)} messages total")
        return messages

    def load_existing_history(self) -> dict:
        """Load existing history file."""
        if DISCORD_HISTORY_FILE.exists():
            with open(DISCORD_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "channel_id": self.channel_id,
            "channel_name": "unknown",
            "total_messages": 0,
            "messages": [],
            "last_export": None
        }

    def save_history(self, history: dict):
        """Save history to file."""
        history["last_export"] = datetime.now().isoformat()
        history["total_messages"] = len(history["messages"])

        # Backup existing file
        if DISCORD_HISTORY_FILE.exists():
            backup_file = DISCORD_HISTORY_FILE.with_suffix(f".json.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            import shutil
            shutil.copy(DISCORD_HISTORY_FILE, backup_file)
            logger.info(f"Backup created: {backup_file}")

        # Save new file
        with open(DISCORD_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

        logger.info(f"History saved to {DISCORD_HISTORY_FILE}")

    def incremental_update(self, existing_history: dict, new_messages: list) -> dict:
        """Incrementally update existing history with new messages."""
        existing_ids = {msg["id"] for msg in existing_history.get("messages", [])}

        # Filter out messages we already have
        new_msgs = [msg for msg in new_messages if msg["id"] not in existing_ids]

        if new_msgs:
            logger.info(f"Found {len(new_msgs)} new messages")
            # Merge and sort by timestamp
            existing_history["messages"].extend(new_msgs)
            existing_history["messages"].sort(
                key=lambda x: datetime.fromisoformat(x["timestamp"].replace("+00:00", ""))
            )
            existing_history["total_messages"] = len(existing_history["messages"])
        else:
            logger.info("No new messages found")

        return existing_history

    async def run(self, full: bool = False):
        """Run the exporter."""
        @self.client.event
        async def on_ready():
            try:
                self.channel = self.client.get_channel(self.channel_id)
                if not self.channel:
                    self.channel = await self.client.fetch_channel(self.channel_id)

                logger.info(f"Connected to channel: #{self.channel.name}")

                # Update channel info
                history = self.load_existing_history()
                history["channel_id"] = self.channel.id
                history["channel_name"] = self.channel.name

                if full or not history.get("messages"):
                    # Full export
                    messages = await self.fetch_message_history(limit=10000)
                    history["messages"] = messages
                else:
                    # Incremental export - fetch recent messages
                    logger.info("Performing incremental export...")
                    recent_messages = await self.fetch_message_history(limit=1000)
                    history = self.incremental_update(history, recent_messages)

                self.save_history(history)
                logger.info(f"Export complete! Total messages: {history['total_messages']}")

            except Exception as e:
                logger.error(f"Export failed: {e}", exc_info=True)
            finally:
                await self.client.close()

        await self.client.start(self.token)


def main():
    parser = argparse.ArgumentParser(description="Export Discord channel history")
    parser.add_argument("--full", action="store_true", help="Full export (re-fetch all messages)")
    parser.add_argument("--incremental", action="store_true", help="Incremental export (only new messages)")
    args = parser.parse_args()

    if not DISCORD_TOKEN:
        logger.error("DISCORD_BOT_TOKEN not found in environment")
        return

    if DISCORD_CHANNEL_ID == 0:
        logger.error("DISCORD_CHANNEL_ID not found in environment")
        return

    exporter = DiscordHistoryExporter(DISCORD_TOKEN, DISCORD_CHANNEL_ID)

    try:
        asyncio.run(exporter.run(full=args.full))
    except KeyboardInterrupt:
        logger.info("Export interrupted")


if __name__ == "__main__":
    main()

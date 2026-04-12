#!/usr/bin/env python3
"""
Discord 历史记录导入工具

将 Discord 频道历史记录导入到共享上下文中，让所有 Bot 都能看到之前的对话。

Usage:
    python3 import_discord_history.py --bot 场控 --limit 100
    python3 import_discord_history.py --all --limit 500
"""

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# 配置
DISCORD_HISTORY_FILE = Path("discord_channel_history.json")
SHARED_MEMORY_DIR = Path("shared_memory")
SHARED_LOGS_DIR = SHARED_MEMORY_DIR / "logs"


def load_discord_history():
    """Load Discord channel history from JSON file."""
    if not DISCORD_HISTORY_FILE.exists():
        logger.error(f"Discord history file not found: {DISCORD_HISTORY_FILE}")
        return None

    with open(DISCORD_HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_recent_conversations(messages: list, limit: int = 100) -> list:
    """Extract recent conversations from messages."""
    conversations = []

    # Group messages by conversation (messages within 5 minutes)
    current_conv = []
    last_timestamp = None

    for msg in messages[:limit]:
        msg_time = datetime.fromisoformat(msg["timestamp"].replace("+00:00", ""))

        if last_timestamp and (last_timestamp - msg_time).total_seconds() > 300:
            # New conversation
            if current_conv:
                conversations.append(current_conv)
            current_conv = []

        current_conv.append(msg)
        last_timestamp = msg_time

    if current_conv:
        conversations.append(current_conv)

    return conversations


def format_conversation(conversation: list, preserve_full_content: bool = True) -> str:
    """Format a conversation for shared log."""
    lines = []

    for msg in conversation:
        author = msg["author"]["name"]
        content = msg["content"]
        timestamp = msg["timestamp"][:16].replace("T", " ")

        # Preserve full content for important messages
        if not preserve_full_content and len(content) > 500:
            content = content[:500] + "\n\n[...内容已截断，查看原始 Discord 历史...]"

        lines.append(f"**{timestamp} {author}**: {content}")

    return "\n\n".join(lines)


def import_to_shared_log(conversations: list, bot_name: str = None):
    """Import conversations to shared log file."""
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = SHARED_LOGS_DIR / f"{today}.md"

    # Ensure directory exists
    SHARED_LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # Read existing content
    existing_content = ""
    if log_file.exists():
        with open(log_file, "r", encoding="utf-8") as f:
            existing_content = f.read()

    # Build new section
    new_section = f"\n\n## Discord 历史对话导入 ({datetime.now().strftime('%H:%M')})\n\n"

    if bot_name:
        new_section += f"_为 {bot_name} 导入的上下文_\n\n"

    for i, conv in enumerate(conversations[:10], 1):  # Limit to 10 conversations
        new_section += f"\n### 对话 {i}\n"
        new_section += format_conversation(conv)
        new_section += "\n\n---\n"

    # Append to file
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(existing_content + new_section)

    logger.info(f"Imported {len(conversations)} conversations to {log_file}")


def main():
    parser = argparse.ArgumentParser(description="Import Discord history to shared memory")
    parser.add_argument("--bot", type=str, help="Bot name to import for")
    parser.add_argument("--all", action="store_true", help="Import all history")
    parser.add_argument("--limit", type=int, default=100, help="Limit messages to import")

    args = parser.parse_args()

    # Load Discord history
    logger.info("Loading Discord history...")
    history = load_discord_history()

    if not history:
        return

    logger.info(f"Loaded {history.get('total_messages', 0)} messages from channel #{history.get('channel_name', 'unknown')}")

    # Extract recent conversations
    messages = history.get("messages", [])
    conversations = extract_recent_conversations(messages, args.limit)

    logger.info(f"Extracted {len(conversations)} conversations")

    # Import to shared log
    import_to_shared_log(conversations, args.bot)

    logger.info("Import complete!")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Discord 历史记录导入工具 - 完整版

将 Discord 频道历史记录导入到共享上下文中，按主题分类存储。

Usage:
    python3 import_discord_history_full.py
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
SHARED_PROJECTS_DIR = SHARED_MEMORY_DIR / "projects"


def load_discord_history():
    """Load Discord channel history from JSON file."""
    if not DISCORD_HISTORY_FILE.exists():
        logger.error(f"Discord history file not found: {DISCORD_HISTORY_FILE}")
        return None

    with open(DISCORD_HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def find_key_conversations(messages: list) -> dict:
    """Find key conversations by topic."""
    topics = {
        "生日方案": [],
        "直播运营": [],
        "流量密码": [],
        "用户画像": [],
        "内容策划": [],
        "其他": []
    }

    keywords = {
        "生日方案": ["生日", "生日直播", "生日庆", "生日方案", "生日会"],
        "直播运营": ["直播", "开播", "场控", "流量", "观众"],
        "流量密码": ["流量密码", "流量池", "推流", "权重"],
        "用户画像": ["用户画像", "用户分析", "观众分析", "粉丝"],
        "内容策划": ["内容", "策划", "脚本", "选题", "创意"]
    }

    for msg in messages:
        content = msg.get("content", "").lower()
        author = msg.get("author", {}).get("name", "")

        # Skip bot introduction messages
        if "我是" in content and "Bot" in content:
            continue

        matched = False
        for topic, kw_list in keywords.items():
            for kw in kw_list:
                if kw in content:
                    topics[topic].append(msg)
                    matched = True
                    break
            if matched:
                break

        if not matched and len(content) > 20:
            topics["其他"].append(msg)

    return topics


def create_topic_file(topic: str, messages: list):
    """Create a topic-specific file in projects directory."""
    SHARED_PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    filename = SHARED_PROJECTS_DIR / f"Discord 历史-{topic}.md"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# Discord 历史记录 - {topic}\n\n")
        f.write(f"_导入时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}_\n\n")
        f.write(f"_共 {len(messages)} 条相关消息_\n\n")
        f.write("---\n\n")

        # Group by date
        current_date = None
        for msg in messages[-200:]:  # Limit to last 200 per topic
            msg_date = msg["timestamp"][:10]
            if msg_date != current_date:
                current_date = msg_date
                f.write(f"\n## {current_date}\n\n")

            author = msg["author"]["name"]
            content = msg["content"]
            timestamp = msg["timestamp"][11:16]

            f.write(f"### {timestamp} {author}\n\n")
            f.write(f"{content}\n\n")

    logger.info(f"Created {filename} with {min(len(messages), 200)} messages")


def import_full_history():
    """Import full Discord history organized by topic."""
    logger.info("Loading Discord history...")
    history = load_discord_history()

    if not history:
        return

    logger.info(f"Loaded {history.get('total_messages', 0)} messages from channel #{history.get('channel_name', 'unknown')}")

    messages = history.get("messages", [])

    # Find key conversations by topic
    logger.info("Analyzing conversations by topic...")
    topics = find_key_conversations(messages)

    for topic, msgs in topics.items():
        if msgs:
            logger.info(f"Found {len(msgs)} messages for topic: {topic}")
            create_topic_file(topic, msgs)

    # Update main log with summary
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = SHARED_LOGS_DIR / f"{today}.md"

    summary = f"""

## Discord 完整历史导入 - {datetime.now().strftime('%H:%M')}

已导入全部 {len(messages)} 条 Discord 消息，按主题分类存储：

| 主题 | 消息数 | 文件位置 |
|------|--------|---------|
"""

    for topic, msgs in topics.items():
        if msgs:
            summary += f"| {topic} | {len(msgs)} | `shared_memory/projects/Discord 历史-{topic}.md` |\n"

    summary += f"""
**所有 Bot 现在可以访问完整的 Discord 历史记录了！**

---
"""

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(summary)

    logger.info("Full import complete!")


if __name__ == "__main__":
    import_full_history()

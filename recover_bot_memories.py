#!/usr/bin/env python3
"""
Recover Bot memories from Discord channel history
and save to Phoenix Core workspace memory structure.
"""

import json
import os
from datetime import datetime
from pathlib import Path

# Configuration
DISCORD_HISTORY_FILE = str(Path(__file__).parent / "discord_channel_history.json")
PHOENIX_CORE_DIR = str(Path(__file__).parent)

# Bot name mapping (Discord name -> workspace name)
BOT_MAPPING = {
    "编导": "编导",
    "剪辑": "剪辑",
    "美工": "美工",
    "场控": "场控",
    "客服": "客服",
    "运营": "运营",
    "渠道": "渠道",
    "小小谦": "小小谦",
    "美工/设计": "美工",
    "视频剪辑": "剪辑",
    "粉丝运营": "运营",
}

# Memory categories based on content keywords
MEMORY_CATEGORIES = {
    "项目": ["直播", "策划", "方案", "生日", "活动", "project", "plan"],
    "知识库": ["知识", "技能", "能力", "介绍", "template", "guide", "教程", "方法"],
    "学习笔记": ["学习", "笔记", "总结", "复盘", "心得", "learn", "study"],
    "日志": ["日志", "记录", "日报", "总结", "review"],
}

def categorize_message(content: str) -> str:
    """Categorize message content into memory category."""
    content_lower = content.lower()

    for category, keywords in MEMORY_CATEGORIES.items():
        for keyword in keywords:
            if keyword in content_lower:
                return category

    # Default to knowledge base for substantial bot responses
    if len(content) > 200:
        return "知识库"

    return "日志"

def extract_memory_from_message(msg: dict) -> dict:
    """Extract memory data from a Discord message."""
    return {
        "id": msg["id"],
        "timestamp": msg["timestamp"],
        "author": msg["author"]["name"],
        "content": msg["content"],
        "category": categorize_message(msg["content"]),
    }

def save_memory_to_workspace(bot_name: str, memory: dict, output_dir: Path):
    """Save memory to bot workspace."""
    workspace_dir = output_dir / f"workspaces/{bot_name}" / "memory"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    category_dir = workspace_dir / memory["category"]
    category_dir.mkdir(parents=True, exist_ok=True)

    # Create memory file
    date_str = memory["timestamp"][:10].replace("-", "")
    memory_file = category_dir / f"{date_str}_{memory['id']}.md"

    content = f"""# Bot Memory - {memory['author']}

**来源**: Discord 频道对话
**日期**: {memory['timestamp']}
**消息 ID**: {memory['id']}
**分类**: {memory['category']}

---

{memory['content']}

---

_此文件由 Phoenix Core 记忆恢复系统自动生成_
"""

    with open(memory_file, "w", encoding="utf-8") as f:
        f.write(content)

    return memory_file

def recover_bot_memories():
    """Main function to recover all bot memories."""
    print("=== Phoenix Core Bot 记忆恢复系统 ===\n")

    # Load Discord history
    with open(DISCORD_HISTORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"已加载 {len(data['messages'])} 条 Discord 消息\n")

    # Group messages by bot
    bot_memories = {}
    for msg in data["messages"]:
        if not msg["author"]["bot"]:
            continue

        discord_name = msg["author"]["name"]
        workspace_name = BOT_MAPPING.get(discord_name)

        if not workspace_name:
            print(f"⚠️  未找到 Bot 映射：{discord_name}")
            continue

        if workspace_name not in bot_memories:
            bot_memories[workspace_name] = []

        memory = extract_memory_from_message(msg)
        memory["workspace"] = workspace_name
        bot_memories[workspace_name].append(memory)

    # Statistics
    print("=== Bot 记忆统计 ===")
    for bot_name, memories in sorted(bot_memories.items(), key=lambda x: -len(x[1])):
        print(f"  {bot_name}: {len(memories)} 条记忆")
    print()

    # Save memories (limit to most important ones first)
    print("正在保存记忆到各 Bot workspace...\n")

    total_saved = 0
    for bot_name, memories in bot_memories.items():
        workspace_dir = Path(PHOENIX_CORE_DIR)
        saved_count = 0

        for memory in memories:
            # Only save substantial memories (avoid short chat messages)
            if len(memory["content"]) < 50:
                continue

            try:
                save_memory_to_workspace(bot_name, memory, workspace_dir)
                saved_count += 1
                total_saved += 1
            except Exception as e:
                print(f"❌ 保存失败 {bot_name}: {e}")

        if saved_count > 0:
            print(f"✅ {bot_name}: 保存 {saved_count} 条记忆")

    print(f"\n=== 记忆恢复完成 ===")
    print(f"总计恢复：{total_saved} 条记忆")
    print(f"存储位置：{PHOENIX_CORE_DIR}/workspaces/*/memory/")

if __name__ == "__main__":
    recover_bot_memories()

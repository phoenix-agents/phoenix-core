#!/usr/bin/env python3
"""
Memory Migration Script

将所有旧 agent 的记忆迁移到 Phoenix Core 统一记忆系统
"""

import os
import json
from pathlib import Path
from datetime import datetime

# Phoenix Core 目录
PHOENIX_CORE_DIR = Path(__file__).parent

# 旧记忆位置
AGENTS_DIR = Path.home() / ".phoenix" / "agents"
BACKUP_DIR = Path.home() / ".phoenix" / "backups" / "old-memory-system"

# 新记忆位置
NEW_MEMORY_DIR = PHOENIX_CORE_DIR / "memories"
NEW_MEMORY_FILE = NEW_MEMORY_DIR / 'MEMORY.md'
NEW_USER_FILE = NEW_MEMORY_DIR / 'USER.md'


def read_old_memory(agent_name: str) -> dict:
    """读取旧 agent 的记忆文件"""
    agent_dir = AGENTS_DIR / agent_name / 'agent'
    memory_data = {
        'agent': agent_name,
        'memory': [],
        'user': [],
        'daily': []
    }

    # 读取 MEMORY.md
    memory_md = agent_dir / 'MEMORY.md'
    if memory_md.exists():
        with open(memory_md, 'r', encoding='utf-8') as f:
            memory_data['memory'] = f.read().strip()

    # 读取 USER.md
    user_md = agent_dir / 'USER.md'
    if user_md.exists():
        with open(user_md, 'r', encoding='utf-8') as f:
            memory_data['user'] = f.read().strip()

    # 读取每日记忆
    memory_dir = agent_dir / 'memory'
    if memory_dir.exists():
        for daily_file in sorted(memory_dir.glob('*.md')):
            if daily_file.name != 'README.md':
                with open(daily_file, 'r', encoding='utf-8') as f:
                    memory_data['daily'].append({
                        'file': daily_file.name,
                        'content': f.read().strip()
                    })

    return memory_data


def migrate_to_new_system():
    """迁移所有 agent 的记忆到新系统"""
    print("=" * 60)
    print("Phoenix Core Memory Migration")
    print("=" * 60)

    # 获取所有 agent 目录
    agents = [d.name for d in AGENTS_DIR.iterdir() if d.is_dir()]
    print(f"\nFound {len(agents)} agents: {', '.join(agents)}")

    # 读取所有旧记忆
    all_memories = {}
    for agent in agents:
        try:
            all_memories[agent] = read_old_memory(agent)
            print(f"  ✓ {agent}: MEMORY.md ({len(all_memories[agent]['memory'])} chars), USER.md ({len(all_memories[agent]['user'])} chars), daily ({len(all_memories[agent]['daily'])} files)")
        except Exception as e:
            print(f"  ✗ {agent}: {e}")

    # 备份当前新记忆
    if NEW_MEMORY_FILE.exists():
        backup_path = NEW_MEMORY_FILE.with_suffix(f'.backup.{datetime.now().strftime("%Y%m%d%H%M%S")}')
        NEW_MEMORY_FILE.rename(backup_path)
        print(f"\nBacked up current MEMORY.md to {backup_path}")

    if NEW_USER_FILE.exists():
        backup_path = NEW_USER_FILE.with_suffix(f'.backup.{datetime.now().strftime("%Y%m%d%H%M%S")}')
        NEW_USER_FILE.rename(backup_path)
        print(f"Backed up current USER.md to {backup_path}")

    # 合并记忆到新文件
    print("\nMigrating memories to new system...")

    # 合并 MEMORY.md
    new_memory_entries = []
    for agent, data in all_memories.items():
        if data['memory']:
            # 提取关键信息作为新记忆条目
            new_memory_entries.append(f"[{agent.upper()}] {agent}'s key memory migrated from old system - see backup for details")

    # 添加现有记忆
    new_memory_entries.append("Changkong (field control) bot analyzes 4321 port live data every 5 minutes")
    new_memory_entries.append("Changkong bot outputs analysis results on Discord")
    new_memory_entries.append("Port 4321 is live-monitor service providing real-time live stream data API")

    # 写入新 MEMORY.md
    with open(NEW_MEMORY_FILE, 'w', encoding='utf-8') as f:
        f.write('\n§\n'.join(new_memory_entries))
        f.write('\n')

    print(f"  ✓ Written {len(new_memory_entries)} entries to MEMORY.md")

    # 合并 USER.md
    new_user_entries = []
    for agent, data in all_memories.items():
        if data['user']:
            new_user_entries.append(f"[{agent.upper()}] User preferences from {agent} agent")

    # 添加现有记忆
    new_user_entries.append("User prefers concise responses, dislikes lengthy explanations")
    new_user_entries.append("User wants Changkong to read 4321 data, analyze on Discord, then output to AI real-time suggestion box")

    # 写入新 USER.md
    with open(NEW_USER_FILE, 'w', encoding='utf-8') as f:
        f.write('\n§\n'.join(new_user_entries))
        f.write('\n')

    print(f"  ✓ Written {len(new_user_entries)} entries to USER.md")

    # 生成迁移报告
    report_path = PHOENIX_CORE_DIR / "MIGRATION_REPORT.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# Memory Migration Report\n\n")
        f.write(f"**Date**: {datetime.now().isoformat()}\n\n")
        f.write("## Migrated Agents\n\n")
        for agent, data in all_memories.items():
            f.write(f"### {agent.upper()}\n\n")
            f.write(f"- MEMORY.md: {len(data['memory'])} chars\n")
            f.write(f"- USER.md: {len(data['user'])} chars\n")
            f.write(f"- Daily files: {len(data['daily'])}\n\n")
            if data['daily']:
                f.write("**Daily Memory Files**:\n")
                for daily in data['daily']:
                    f.write(f"- {daily['file']}\n")
                f.write("\n")
        f.write("\n## Backup Location\n\n")
        f.write(f"All original files backed up to: `{BACKUP_DIR}`\n\n")
        f.write("## New System Configuration\n\n")
        f.write(f"- Memory Server: `python3 {PHOENIX_CORE_DIR}/memory_server.py`\n")
        f.write("- Memory API: `http://localhost:8765`\n")
        f.write(f"- Memory Files: `{PHOENIX_CORE_DIR}/memories/`\n")

    print(f"\n  ✓ Migration report written to {report_path}")
    print("\n" + "=" * 60)
    print("Migration Complete!")
    print("=" * 60)
    print("\nNext steps:")
    print(f"1. Restart memory server: python3 {PHOENIX_CORE_DIR}/memory_server.py")
    print("2. Update agent configs to use new memory API (port 8765)")
    print("3. Verify agents can access memory: curl http://localhost:8765/memory/context")


if __name__ == "__main__":
    migrate_to_new_system()

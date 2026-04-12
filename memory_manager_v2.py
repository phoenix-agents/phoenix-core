#!/usr/bin/env python3
"""
Memory Manager v2.0 - 分层记忆系统

Phoenix Core Phoenix v2.0 核心模块

五层记忆架构:
- L1: 工作记忆 (Working Memory) - 当前任务上下文，~2000 tokens
- L2: 短期记忆 (Short-term) - 最近 3 天日志，~5000 tokens
- L3: 核心记忆 (Core Memory) - MEMORY.md/USER.md, ~3500 tokens
- L4: 技能记忆 (Skill Memory) - skills/目录，按需加载
- L5: 归档记忆 (Archive) - SQLite FTS5, 全文搜索

Usage:
    from memory_manager_v2 import MemoryManagerV2

    manager = MemoryManagerV2(bot_name="编导")
    manager.add_memory("用户偏好：喜欢简洁的回复", priority="high")
    context = manager.build_memory_context()
"""

import json
import logging
import os
import sqlite3
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import OrderedDict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 各层级 token 限制
L1_WORKING_TOKEN_LIMIT = 2000
L2_SHORTTERM_TOKEN_LIMIT = 5000
L3_CORE_TOKEN_LIMIT = 3500
# L4 和 L5 按需加载，无硬性限制


class MemoryLayer:
    """记忆层级基类"""

    def __init__(self, name: str, token_limit: int):
        self.name = name
        self.token_limit = token_limit
        self.entries: List[Dict] = []

    def add(self, content: str, metadata: Dict = None) -> bool:
        """添加记忆条目"""
        raise NotImplementedError

    def get_context(self) -> str:
        """获取记忆上下文"""
        raise NotImplementedError

    def token_count(self) -> int:
        """估算 token 数"""
        return sum(len(e.get('content', '')) for e in self.entries) // 4  # 粗略估算


class L1_WorkingMemory(MemoryLayer):
    """
    L1: 工作记忆
    - 当前任务上下文
    - 对话历史 (最近 10 轮)
    - 容量：~2000 tokens
    """

    def __init__(self, bot_name: str):
        super().__init__("working", L1_WORKING_TOKEN_LIMIT)
        self.bot_name = bot_name
        self.max_entries = 20  # 最近 20 条

    def add(self, content: str, metadata: Dict = None) -> bool:
        entry = {
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
            "type": metadata.get("type", "general")
        }
        self.entries.append(entry)

        # LRU 驱逐：保持最近 N 条
        while len(self.entries) > self.max_entries:
            self.entries.pop(0)

        return True

    def get_context(self) -> str:
        """获取工作记忆上下文"""
        if not self.entries:
            return ""

        context_parts = []
        for entry in self.entries[-10:]:  # 最近 10 条
            context_parts.append(f"[{entry.get('type', 'general')}] {entry['content']}")

        return "\n".join(context_parts)

    def clear(self):
        """清空工作记忆 (任务完成后)"""
        self.entries = []


class L2_ShortTermMemory(MemoryLayer):
    """
    L2: 短期记忆
    - 最近 3 天日志
    - 自动清理 (3 天后归档)
    - 容量：~5000 tokens
    """

    def __init__(self, bot_name: str):
        super().__init__("short_term", L2_SHORTTERM_TOKEN_LIMIT)
        self.bot_name = bot_name
        self.log_dir = Path(f"workspaces/{bot_name}/DYNAMIC/learnings")
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def load_recent_logs(self, days: int = 3):
        """加载最近 N 天的日志"""
        self.entries = []
        cutoff_date = datetime.now() - timedelta(days=days)

        for log_file in self.log_dir.glob("*.md"):
            try:
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime >= cutoff_date:
                    content = log_file.read_text(encoding="utf-8")
                    self.entries.append({
                        "content": content[:1000],  # 限制每条长度
                        "source": log_file.name,
                        "timestamp": mtime.isoformat(),
                        "type": "log"
                    })
            except Exception as e:
                logger.error(f"Failed to load log {log_file}: {e}")

        return len(self.entries)

    def add(self, content: str, metadata: Dict = None) -> bool:
        """添加日志到短期记忆"""
        # 写入日志文件
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = self.log_dir / f"{date_str}.md"

        # 确保 metadata 不为 None
        if metadata is None:
            metadata = {}

        log_entry = f"""
## [{datetime.now().strftime("%H:%M")}] {metadata.get('event', 'Event')}

{content}

---
"""
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)

        # 同时加入内存
        self.entries.append({
            "content": content[:500],
            "metadata": metadata,
            "timestamp": datetime.now().isoformat(),
            "type": metadata.get("type", "log"),
            "source": log_file.name
        })

        return True

    def get_context(self) -> str:
        """获取短期记忆上下文"""
        if not self.entries:
            return ""

        # 按时间排序
        sorted_entries = sorted(
            self.entries,
            key=lambda x: x.get('timestamp', ''),
            reverse=True
        )[:10]  # 最近 10 条

        context_parts = []
        for entry in sorted_entries:
            source = entry.get('source', 'unknown')
            context_parts.append(f"[{source}] {entry['content'][:200]}")

        return "\n---\n".join(context_parts)

    def archive_old_logs(self, days: int = 3) -> int:
        """归档 3 天前的日志"""
        archived = 0
        cutoff_date = datetime.now() - timedelta(days=days)

        for log_file in self.log_dir.glob("*.md"):
            try:
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime < cutoff_date:
                    # 移动到归档 (这里简化为标记)
                    archived += 1
                    logger.debug(f"Archived log: {log_file.name}")
            except Exception as e:
                logger.error(f"Failed to archive log {log_file}: {e}")

        return archived


class L3_CoreMemory(MemoryLayer):
    """
    L3: 核心记忆
    - 用户偏好 (USER.md)
    - 环境事实
    - 工具 quirks
    - 容量：~3500 tokens
    """

    def __init__(self, bot_name: str):
        super().__init__("core", L3_CORE_TOKEN_LIMIT)
        self.bot_name = bot_name
        self.workspace_dir = Path(f"workspaces/{bot_name}")
        self.memory_file = self.workspace_dir / "MEMORY.md"
        self.user_file = self.workspace_dir / "USER.md"

    def load_from_disk(self):
        """从磁盘加载核心记忆"""
        self.entries = []

        # 加载 MEMORY.md
        if self.memory_file.exists():
            content = self.memory_file.read_text(encoding="utf-8")
            self.entries.append({
                "content": content,
                "source": "MEMORY.md",
                "type": "memory"
            })

        # 加载 USER.md
        if self.user_file.exists():
            content = self.user_file.read_text(encoding="utf-8")
            self.entries.append({
                "content": content,
                "source": "USER.md",
                "type": "user"
            })

        return len(self.entries)

    def add(self, content: str, metadata: Dict = None) -> bool:
        """添加核心记忆"""
        entry_type = metadata.get("type", "general") if metadata else "general"

        # 添加到相应用户文件
        if entry_type == "user":
            target_file = self.user_file
        else:
            target_file = self.memory_file

        # 追加到文件
        with open(target_file, "a", encoding="utf-8") as f:
            f.write(f"\n§\n{content}\n")

        # 同时加入内存
        self.entries.append({
            "content": content,
            "metadata": metadata,
            "timestamp": datetime.now().isoformat(),
            "type": entry_type,
            "source": target_file.name
        })

        return True

    def get_context(self) -> str:
        """获取核心记忆上下文"""
        if not self.entries:
            return ""

        context_parts = []
        for entry in self.entries:
            source = entry.get('source', 'unknown')
            content = entry['content'][:1500]  # 限制长度
            context_parts.append(f"=== {source} ===\n{content}")

        return "\n\n".join(context_parts)


class L4_SkillMemory(MemoryLayer):
    """
    L4: 技能记忆
    - 自主沉淀的技能
    - 社区安装的技能
    - 按需加载
    """

    def __init__(self, bot_name: str):
        super().__init__("skill", 0)  # 无硬性限制
        self.bot_name = bot_name
        self.skills_dir = Path(f"workspaces/{bot_name}/DYNAMIC/skills")
        self.skills_dir.mkdir(parents=True, exist_ok=True)

        # 缓存已加载的技能
        self._loaded_skills: Dict[str, str] = {}

    def list_skills(self) -> List[Dict]:
        """列出所有可用技能"""
        skills = []
        for skill_file in self.skills_dir.glob("*.md"):
            skills.append({
                "name": skill_file.stem,
                "path": str(skill_file),
                "size": skill_file.stat().st_size
            })
        return skills

    def load_skill(self, skill_name: str) -> Optional[str]:
        """按需加载技能"""
        if skill_name in self._loaded_skills:
            return self._loaded_skills[skill_name]

        skill_file = self.skills_dir / f"{skill_name}.md"
        if not skill_file.exists():
            return None

        content = skill_file.read_text(encoding="utf-8")
        self._loaded_skills[skill_name] = content
        return content

    def add_skill(self, skill_name: str, content: str) -> bool:
        """添加新技能"""
        skill_file = self.skills_dir / f"{skill_name}.md"

        with open(skill_file, "w", encoding="utf-8") as f:
            f.write(content)

        # 清除缓存
        if skill_name in self._loaded_skills:
            del self._loaded_skills[skill_name]

        logger.info(f"Skill saved: {skill_name}")
        return True

    def get_context(self, skill_names: List[str] = None) -> str:
        """获取技能上下文"""
        if not skill_names:
            # 返回技能列表
            skills = self.list_skills()
            return f"Available skills: {[s['name'] for s in skills]}"

        # 加载指定技能
        contents = []
        for name in skill_names:
            content = self.load_skill(name)
            if content:
                contents.append(f"=== Skill: {name} ===\n{content[:1000]}")

        return "\n\n".join(contents)


class L5_ArchiveMemory:
    """
    L5: 归档记忆
    - SQLite + FTS5 全文搜索
    - 历史会话
    - 跨会话召回
    """

    def __init__(self, bot_name: str):
        self.bot_name = bot_name
        self.db_path = Path(f"workspaces/{bot_name}/memory_archive.db")
        self._init_db()

    def _init_db(self):
        """初始化 SQLite 数据库"""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

        cursor = self._conn()

        # 归档表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS archives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                source TEXT,
                category TEXT,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)

        # FTS5 虚拟表
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS archives_fts USING fts5(
                content,
                source,
                category,
                content='archives',
                content_rowid='id'
            )
        """)

        # 触发器
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS archives_ai AFTER INSERT ON archives BEGIN
                INSERT INTO archives_fts(rowid, content, source, category)
                VALUES (new.id, new.content, new.source, new.category);
            END
        """)

        self._commit()
        logger.info(f"L5 Archive initialized for {self.bot_name}")

    def _conn(self):
        return self.conn.cursor()

    def _commit(self):
        self.conn.commit()

    def archive(self, content: str, source: str = None, category: str = None) -> bool:
        """归档内容"""
        cursor = self._conn()
        cursor.execute("""
            INSERT INTO archives (content, source, category)
            VALUES (?, ?, ?)
        """, (content, source, category))
        self._commit()
        return True

    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """全文搜索归档记忆"""
        cursor = self._conn()
        cursor.execute("""
            SELECT a.*, highlight(archives_fts, 0, '<mark>', '</mark>') as highlighted
            FROM archives_fts
            JOIN archives a ON archives_fts.rowid = a.id
            WHERE archives_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (query, limit))

        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row["id"],
                "content": row["content"],
                "highlighted": row["highlighted"],
                "source": row["source"],
                "category": row["category"],
                "created_at": row["created_at"]
            })

        return results

    def get_context(self, query: str = None, limit: int = 5) -> str:
        """获取归档记忆上下文"""
        if not query:
            return ""

        results = self.search(query, limit)
        if not results:
            return f"No archived memory found for: {query}"

        context_parts = []
        for r in results:
            context_parts.append(f"[{r.get('source', 'unknown')}] {r['highlighted']}")

        return "\n---\n".join(context_parts)


class MemoryManagerV2:
    """
    分层记忆管理器 v2.0

    统一管理五层记忆，自动分类、归档、提取
    """

    def __init__(self, bot_name: str):
        self.bot_name = bot_name

        # 初始化五层记忆
        self.l1_working = L1_WorkingMemory(bot_name)
        self.l2_shortterm = L2_ShortTermMemory(bot_name)
        self.l3_core = L3_CoreMemory(bot_name)
        self.l4_skill = L4_SkillMemory(bot_name)
        self.l5_archive = L5_ArchiveMemory(bot_name)

        # 加载现有记忆
        self._load_all()

    def _load_all(self):
        """加载所有记忆层级"""
        self.l2_shortterm.load_recent_logs(days=3)
        self.l3_core.load_from_disk()
        logger.info(f"[{self.bot_name}] All memory layers loaded")

    def add_memory(self, content: str, priority: str = "normal",
                   metadata: Dict = None) -> bool:
        """
        添加记忆，自动分类到合适的层级

        Args:
            content: 记忆内容
            priority: 优先级 (high/normal/low)
            metadata: 元数据
        """
        # 高优先级 → L3 核心记忆
        if priority == "high":
            return self.l3_core.add(content, metadata)

        # 任务相关 → L1 工作记忆
        if metadata and metadata.get("type") == "task":
            return self.l1_working.add(content, metadata)

        # 默认 → L2 短期记忆
        return self.l2_shortterm.add(content, metadata)

    def archive_old_logs(self, days: int = 3) -> int:
        """归档 3 天前的日志"""
        return self.l2_shortterm.archive_old_logs(days)

    def search_memory(self, query: str) -> List[Dict]:
        """
        跨层级搜索记忆

        搜索顺序: L3 核心 → L5 归档
        """
        results = []

        # 搜索 L3 核心记忆
        for entry in self.l3_core.entries:
            if query.lower() in entry.get('content', '').lower():
                results.append({
                    "layer": "L3_core",
                    "content": entry['content'][:200],
                    "source": entry.get('source', 'unknown')
                })

        # 搜索 L5 归档记忆
        archived = self.l5_archive.search(query, limit=5)
        for entry in archived:
            results.append({
                "layer": "L5_archive",
                "content": entry['highlighted'][:200],
                "source": entry.get('source', 'unknown')
            })

        return results

    def build_memory_context(self, max_tokens: int = 10000) -> str:
        """
        构建记忆上下文用于系统提示

        按层级合并，控制在 token 限制内
        """
        context_parts = []

        # L1: 工作记忆 (最高优先级)
        l1_context = self.l1_working.get_context()
        if l1_context:
            context_parts.append(f"=== 工作记忆 ===\n{l1_context}")

        # L2: 短期记忆
        l2_context = self.l2_shortterm.get_context()
        if l2_context:
            context_parts.append(f"=== 短期记忆 (最近 3 天) ===\n{l2_context}")

        # L3: 核心记忆
        l3_context = self.l3_core.get_context()
        if l3_context:
            context_parts.append(f"=== 核心记忆 ===\n{l3_context}")

        # L4: 技能记忆 (仅列表)
        skill_list = self.l4_skill.list_skills()
        if skill_list:
            skills_text = ", ".join(s['name'] for s in skill_list[:10])
            context_parts.append(f"=== 可用技能 ({len(skill_list)} 个) ===\n{skills_text}")

        full_context = "\n\n".join(context_parts)

        # 检查 token 限制
        estimated_tokens = len(full_context) // 4
        if estimated_tokens > max_tokens:
            logger.warning(f"Memory context exceeds limit: {estimated_tokens} > {max_tokens}")
            # 截断
            full_context = full_context[:max_tokens * 4]

        return full_context

    def get_stats(self) -> Dict:
        """获取记忆统计"""
        return {
            "bot_name": self.bot_name,
            "l1_working": {
                "entries": len(self.l1_working.entries),
                "tokens": self.l1_working.token_count()
            },
            "l2_shortterm": {
                "entries": len(self.l2_shortterm.entries),
                "tokens": self.l2_shortterm.token_count()
            },
            "l3_core": {
                "entries": len(self.l3_core.entries),
                "tokens": self.l3_core.token_count()
            },
            "l4_skill": {
                "skills": len(self.l4_skill.list_skills())
            },
            "l5_archive": {
                "db_size": self.l5_archive.db_path.stat().st_size if self.l5_archive.db_path.exists() else 0
            }
        }


# 全局实例
_managers: Dict[str, MemoryManagerV2] = {}


def get_memory_manager_v2(bot_name: str) -> MemoryManagerV2:
    """获取 Bot 的记忆管理器实例"""
    if bot_name not in _managers:
        _managers[bot_name] = MemoryManagerV2(bot_name)
    return _managers[bot_name]


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Memory Manager v2.0 - 分层记忆系统")
        print("\nUsage:")
        print("  python3 memory_manager_v2.py <bot_name> test")
        sys.exit(1)

    bot_name = sys.argv[1]
    manager = MemoryManagerV2(bot_name)

    if len(sys.argv) > 2 and sys.argv[2] == "test":
        print(f"\nTesting Memory Manager v2.0 for {bot_name}\n")

        # 测试添加记忆
        manager.add_memory("用户偏好：回复要简洁", priority="high")
        manager.add_memory("今天完成了直播策划", metadata={"type": "task"})

        # 测试搜索
        results = manager.search_memory("用户偏好")
        print(f"Search results: {len(results)}")

        # 测试上下文
        context = manager.build_memory_context()
        print(f"\nMemory context ({len(context)} chars):")
        print(context[:500])

        # 测试统计
        stats = manager.get_stats()
        print(f"\nStats: {json.dumps(stats, indent=2, ensure_ascii=False)}")

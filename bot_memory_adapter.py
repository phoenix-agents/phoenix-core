#!/usr/bin/env python3
"""
Bot Memory Adapter - Workspace-scoped memory for each bot

Each bot gets its own MemoryStore instance, scoped to its workspace.
Enhanced to auto-load all files from memory/ subdirectories.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any
import glob

from memory_store import MemoryStore, MEMORY_CHAR_LIMIT, USER_CHAR_LIMIT
from memory_cache import get_memory_cache, cache_bot_memory

logger = logging.getLogger(__name__)


class BotMemoryStore(MemoryStore):
    """
    Workspace-scoped memory store for a specific bot.

    Each bot has its own:
    - MEMORY.md (bot's notes and observations)
    - USER.md (user preferences for this bot)
    - memory/ directory (detailed logs, knowledge, projects)
    """

    def __init__(self, bot_name: str, memory_char_limit: int = MEMORY_CHAR_LIMIT):
        self.bot_name = bot_name
        self.workspace_dir = Path(f"workspaces/{bot_name}/")
        self.memory_dir = self.workspace_dir / "memory"

        # Initialize memory cache (Phoenix v2.0)
        self._cache = get_memory_cache(bot_name, ttl_seconds=300, max_entries=100)

        super().__init__(memory_char_limit=memory_char_limit)

    def load_from_disk(self):
        """Load entries from this bot's MEMORY.md, USER.md, AND all memory/ files."""
        # Ensure workspace directory exists
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        # Load from bot's workspace (MEMORY.md and USER.md)
        memory_file = self.workspace_dir / "MEMORY.md"
        user_file = self.workspace_dir / "USER.md"

        self.memory_entries = self._read_file(memory_file)
        self.user_entries = self._read_file(user_file)

        # Initialize cache counter before loading
        cached_count = 0

        # NEW: Auto-load all files from memory/ subdirectories
        cached_count = self._load_memory_directory(cached_count)

        # Deduplicate entries
        self.memory_entries = list(dict.fromkeys(self.memory_entries))
        self.user_entries = list(dict.fromkeys(self.user_entries))

        # Capture frozen snapshot for system prompt injection
        self._system_prompt_snapshot = {
            "memory": self._render_block("memory", self.memory_entries),
            "user": self._render_block("user", self.user_entries),
        }

        logger.info(
            f"[{self.bot_name}] Memory loaded: "
            f"{len(self.memory_entries)} memory entries, "
            f"{len(self.user_entries)} user entries, "
            f"cache hits: {cached_count}"
        )

    def _load_memory_directory(self, initial_cached_count: int = 0):
        """
        Auto-load all markdown files from memory/ subdirectories.

        Priority loading:
        1. Files with "生日" in name are always loaded first
        2. Then other files from each category (limited)

        Returns the total cached_count for logging purposes.
        """
        if not self.memory_dir.exists():
            logger.debug(f"[{self.bot_name}] memory/ directory does not exist")
            return initial_cached_count

        loaded_count = 0
        cached_count = initial_cached_count

        # Helper to load file with truncation (using cache)
        def load_file(md_file, category, truncate_chars):
            nonlocal loaded_count, cached_count

            # Try cache first
            cache_key = f"memory:{self.bot_name}:{md_file}"
            content = self._cache.get(cache_key)

            if content is None:
                # Cache miss, load from disk
                content = self._read_markdown_file(md_file)
                if content:
                    self._cache.set(cache_key, content)
                    loaded_count += 1
            else:
                cached_count += 1

            if content:
                truncated = self._truncate_content(content, truncate_chars)
                self.memory_entries.append(f"【{category}】{md_file.stem}:\n{truncated}")

        # Load from 知识库 (knowledge base)
        knowledge_dir = self.memory_dir / "知识库"
        if knowledge_dir.exists():
            all_files = list(knowledge_dir.glob("*.md"))
            # Priority: birthday files first
            birthday_files = [f for f in all_files if '生日' in f.name]
            other_files = [f for f in all_files if '生日' not in f.name][:8]  # Limit others
            for f in birthday_files + other_files:
                load_file(f, '知识库', 800)

        # Load from 项目 (project files)
        project_dir = self.memory_dir / "项目"
        if project_dir.exists():
            all_files = list(project_dir.glob("*.md"))
            # Priority: birthday files first
            birthday_files = [f for f in all_files if '生日' in f.name]
            other_files = [f for f in all_files if '生日' not in f.name][:8]  # Limit others
            for f in birthday_files + other_files:
                load_file(f, '项目', 600)

        # Load from 学习笔记 (learning notes)
        notes_dir = self.memory_dir / "学习笔记"
        if notes_dir.exists():
            main_notes = notes_dir / "学习笔记.md"
            if main_notes.exists():
                content = self._read_file(main_notes)
                if content:
                    truncated = self._truncate_content('\n'.join(content), 800)
                    self.memory_entries.append(f"【学习笔记】:\n{truncated}")
                    loaded_count += 1

        # Load from 日志 (last 3 days only)
        from datetime import datetime, timedelta
        log_dir = self.memory_dir / "日志"
        if log_dir.exists():
            three_days_ago = datetime.now() - timedelta(days=3)
            recent_files = []
            for md_file in log_dir.glob("*.md"):
                file_date = self._extract_date_from_filename(md_file.name)
                if file_date and file_date >= three_days_ago:
                    recent_files.append((md_file, file_date))
            # Sort by date descending and take most recent 5
            recent_files.sort(key=lambda x: x[1], reverse=True)
            for md_file, _ in recent_files[:5]:
                content = self._read_markdown_file(md_file)
                if content:
                    truncated = self._truncate_content(content, 400)
                    self.memory_entries.append(f"【日志】{md_file.stem}:\n{truncated}")
                    loaded_count += 1

        logger.info(f"[{self.bot_name}] Loaded {loaded_count} files from memory/ directory")

        return cached_count

    def _read_markdown_file(self, file_path: Path) -> str:
        """Read a markdown file and return its content."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            # Remove frontmatter if present
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    content = parts[2]
            return content.strip()
        except Exception as e:
            logger.warning(f"[{self.bot_name}] Could not read {file_path}: {e}")
            return ""

    def _extract_date_from_filename(self, filename: str) -> Any:
        """Extract date from filename like YYYY-MM-DD.md or 20260410.md."""
        from datetime import datetime
        import re

        # Try YYYY-MM-DD format
        match = re.match(r'(\d{4}-\d{2}-\d{2})', filename)
        if match:
            try:
                return datetime.strptime(match.group(1), '%Y-%m-%d')
            except:
                pass

        # Try YYYYMMDD format
        match = re.match(r'(\d{8})', filename)
        if match:
            try:
                return datetime.strptime(match.group(1), '%Y%m%d')
            except:
                pass

        return None

    def _truncate_content(self, content: str, max_chars: int = 1000) -> str:
        """Truncate content to max characters, preserving beginning and end."""
        if len(content) <= max_chars:
            return content

        # Show beginning and end with truncation marker
        chunk_size = max_chars // 2 - 50
        return content[:chunk_size] + "\n\n[...内容已截断...]\n\n" + content[-chunk_size:]

    def add_memory(self, content: str) -> bool:
        """Add a memory entry to this bot's MEMORY.md."""
        return self._add_entry("memory", content)

    def add_user_preference(self, content: str) -> bool:
        """Add a user preference to this bot's USER.md."""
        return self._add_entry("user", content)

    def get_memory_context(self) -> str:
        """Get formatted memory context for system prompt."""
        return self._system_prompt_snapshot.get("memory", "")

    def search_memory(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search all memory files for content matching the query.

        Args:
            query: Search term (supports substring matching)
            limit: Maximum number of results to return

        Returns:
            List of matching entries with file info and content preview
        """
        results = []

        # Search in loaded memory entries
        for entry in self.memory_entries:
            if query in entry:
                results.append({
                    'source': 'MEMORY.md',
                    'content': entry[:500] + '...' if len(entry) > 500 else entry
                })
                if len(results) >= limit:
                    break

        # Search in memory/ directory files
        if self.memory_dir.exists():
            for subdir in ['知识库', '项目', '学习笔记', '日志']:
                dir_path = self.memory_dir / subdir
                if not dir_path.exists():
                    continue

                for md_file in dir_path.glob('*.md'):
                    content = self._read_markdown_file(md_file)
                    if query in content:
                        # Find the matching context (line containing query)
                        lines = content.split('\n')
                        matching_lines = [line for line in lines if query in line]
                        context = matching_lines[0][:200] if matching_lines else content[:200]

                        results.append({
                            'source': f'{subdir}/{md_file.name}',
                            'context': context,
                            'full_match': True
                        })

                        if len(results) >= limit:
                            break

                if len(results) >= limit:
                    break

        return results[:limit]

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get statistics about loaded memory."""
        stats = {
            'memory_entries': len(self.memory_entries),
            'user_entries': len(self.user_entries),
            'files_loaded': 0,
            'birthday_entries': 0,
        }

        # Count birthday-related entries
        for entry in self.memory_entries:
            if '生日' in entry:
                stats['birthday_entries'] += 1

        # Count files in memory/ directory
        if self.memory_dir.exists():
            for subdir in ['知识库', '项目', '学习笔记', '日志']:
                dir_path = self.memory_dir / subdir
                if dir_path.exists():
                    stats['files_loaded'] += len(list(dir_path.glob('*.md')))

        return stats

    def get_user_context(self) -> str:
        """Get formatted user context for system prompt."""
        return self._system_prompt_snapshot.get("user", "")


class BotMemoryManager:
    """
    Manages memory stores for all bots.

    Provides centralized access to each bot's memory store.
    """

    def __init__(self):
        self._stores: Dict[str, BotMemoryStore] = {}

    def get_store(self, bot_name: str) -> BotMemoryStore:
        """Get or create memory store for a bot."""
        if bot_name not in self._stores:
            self._stores[bot_name] = BotMemoryStore(bot_name)
            self._stores[bot_name].load_from_disk()
        return self._stores[bot_name]

    def add_memory(self, bot_name: str, content: str) -> bool:
        """Add memory to a specific bot's store."""
        store = self.get_store(bot_name)
        return store.add_memory(content)

    def add_user_preference(self, bot_name: str, content: str) -> bool:
        """Add user preference to a specific bot's store."""
        store = self.get_store(bot_name)
        return store.add_user_preference(content)

    def get_all_stores(self) -> Dict[str, BotMemoryStore]:
        """Get all memory stores."""
        return self._stores.copy()


# Global instance
_memory_manager: BotMemoryManager = None


def get_memory_manager() -> BotMemoryManager:
    """Get global memory manager instance."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = BotMemoryManager()
    return _memory_manager


def get_bot_memory(bot_name: str) -> BotMemoryStore:
    """Get memory store for a specific bot."""
    return get_memory_manager().get_store(bot_name)


def add_bot_memory(bot_name: str, content: str) -> bool:
    """Add memory to a specific bot."""
    return get_memory_manager().add_memory(bot_name, content)

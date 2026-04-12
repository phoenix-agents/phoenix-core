#!/usr/bin/env python3
"""
Memory Tool Module - Persistent Curated Memory (Enhanced with Auto-Routing)

Provides bounded, file-backed memory that persists across sessions.
Supports automatic routing to subdirectories based on content type.

Directory structure:
  - 学习笔记/学习笔记.md - Daily learning notes (auto-append)
  - 学习笔记/LEARNING-HISTORY.md - Archived learning history
  - 知识库/精华知识.md - High-value knowledge (auto-extracted)
  - 知识库/{topic}.md - Domain knowledge files
  - 日志/YYYY-MM-DD.md - Daily logs
  - 项目/{project}.md - Project-specific memory

IMPORTANT: Memory content should be written in ENGLISH for better compatibility.
Chinese characters may cause encoding issues in some scenarios.

Entry delimiter: § (section sign). Entries can be multiline.
"""

import fcntl
import json
import logging
import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Where memory files live
def get_memory_dir() -> Path:
    """Return the profile-scoped memories directory."""
    profile = os.environ.get('PHOENIX_PROFILE', 'main')
    base_dir = Path(__file__).parent / "memories"
    return base_dir

def get_bot_memory_dir(bot_name: str = None) -> Path:
    """Return bot-specific memory directory."""
    if bot_name:
        return Path(__file__).parent / "workspaces" / {bot_name} / "memory"
    return get_memory_dir()

MEMORY_DIR = get_memory_dir()

ENTRY_DELIMITER = "\n§\n"

# Character limits
MEMORY_CHAR_LIMIT = 5000  # Increased for auto-learning (more entries)
USER_CHAR_LIMIT = 2000  # Increased for user preferences
LEARNING_NOTE_CHAR_LIMIT = 10000  # Larger limit for learning notes
ARCHIVE_THRESHOLD = 8000  # Archive when exceeds this threshold

# High-value knowledge keywords (for automatic extraction)
HIGH_VALUE_KEYWORDS = [
    '方法论', '体系', '框架', '模型', '公式',
    '核心', '关键', '本质', '规律', '原则',
    '最佳实践', '标准化', '流程', '策略',
    '复用', '通用', '模板', '规范',
    '心得', '体会', '发现', '经验', '教训'
]

# Bot to category mapping (for knowledge routing)
BOT_CATEGORY_MAP = {
    '编导': '直播相关',
    '场控': '直播相关',
    '剪辑': '视频制作',
    '美工': '设计规范',
    '客服': '运营数据',
    '运营': '运营数据',
    '渠道': '运营数据'
}


class MemoryStore:
    """
    Bounded curated memory with file persistence.

    Maintains two parallel states:
      - _system_prompt_snapshot: frozen at load time, used for system prompt injection.
        Never mutated mid-session. Keeps prefix cache stable.
      - memory_entries / user_entries: live state, mutated by tool calls, persisted to disk.
        Tool responses always reflect this live state.
    """

    def __init__(self, memory_char_limit: int = MEMORY_CHAR_LIMIT, user_char_limit: int = USER_CHAR_LIMIT):
        self.memory_entries: List[str] = []
        self.user_entries: List[str] = []
        self.memory_char_limit = memory_char_limit
        self.user_char_limit = user_char_limit
        # Frozen snapshot for system prompt -- set once at load_from_disk()
        self._system_prompt_snapshot: Dict[str, str] = {"memory": "", "user": ""}

    def load_from_disk(self):
        """Load entries from MEMORY.md and USER.md, capture system prompt snapshot."""
        mem_dir = get_memory_dir()
        mem_dir.mkdir(parents=True, exist_ok=True)

        self.memory_entries = self._read_file(mem_dir / "MEMORY.md")
        self.user_entries = self._read_file(mem_dir / "USER.md")

        # Deduplicate entries (preserves order, keeps first occurrence)
        self.memory_entries = list(dict.fromkeys(self.memory_entries))
        self.user_entries = list(dict.fromkeys(self.user_entries))

        # Capture frozen snapshot for system prompt injection
        self._system_prompt_snapshot = {
            "memory": self._render_block("memory", self.memory_entries),
            "user": self._render_block("user", self.user_entries),
        }

        logger.info(f"Memory loaded: {len(self.memory_entries)} memory entries, {len(self.user_entries)} user entries")

    @staticmethod
    @contextmanager
    def _file_lock(path: Path):
        """Acquire an exclusive file lock for read-modify-write safety."""
        lock_path = path.with_suffix(path.suffix + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = open(lock_path, "w")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            fd.close()

    @staticmethod
    def _path_for(target: str) -> Path:
        if target == "user":
            return get_memory_dir() / "USER.md"
        return get_memory_dir() / "MEMORY.md"

    def _read_file(self, path: Path) -> List[str]:
        """Read entries from a memory file."""
        if not path.exists():
            path.touch()
            return []

        with open(path, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        if not content:
            return []

        # Split by delimiter and clean up
        entries = [e.strip() for e in content.split(ENTRY_DELIMITER) if e.strip()]
        return entries

    def _write_file(self, path: Path, entries: List[str]):
        """Write entries to a memory file atomically."""
        content = ENTRY_DELIMITER.join(entries) if entries else ""

        # Write to temp file first, then rename for atomicity
        temp_path = path.with_suffix(path.suffix + ".tmp")
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(content)
            if content and not content.endswith('\n'):
                f.write('\n')

        # Atomic rename
        os.replace(temp_path, path)

    def _reload_target(self, target: str):
        """Re-read entries from disk into in-memory state."""
        fresh = self._read_file(self._path_for(target))
        fresh = list(dict.fromkeys(fresh))  # deduplicate
        self._set_entries(target, fresh)

    def save_to_disk(self, target: str):
        """Persist entries to the appropriate file. Called after every mutation."""
        get_memory_dir().mkdir(parents=True, exist_ok=True)
        self._write_file(self._path_for(target), self._entries_for(target))

    def _entries_for(self, target: str) -> List[str]:
        if target == "user":
            return self.user_entries
        return self.memory_entries

    def _set_entries(self, target: str, entries: List[str]):
        if target == "user":
            self.user_entries = entries
        else:
            self.memory_entries = entries

    def _char_count(self, target: str) -> int:
        entries = self._entries_for(target)
        if not entries:
            return 0
        return len(ENTRY_DELIMITER.join(entries))

    def _char_limit(self, target: str) -> int:
        if target == "user":
            return self.user_char_limit
        return self.memory_char_limit

    def _render_block(self, target: str, entries: List[str]) -> str:
        """Render entries as a markdown block for system prompt injection."""
        if not entries:
            return ""

        label = "User Profile" if target == "user" else "Agent Memory"
        content = ENTRY_DELIMITER.join(entries)

        return f"# {label}\n\n{content}\n"

    def add(self, target: str, content: str) -> Dict[str, Any]:
        """Append a new entry. Returns error if it would exceed the char limit."""
        content = content.strip()
        if not content:
            return {"success": False, "error": "Content cannot be empty."}

        with self._file_lock(self._path_for(target)):
            # Re-read from disk under lock to pick up writes from other sessions
            self._reload_target(target)

            entries = self._entries_for(target)
            limit = self._char_limit(target)

            # Reject exact duplicates
            if content in entries:
                return self._success_response(target, "Entry already exists (no duplicate added).")

            # Calculate what the new total would be
            new_entries = entries + [content]
            new_total = len(ENTRY_DELIMITER.join(new_entries))

            if new_total > limit:
                current = self._char_count(target)
                return {
                    "success": False,
                    "error": (
                        f"Memory at {current:,}/{limit:,} chars. "
                        f"Adding this entry ({len(content)} chars) would exceed the limit. "
                        f"Replace or remove existing entries first."
                    ),
                    "current_entries": entries,
                    "usage": f"{current:,}/{limit:,}",
                }

            entries.append(content)
            self._set_entries(target, entries)
            self.save_to_disk(target)

        return self._success_response(target, "Entry added.")

    def replace(self, target: str, old_text: str, new_content: str) -> Dict[str, Any]:
        """Find entry containing old_text substring, replace it with new_content."""
        old_text = old_text.strip()
        new_content = new_content.strip()
        if not old_text:
            return {"success": False, "error": "old_text cannot be empty."}
        if not new_content:
            return {"success": False, "error": "new_content cannot be empty. Use 'remove' to delete entries."}

        with self._file_lock(self._path_for(target)):
            self._reload_target(target)

            entries = self._entries_for(target)
            matches = [(i, e) for i, e in enumerate(entries) if old_text in e]

            if not matches:
                return {"success": False, "error": f"No entry matched '{old_text}'."}

            if len(matches) > 1:
                # If all matches are identical (exact duplicates), operate on the first one
                unique_texts = set(e for _, e in matches)
                if len(unique_texts) > 1:
                    previews = [e[:80] + ("..." if len(e) > 80 else "") for _, e in matches]
                    return {
                        "success": False,
                        "error": f"Multiple entries matched '{old_text}'. Be more specific.",
                        "matches": previews,
                    }

            idx = matches[0][0]
            limit = self._char_limit(target)

            # Check that replacement doesn't blow the budget
            test_entries = entries.copy()
            test_entries[idx] = new_content
            new_total = len(ENTRY_DELIMITER.join(test_entries))

            if new_total > limit:
                return {
                    "success": False,
                    "error": (
                        f"Replacement would put memory at {new_total:,}/{limit:,} chars. "
                        f"Shorten the new content or remove other entries first."
                    ),
                }

            entries[idx] = new_content
            self._set_entries(target, entries)
            self.save_to_disk(target)

        return self._success_response(target, "Entry replaced.")

    def remove(self, target: str, text: str) -> Dict[str, Any]:
        """Find entry containing text substring, remove it."""
        text = text.strip()
        if not text:
            return {"success": False, "error": "Text cannot be empty."}

        with self._file_lock(self._path_for(target)):
            self._reload_target(target)

            entries = self._entries_for(target)
            matches = [(i, e) for i, e in enumerate(entries) if text in e]

            if not matches:
                return {"success": False, "error": f"No entry matched '{text}'."}

            if len(matches) > 1:
                previews = [e[:80] + ("..." if len(e) > 80 else "") for _, e in matches]
                return {
                    "success": False,
                    "error": f"Multiple entries matched '{text}'. Be more specific.",
                    "matches": previews,
                }

            idx = matches[0][0]
            entries.pop(idx)
            self._set_entries(target, entries)
            self.save_to_disk(target)

        return self._success_response(target, "Entry removed.")

    def read(self, target: str) -> Dict[str, Any]:
        """Return current entries for the target."""
        self._reload_target(target)
        entries = self._entries_for(target)

        return {
            "success": True,
            "target": target,
            "count": len(entries),
            "entries": entries,
            "usage": f"{self._char_count(target):,}/{self._char_limit(target):,}",
        }

    def _success_response(self, target: str, message: str) -> Dict[str, Any]:
        return {
            "success": True,
            "target": target,
            "message": message,
            "usage": f"{self._char_count(target):,}/{self._char_limit(target):,}",
        }

    def get_system_prompt_snapshot(self) -> Dict[str, str]:
        """Return the frozen snapshot for system prompt injection."""
        return self._system_prompt_snapshot.copy()

    def get_live_entries(self, target: str) -> List[str]:
        """Return live entries (may differ from snapshot if modified mid-session)."""
        return self._entries_for(target).copy()

    # ========== Enhanced Methods for Auto-Routing ==========

    @staticmethod
    def is_high_value(content: str) -> bool:
        """Check if content is high-value knowledge worth extracting."""
        if len(content) < 20:
            return False
        score = sum(1 for kw in HIGH_VALUE_KEYWORDS if kw in content)
        return score >= 1

    @staticmethod
    def get_bot_category(bot: str) -> str:
        """Get knowledge category for a bot."""
        return BOT_CATEGORY_MAP.get(bot, '通用')

    def route_content(self, content: str, bot: str = None, category: str = None) -> Dict[str, Any]:
        """
        Auto-route content to appropriate subdirectory.

        Routing rules:
        - High-value content → 知识库/精华知识.md
        - Learning notes → 学习笔记/学习笔记.md
        - Daily logs → 日志/YYYY-MM-DD.md
        - Project docs → 项目/{project}.md
        """
        today = datetime.now().strftime('%Y-%m-%d')
        memory_dir = get_bot_memory_dir(bot) if bot else get_memory_dir()

        # Determine target category
        if category:
            target_category = category
        elif self.is_high_value(content):
            target_category = '知识库'
        else:
            target_category = '学习笔记'

        # Build target path
        if target_category == '知识库':
            target_file = memory_dir / '知识库' / '精华知识.md'
        elif target_category == '学习笔记':
            target_file = memory_dir / '学习笔记' / '学习笔记.md'
        elif target_category == '日志':
            target_file = memory_dir / '日志' / f'{today}.md'
        else:
            target_file = memory_dir / target_category / f'{category}.md'

        # Ensure directory exists
        target_file.parent.mkdir(parents=True, exist_ok=True)

        # Append content
        entry = f"\n\n## {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n{content}\n"
        with open(target_file, 'a', encoding='utf-8') as f:
            f.write(entry)

        # Check if archive needed for learning notes
        if target_category == '学习笔记':
            self._check_and_archive(memory_dir / '学习笔记')

        return {
            'success': True,
            'target_file': str(target_file),
            'category': target_category,
            'is_high_value': self.is_high_value(content)
        }

    def _check_and_archive(self, notes_dir: Path):
        """Archive learning notes if exceeds threshold."""
        notes_file = notes_dir / '学习笔记.md'
        if not notes_file.exists():
            return

        with open(notes_file, 'r', encoding='utf-8') as f:
            content = f.read()

        if len(content) > ARCHIVE_THRESHOLD:
            history_file = notes_dir / 'LEARNING-HISTORY.md'
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Append to history
            archive_entry = f"\n\n---\n\n## 归档时间：{timestamp}\n\n{content}\n"
            with open(history_file, 'a', encoding='utf-8') as f:
                f.write(archive_entry)

            # Clear the notes file
            with open(notes_file, 'w', encoding='utf-8') as f:
                f.write('')

            logger.info(f"Archived learning notes to {history_file}")

    def save_learning_summary(self, content: str, bot: str, source_file: str = None) -> Dict[str, Any]:
        """
        Save a learning summary with automatic knowledge extraction.

        1. Saves full summary to 日志/学习总结-{date}.md
        2. Extracts high-value points to 知识库/精华知识.md
        3. Appends key points to 学习笔记/学习笔记.md
        """
        memory_dir = get_bot_memory_dir(bot)
        today = datetime.now().strftime('%Y-%m-%d')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 1. Save full summary to logs
        log_file = memory_dir / '日志' / f'学习总结-{today}.md'
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n\n## {timestamp} - 学习总结\n\n")
            if source_file:
                f.write(f"**来源文件**: {source_file}\n\n")
            f.write(content)

        # 2. Extract and save high-value knowledge
        high_value_points = self._extract_high_value(content)
        promoted_files = []
        if high_value_points:
            category = self.get_bot_category(bot)
            knowledge_file = memory_dir / '知识库' / f'{category}-精华.md'
            knowledge_file.parent.mkdir(parents=True, exist_ok=True)

            with open(knowledge_file, 'a', encoding='utf-8') as f:
                f.write(f"\n\n## {timestamp} - 来自 {bot} Bot\n\n")
                for point in high_value_points:
                    f.write(f"### {point['title']}\n\n{point['content']}\n\n")
            promoted_files.append(str(knowledge_file))

        # 3. Append summary to learning notes
        notes_file = memory_dir / '学习笔记' / '学习笔记.md'
        notes_file.parent.mkdir(parents=True, exist_ok=True)
        with open(notes_file, 'a', encoding='utf-8') as f:
            f.write(f"\n\n## {timestamp} - 学习总结\n\n")
            if source_file:
                f.write(f"**来源**: {source_file}\n\n")
            f.write(content)

        # Check if archive needed
        self._check_and_archive(memory_dir / '学习笔记')

        return {
            'success': True,
            'log_file': str(log_file),
            'notes_file': str(notes_file),
            'promoted_files': promoted_files,
            'high_value_count': len(high_value_points)
        }

    def _extract_high_value(self, content: str) -> List[Dict[str, str]]:
        """Extract high-value knowledge points from content."""
        high_value_points = []
        lines = content.split('\n')

        current_section = ''
        current_content = []

        for line in lines:
            # Detect section headers
            if line.startswith('##') or line.startswith('###'):
                if current_content:
                    full_content = '\n'.join(current_content)
                    if self.is_high_value(full_content):
                        high_value_points.append({
                            'title': current_section or '通用',
                            'content': full_content
                        })
                current_section = line.replace('#', '').strip()
                current_content = []
            else:
                # Collect content lines
                if line.strip() and len(line) > 10:
                    current_content.append(line)

        # Handle last section
        if current_content:
            full_content = '\n'.join(current_content)
            if self.is_high_value(full_content):
                high_value_points.append({
                    'title': current_section or '通用',
                    'content': full_content
                })

        return high_value_points


# Tool schema for memory management
MEMORY_TOOL_SCHEMA = {
    "name": "memory",
    "description": (
        "Persistent curated memory that survives across sessions.\n\n"
        "Two stores:\n"
        "- MEMORY.md: Agent's notes about projects, conventions, learned facts\n"
        "- USER.md: User preferences, expectations, work style\n\n"
        "IMPORTANT: Write memory content in ENGLISH for better compatibility.\n\n"
        "Actions:\n"
        "- add: Append a new entry (rejects if over limit)\n"
        "- replace: Find entry by substring and replace it\n"
        "- remove: Find entry by substring and delete it\n"
        "- read: View current entries and usage\n\n"
        "Limits: MEMORY=2200 chars, USER=1375 chars"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "replace", "remove", "read"],
                "description": "What to do with the memory"
            },
            "target": {
                "type": "string",
                "enum": ["memory", "user"],
                "description": "Which store to modify"
            },
            "content": {
                "type": "string",
                "description": "Content to add (for 'add' action)"
            },
            "old_text": {
                "type": "string",
                "description": "Text to find (for 'replace' or 'remove')"
            },
            "new_content": {
                "type": "string",
                "description": "New content (for 'replace' action)"
            },
        },
        "required": ["action", "target"],
    },
}


def memory_tool(action: str, target: str, store: MemoryStore, **kwargs) -> str:
    """Execute a memory tool action."""
    if action == "add":
        content = kwargs.get("content", "")
        if not content:
            return json.dumps({"success": False, "error": "Missing 'content' for add action"})
        result = store.add(target, content)
    elif action == "replace":
        old_text = kwargs.get("old_text", "")
        new_content = kwargs.get("new_content", "")
        if not old_text:
            return json.dumps({"success": False, "error": "Missing 'old_text' for replace action"})
        if not new_content:
            return json.dumps({"success": False, "error": "Missing 'new_content' for replace action"})
        result = store.replace(target, old_text, new_content)
    elif action == "remove":
        text = kwargs.get("old_text", "")
        if not text:
            return json.dumps({"success": False, "error": "Missing 'old_text' for remove action"})
        result = store.remove(target, text)
    elif action == "read":
        result = store.read(target)
    else:
        return json.dumps({"success": False, "error": f"Unknown action: {action}"})

    return json.dumps(result, ensure_ascii=False, indent=2)

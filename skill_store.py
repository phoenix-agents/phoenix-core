#!/usr/bin/env python3
"""
Skill Store Module - Persistent Skill/Pattern Storage

Provides file-backed storage for reusable skills and patterns learned from conversations.
Skills are more structured than memory entries - they represent actionable patterns,
workflows, or capabilities that the agent can reuse.

IMPORTANT: Skill content should be written in ENGLISH for better compatibility.

Entry delimiter: § (section sign). Entries can be multiline.
"""

import fcntl
import json
import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Where skill files live
def get_skill_dir() -> Path:
    """Return the skills directory."""
    base_dir = Path(__file__).parent / "skills"
    return base_dir

SKILL_DIR = get_skill_dir()

ENTRY_DELIMITER = "\n§\n"

# Character limits
SKILL_CHAR_LIMIT = 10000  # Skills can be longer (detailed patterns)


class SkillStore:
    """
    Bounded skill storage with file persistence.

    Skills differ from memory in that they represent:
    - Reusable interaction patterns
    - Workflows and procedures
    - Capabilities the agent has learned
    - Problem-solving strategies

    Each skill has a structured format:
    - name: Short identifier
    - description: What this skill does
    - triggers: When to apply it
    - steps: How to execute
    - examples: Sample applications
    """

    def __init__(self, skill_char_limit: int = SKILL_CHAR_LIMIT):
        self.skill_entries: List[str] = []
        self.skill_char_limit = skill_char_limit
        # Frozen snapshot for system prompt injection
        self._system_prompt_snapshot: Dict[str, str] = {"skills": ""}

    def load_from_disk(self):
        """Load entries from SKILL.md, capture system prompt snapshot."""
        skill_dir = get_skill_dir()
        skill_dir.mkdir(parents=True, exist_ok=True)

        self.skill_entries = self._read_file(skill_dir / "SKILL.md")

        # Deduplicate entries (preserves order, keeps first occurrence)
        self.skill_entries = list(dict.fromkeys(self.skill_entries))

        # Capture frozen snapshot for system prompt injection
        self._system_prompt_snapshot = {
            "skills": self._render_block("skills", self.skill_entries),
        }

        logger.info(f"Skill loaded: {len(self.skill_entries)} skill entries")

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
    def _path_for(target: str = "skills") -> Path:
        return get_skill_dir() / "SKILL.md"

    def _read_file(self, path: Path) -> List[str]:
        """Read entries from a skill file."""
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
        """Write entries to a skill file atomically."""
        content = ENTRY_DELIMITER.join(entries) if entries else ""

        # Write to temp file first, then rename for atomicity
        temp_path = path.with_suffix(path.suffix + ".tmp")
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(content)
            if content and not content.endswith('\n'):
                f.write('\n')

        # Atomic rename
        os.replace(temp_path, path)

    def _reload(self):
        """Re-read entries from disk into in-memory state."""
        fresh = self._read_file(self._path_for())
        fresh = list(dict.fromkeys(fresh))  # deduplicate
        self.skill_entries = fresh

    def save_to_disk(self):
        """Persist entries to SKILL.md. Called after every mutation."""
        get_skill_dir().mkdir(parents=True, exist_ok=True)
        self._write_file(self._path_for(), self.skill_entries)

    def _char_count(self) -> int:
        if not self.skill_entries:
            return 0
        return len(ENTRY_DELIMITER.join(self.skill_entries))

    def _render_block(self, target: str, entries: List[str]) -> str:
        """Render entries as a markdown block for system prompt injection."""
        if not entries:
            return ""

        content = ENTRY_DELIMITER.join(entries)
        return f"# Skills\n\n{content}\n"

    def add(self, content: str) -> Dict[str, Any]:
        """Append a new skill entry. Returns error if it would exceed the char limit."""
        content = content.strip()
        if not content:
            return {"success": False, "error": "Content cannot be empty."}

        with self._file_lock(self._path_for()):
            # Re-read from disk under lock
            self._reload()

            limit = self.skill_char_limit

            # Reject exact duplicates
            if content in self.skill_entries:
                return self._success_response("Entry already exists (no duplicate added).")

            # Calculate what the new total would be
            new_entries = self.skill_entries + [content]
            new_total = len(ENTRY_DELIMITER.join(new_entries))

            if new_total > limit:
                current = self._char_count()
                return {
                    "success": False,
                    "error": (
                        f"Skill storage at {current:,}/{limit:,} chars. "
                        f"Adding this entry ({len(content)} chars) would exceed the limit. "
                        f"Replace or remove existing entries first."
                    ),
                    "current_entries": self.skill_entries,
                    "usage": f"{current:,}/{limit:,}",
                }

            self.skill_entries.append(content)
            self.save_to_disk()

        return self._success_response("Skill entry added.")

    def replace(self, old_text: str, new_content: str) -> Dict[str, Any]:
        """Find entry containing old_text substring, replace it with new_content."""
        old_text = old_text.strip()
        new_content = new_content.strip()
        if not old_text:
            return {"success": False, "error": "old_text cannot be empty."}
        if not new_content:
            return {"success": False, "error": "new_content cannot be empty. Use 'remove' to delete entries."}

        with self._file_lock(self._path_for()):
            self._reload()

            matches = [(i, e) for i, e in enumerate(self.skill_entries) if old_text in e]

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

            # Check that replacement doesn't blow the budget
            test_entries = self.skill_entries.copy()
            test_entries[idx] = new_content
            new_total = len(ENTRY_DELIMITER.join(test_entries))

            if new_total > self.skill_char_limit:
                return {
                    "success": False,
                    "error": (
                        f"Replacement would put skill storage at {new_total:,}/{self.skill_char_limit:,} chars. "
                        f"Shorten the new content or remove other entries first."
                    ),
                }

            self.skill_entries[idx] = new_content
            self.save_to_disk()

        return self._success_response("Skill entry replaced.")

    def remove(self, text: str) -> Dict[str, Any]:
        """Find entry containing text substring, remove it."""
        text = text.strip()
        if not text:
            return {"success": False, "error": "Text cannot be empty."}

        with self._file_lock(self._path_for()):
            self._reload()

            matches = [(i, e) for i, e in enumerate(self.skill_entries) if text in e]

            if not matches:
                return {"success": False, "error": f"No entry matched '{text}'."}

            if len(matches) > 1:
                previews = [e[:80] + ("..." if len(e) > 80 else "") for _, e in matches]
                return {
                    "success": False,
                    "error": f"Multiple entries matched '{text}'. Be more specific.",
                    "matches": previews,
                }

            self.skill_entries.pop(matches[0][0])
            self.save_to_disk()

        return self._success_response("Skill entry removed.")

    def read(self) -> Dict[str, Any]:
        """Return current skill entries."""
        self._reload()

        return {
            "success": True,
            "count": len(self.skill_entries),
            "entries": self.skill_entries,
            "usage": f"{self._char_count():,}/{self.skill_char_limit:,}",
        }

    def search(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search skill entries by keyword."""
        self._reload()

        query_lower = query.lower()
        matches = []

        for i, entry in enumerate(self.skill_entries):
            if query_lower in entry.lower():
                matches.append(entry)
                if len(matches) >= limit:
                    break

        return {
            "success": True,
            "query": query,
            "count": len(matches),
            "total_skills": len(self.skill_entries),
            "matches": matches,
        }

    def _success_response(self, message: str) -> Dict[str, Any]:
        return {
            "success": True,
            "message": message,
            "usage": f"{self._char_count():,}/{self.skill_char_limit:,}",
        }

    def get_system_prompt_snapshot(self) -> Dict[str, str]:
        """Return the frozen snapshot for system prompt injection."""
        return self._system_prompt_snapshot.copy()

    def get_live_entries(self) -> List[str]:
        """Return live skill entries (may differ from snapshot if modified)."""
        return self.skill_entries.copy()


# Tool schema for skill management
SKILL_TOOL_SCHEMA = {
    "name": "skill_manage",
    "description": (
        "Persistent skill/pattern storage for reusable capabilities.\n\n"
        "Skills represent:\n"
        "- Reusable interaction patterns\n"
        "- Workflows and procedures\n"
        "- Problem-solving strategies\n"
        "- Learned capabilities\n\n"
        "IMPORTANT: Write skill content in ENGLISH for better compatibility.\n\n"
        "Actions:\n"
        "- add: Append a new skill entry\n"
        "- replace: Find entry by substring and replace it\n"
        "- remove: Find entry by substring and delete it\n"
        "- read: View current skills\n"
        "- search: Search skills by keyword\n\n"
        "Limit: SKILL=10000 chars"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "replace", "remove", "read", "search"],
                "description": "What to do with the skill"
            },
            "content": {
                "type": "string",
                "description": "Content to add (for 'add' action) or search query (for 'search')"
            },
            "old_text": {
                "type": "string",
                "description": "Text to find (for 'replace' or 'remove')"
            },
            "new_content": {
                "type": "string",
                "description": "New content (for 'replace' action)"
            },
            "limit": {
                "type": "integer",
                "description": "Max results (for 'search' action)"
            },
        },
        "required": ["action"],
    },
}


def skill_tool(action: str, store: SkillStore, **kwargs) -> str:
    """Execute a skill tool action."""
    if action == "add":
        content = kwargs.get("content", "")
        if not content:
            return json.dumps({"success": False, "error": "Missing 'content' for add action"})
        result = store.add(content)
    elif action == "replace":
        old_text = kwargs.get("old_text", "")
        new_content = kwargs.get("new_content", "")
        if not old_text:
            return json.dumps({"success": False, "error": "Missing 'old_text' for replace action"})
        if not new_content:
            return json.dumps({"success": False, "error": "Missing 'new_content' for replace action"})
        result = store.replace(old_text, new_content)
    elif action == "remove":
        text = kwargs.get("old_text", "")
        if not text:
            return json.dumps({"success": False, "error": "Missing 'old_text' for remove action"})
        result = store.remove(text)
    elif action == "read":
        result = store.read()
    elif action == "search":
        query = kwargs.get("content", "")
        limit = kwargs.get("limit", 10)
        if not query:
            return json.dumps({"success": False, "error": "Missing 'content' (search query)"})
        result = store.search(query, limit)
    else:
        return json.dumps({"success": False, "error": f"Unknown action: {action}"})

    return json.dumps(result, ensure_ascii=False, indent=2)

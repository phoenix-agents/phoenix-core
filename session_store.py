#!/usr/bin/env python3
"""
Session Store - SQLite storage with FTS5 full-text search

Stores conversation sessions with messages, searchable via FTS5.
Patterned after Phoenix Core Agent's phoenix_state.py
"""

import sqlite3
import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Database path
def get_db_path() -> Path:
    """Return the profile-scoped database path."""
    profile = os.environ.get('PHOENIX_PROFILE', 'main')
    db_dir = Path(__file__).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / f"{profile}.db"


class SessionStore:
    """SQLite session storage with FTS5 full-text search."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or get_db_path()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self):
        """Initialize database schema with FTS5 and performance optimizations."""
        # Enable WAL mode for better concurrent write performance
        self._conn = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,           # 30 second timeout
            check_same_thread=False # Allow multi-thread access
        )
        self._conn.row_factory = sqlite3.Row

        # Enable WAL mode for concurrent writes
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA busy_timeout=30000")
        self._conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        self._conn.execute("PRAGMA temp_store=MEMORY")

        cursor = self._conn.cursor()

        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                source TEXT DEFAULT 'cli',
                model TEXT,
                started_at REAL,
                ended_at REAL,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active'
            )
        """)

        # Messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT,
                tool_name TEXT,
                tool_calls TEXT,
                tool_call_id TEXT,
                finish_reason TEXT,
                created_at REAL DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)

        # FTS5 virtual table for full-text search
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                content,
                tool_name,
                session_id,
                content='messages',
                content_rowid='id'
            )
        """)

        # Triggers to keep FTS5 in sync
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
                INSERT INTO messages_fts(rowid, content, tool_name, session_id)
                VALUES (new.id, new.content, new.tool_name, new.session_id);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
                INSERT INTO messages_fts(messages_fts, rowid, content, tool_name, session_id)
                VALUES('delete', old.id, old.content, old.tool_name, old.session_id);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
                INSERT INTO messages_fts(messages_fts, rowid, content, tool_name, session_id)
                VALUES('delete', old.id, old.content, old.tool_name, old.session_id);
                INSERT INTO messages_fts(rowid, content, tool_name, session_id)
                VALUES (new.id, new.content, new.tool_name, new.session_id);
            END
        """)

        # Indexes for performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_source ON sessions(source)
        """)

        self._conn.commit()
        logger.info(f"Session store initialized: {self.db_path}")

    def create_session(self, session_id: str, source: str = 'cli', model: str = None) -> bool:
        """Create a new session row."""
        try:
            cursor = self._conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO sessions (session_id, source, model, started_at)
                VALUES (?, ?, ?, ?)
            """, (session_id, source, model, datetime.now().timestamp()))
            self._conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return False

    def end_session(self, session_id: str, input_tokens: int = 0, output_tokens: int = 0):
        """Mark a session as ended with token counts."""
        try:
            cursor = self._conn.cursor()
            cursor.execute("""
                UPDATE sessions
                SET ended_at = ?, input_tokens = ?, output_tokens = ?,
                    total_tokens = ?, status = 'completed'
                WHERE session_id = ?
            """, (datetime.now().timestamp(), input_tokens, output_tokens,
                  input_tokens + output_tokens, session_id))
            self._conn.commit()
        except Exception as e:
            logger.error(f"Failed to end session: {e}")

    def append_message(self, session_id: str, role: str, content: str = None,
                       tool_name: str = None, tool_calls: List[Dict] = None,
                       tool_call_id: str = None, finish_reason: str = None):
        """Append a message to the session."""
        try:
            cursor = self._conn.cursor()
            tool_calls_json = json.dumps(tool_calls) if tool_calls else None
            cursor.execute("""
                INSERT INTO messages (session_id, role, content, tool_name,
                                      tool_calls, tool_call_id, finish_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (session_id, role, content, tool_name, tool_calls_json,
                  tool_call_id, finish_reason))
            self._conn.commit()
        except Exception as e:
            logger.error(f"Failed to append message: {e}")

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session metadata."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all messages for a session."""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT * FROM messages
            WHERE session_id = ?
            ORDER BY created_at ASC
        """, (session_id,))
        rows = cursor.fetchall()
        messages = []
        for row in rows:
            msg = dict(row)
            if msg.get('tool_calls'):
                try:
                    msg['tool_calls'] = json.loads(msg['tool_calls'])
                except:
                    msg['tool_calls'] = None
            messages.append(msg)
        return messages

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search messages using FTS5."""
        cursor = self._conn.cursor()

        # FTS5 search with snippet highlighting
        cursor.execute("""
            SELECT m.session_id, m.role, m.content, m.tool_name, m.created_at,
                   s.model, s.source, s.started_at,
                   snippet(messages_fts, 0, '<<', '>>', '...', 32) as snippet
            FROM messages_fts
            JOIN messages m ON messages_fts.rowid = m.id
            JOIN sessions s ON m.session_id = s.session_id
            WHERE messages_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (query, limit))

        rows = cursor.fetchall()
        results = []
        for row in rows:
            result = dict(row)
            # Group by session for summary
            results.append(result)
        return results

    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent sessions."""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT * FROM sessions
            ORDER BY started_at DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def list_recent_sessions(self, limit: int = 10, exclude_sources: List[str] = None) -> List[Dict[str, Any]]:
        """List recent sessions, optionally excluding certain sources."""
        cursor = self._conn.cursor()

        if exclude_sources:
            placeholders = ','.join('?' * len(exclude_sources))
            query = f"""
                SELECT * FROM sessions
                WHERE source NOT IN ({placeholders})
                ORDER BY started_at DESC
                LIMIT ?
            """
            cursor.execute(query, (*exclude_sources, limit))
        else:
            cursor.execute("""
                SELECT * FROM sessions
                ORDER BY started_at DESC
                LIMIT ?
            """, (limit,))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


# Tool schema
SESSION_STORE_SCHEMA = {
    "name": "session_store",
    "description": (
        "Search and manage conversation history stored in SQLite with FTS5.\n\n"
        "Actions:\n"
        "- search: Find messages by keyword/phrase\n"
        "- list: List recent sessions\n"
        "- get: Get messages from a specific session\n"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search", "list", "get"],
            },
            "query": {"type": "string", "description": "Search query (for 'search')"},
            "session_id": {"type": "string", "description": "Session ID (for 'get')"},
            "limit": {"type": "integer", "description": "Max results (default: 10)"},
        },
        "required": ["action"],
    },
}


def session_store_tool(action: str, store: SessionStore, **kwargs) -> str:
    """Execute a session store tool action."""
    if action == "search":
        query = kwargs.get("query", "")
        limit = kwargs.get("limit", 10)
        if not query:
            return json.dumps({"success": False, "error": "Missing 'query' for search"})
        results = store.search(query, limit)
        result = {"success": True, "count": len(results), "results": results}
    elif action == "list":
        limit = kwargs.get("limit", 10)
        results = store.list_sessions(limit)
        result = {"success": True, "count": len(results), "sessions": results}
    elif action == "get":
        session_id = kwargs.get("session_id", "")
        if not session_id:
            return json.dumps({"success": False, "error": "Missing 'session_id' for get"})
        session = store.get_session(session_id)
        messages = store.get_messages(session_id) if session else []
        result = {"success": True, "session": session, "messages": messages}
    else:
        return json.dumps({"success": False, "error": f"Unknown action: {action}"})

    return json.dumps(result, ensure_ascii=False, indent=2, default=str)

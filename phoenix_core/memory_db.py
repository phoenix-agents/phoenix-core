#!/usr/bin/env python3
"""
Phoenix Core Memory DB - SQLite 记忆存储加固

提供银行级数据保护：
- WAL 模式 (崩溃自动恢复)
- FULL 同步 (数据不丢)
- 事务封装 (原子操作)
- 并发重试 (8 Bot 同时写入)

Usage:
    from phoenix_core.memory_db import MemoryDatabase, safe_memory_write

    # 获取连接 (已配置安全参数)
    db = MemoryDatabase()
    conn = db.get_connection()

    # 安全写入 (自动重试)
    safe_memory_write("客服", lambda conn: conn.execute("INSERT INTO memory ..."))
"""

import sqlite3
import time
import os
import shutil
import threading
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable, Any, List
import logging

logger = logging.getLogger(__name__)

# 数据库路径 - 使用 shared_memory/memory_share.db 与 memory_share.py 统一
DB_PATH = Path(__file__).parent.parent.parent / "shared_memory" / "memory_share.db"
BACKUP_DIR = Path(__file__).parent.parent.parent / "data" / "backups" / "memory"


class MemoryDatabase:
    """SQLite 记忆数据库 (单例模式)"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._local = threading.local()

    def _get_connection(self) -> sqlite3.Connection:
        """获取线程专属连接"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            # 确保数据库目录存在
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)

            conn = sqlite3.connect(
                str(DB_PATH),
                timeout=10.0,  # 10 秒锁等待
                check_same_thread=False  # 允许多线程
            )

            # 关键安全配置 (一次性设置)
            conn.execute("PRAGMA journal_mode=WAL;")      # 写前日志，崩溃可恢复
            conn.execute("PRAGMA synchronous=FULL;")      # 每次提交强制刷盘
            conn.execute("PRAGMA temp_store=MEMORY;")     # 临时表放内存
            conn.execute("PRAGMA busy_timeout=5000;")     # 5 秒忙等待
            conn.execute("PRAGMA cache_size=-2000;")      # 2MB 缓存
            conn.execute("PRAGMA mmap_size=268435456;")   # 256MB 内存映射

            conn.row_factory = sqlite3.Row  # 字典式行对象
            self._local.conn = conn

            # 初始化表结构
            self._init_tables(conn)

        return self._local.conn

    def _init_tables(self, conn: sqlite3.Connection):
        """初始化记忆表结构"""
        # 表 1: memory - Bot 私有对话记忆 (user/assistant 角色)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id TEXT NOT NULL,
                session_id TEXT,
                role TEXT NOT NULL,  -- 'user' or 'assistant'
                content TEXT NOT NULL,
                timestamp REAL NOT NULL,
                tokens INTEGER DEFAULT 0,
                metadata TEXT  -- JSON 字符串
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_bot_id
            ON memory(bot_id, timestamp)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_session
            ON memory(session_id)
        """)

        # 表 2: shared_memories - 跨 Bot 共享记忆 (与 memory_share.py 兼容)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS shared_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_name TEXT NOT NULL,
                content TEXT NOT NULL,
                visibility TEXT DEFAULT 'public',
                team TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                channel_id TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                word_count INTEGER DEFAULT 0,
                share_count INTEGER DEFAULT 0
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_shared_bot ON shared_memories(bot_name)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_shared_visibility ON shared_memories(visibility)
        """)

        conn.commit()

    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接 (线程安全)"""
        return self._get_connection()

    def close(self):
        """关闭当前线程的连接"""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    def check_integrity(self) -> bool:
        """检查数据库完整性"""
        try:
            conn = self.get_connection()
            result = conn.execute("PRAGMA integrity_check;").fetchone()
            return result[0] == "ok"
        except Exception as e:
            logger.error(f"[MemoryDB] 完整性检查失败：{e}")
            return False

    def get_size_mb(self) -> float:
        """获取数据库文件大小 (MB)"""
        if DB_PATH.exists():
            return DB_PATH.stat().st_size / 1024 / 1024
        return 0.0


# 全局数据库实例
_db_instance: Optional[MemoryDatabase] = None


def get_memory_db() -> MemoryDatabase:
    """获取全局数据库实例"""
    global _db_instance
    if _db_instance is None:
        _db_instance = MemoryDatabase()
    return _db_instance


def safe_memory_write(
    bot_id: str,
    write_func: Callable[[sqlite3.Connection, str], Any],
    max_retries: int = 3,
    retry_delay: float = 0.5,
) -> bool:
    """
    安全写入记忆 (带事务和重试)

    Args:
        bot_id: Bot 名称
        write_func: 写入回调，接收 (conn, bot_id) 参数
        max_retries: 最大重试次数
        retry_delay: 重试间隔 (秒)

    Returns:
        是否成功

    Usage:
        def _insert(conn, bid):
            conn.execute(
                "INSERT INTO memory (bot_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (bid, 'user', '你好', time.time())
            )
        safe_memory_write("客服", _insert)
    """
    db = get_memory_db()

    for attempt in range(max_retries):
        conn = None
        try:
            conn = db.get_connection()

            # with conn 确保原子性：要么全部提交，要么全部回滚
            with conn:
                write_func(conn, bot_id)

            return True

        except sqlite3.OperationalError as e:
            error_msg = str(e)

            # 数据库锁冲突 - 重试
            if "database is locked" in error_msg and attempt < max_retries - 1:
                delay = retry_delay * (attempt + 1)  # 指数退避
                logger.warning(f"[MemoryDB] 锁冲突，{delay}s 后重试 ({attempt + 1}/{max_retries})")
                time.sleep(delay)
                continue

            # 其他错误 - 记录并重试
            logger.error(f"[MemoryDB] 写入失败：{e} ({attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue

            # 最后一次重试失败
            logger.error(f"[MemoryDB] 写入失败，已达最大重试次数")
            return False

        except Exception as e:
            logger.error(f"[MemoryDB] 未知错误：{e}")
            if conn:
                conn.rollback()
            return False

        finally:
            if conn:
                # 不关闭连接，返回连接池复用
                pass

    return False


def save_conversation(
    bot_id: str,
    user_msg: str,
    bot_reply: str,
    session_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    channel_id: Optional[str] = None,
    username: Optional[str] = None,
) -> bool:
    """
    保存一轮对话记忆 (用户消息 + Bot 回复)
    统一保存到 shared_memories 表（与 memory_share.py 共享数据库）

    Args:
        bot_id: Bot 名称
        user_msg: 用户消息
        bot_reply: Bot 回复
        session_id: 会话 ID (可选)
        metadata: 额外元数据 (转为 JSON 存储)
        channel_id: 频道 ID (用于 shared_memories 表)
        username: 用户名 (用于元数据)

    Returns:
        是否成功
    """
    import json

    timestamp = time.time()
    json_meta = json.dumps(metadata or {})

    def _insert(conn, bid):
        # 保存到 shared_memories 表 (跨 Bot 共享记忆)
        # 用户消息
        conn.execute(
            """INSERT INTO shared_memories (bot_name, content, visibility, channel_id, tags, created_at)
               VALUES (?, ?, 'private', ?, ?, datetime('now'))""",
            (bid, f"[USER] {user_msg}", channel_id or '', f'user:{username or "unknown"}')
        )
        # Bot 回复
        conn.execute(
            """INSERT INTO shared_memories (bot_name, content, visibility, channel_id, tags, created_at)
               VALUES (?, ?, 'private', ?, ?, datetime('now'))""",
            (bid, f"[BOT] {bot_reply}", channel_id or '', f'bot:{bid}')
        )

    success = safe_memory_write(bot_id, _insert)

    # 记忆双轨制：异步导出到 Markdown
    if success:
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(_export_to_markdown(bot_id, user_msg, bot_reply, timestamp))
        except RuntimeError:
            # 没有运行的事件 loop，在新 loop 中运行
            asyncio.run(_export_to_markdown(bot_id, user_msg, bot_reply, timestamp))

    return success


async def _export_to_markdown(
    bot_id: str,
    user_msg: str,
    bot_reply: str,
    timestamp: float,
):
    """
    异步导出对话到 Markdown (记忆双轨制 - 白盒层)

    Args:
        bot_id: Bot 名称
        user_msg: 用户消息
        bot_reply: Bot 回复
        timestamp: 时间戳
    """
    try:
        # 等待一下，避免频繁 IO
        await asyncio.sleep(0.1)

        # 构建文件路径
        memory_dir = Path(__file__).parent.parent.parent / "workspaces" / bot_id / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)

        history_file = memory_dir / "history.md"

        # 格式化时间
        time_str = datetime.fromtimestamp(timestamp).isoformat()
        date_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")

        # 构建条目
        entry = f"""
---

**时间**: {time_str}
**日期**: {date_str}

### 用户

{user_msg}

### {bot_id}

{bot_reply}

---
"""
        # 追加到文件
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(entry)

        logger.debug(f"[MemoryDB] Exported to Markdown: {history_file}")

    except Exception as e:
        logger.error(f"[MemoryDB] Markdown export failed: {e}")
        # 不抛出异常，不影响主流程


def get_recent_memory(
    bot_id: str,
    limit: int = 50,
    session_id: Optional[str] = None,
) -> List[dict]:
    """
    获取最近的记忆

    Args:
        bot_id: Bot 名称
        limit: 条数限制
        session_id: 会话 ID (为 None 则获取全部)

    Returns:
        记忆列表，按时间倒序
    """
    db = get_memory_db()
    conn = db.get_connection()

    if session_id:
        rows = conn.execute(
            """SELECT * FROM memory
               WHERE bot_id = ? AND session_id = ?
               ORDER BY timestamp DESC LIMIT ?""",
            (bot_id, session_id, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM memory
               WHERE bot_id = ?
               ORDER BY timestamp DESC LIMIT ?""",
            (bot_id, limit)
        ).fetchall()

    return [dict(row) for row in rows]


# ========== 备份与恢复 ==========

def backup_memory_db() -> str:
    """
    备份记忆数据库

    Returns:
        备份文件路径
    """
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    if not DB_PATH.exists():
        logger.warning("[MemoryDB] 数据库不存在，跳过备份")
        return ""

    # 备份文件名带时间戳
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"memory_{timestamp}.db"

    try:
        # 使用 SQLite 在线备份 API (不锁库)
        src_conn = sqlite3.connect(str(DB_PATH))
        dst_conn = sqlite3.connect(str(backup_path))
        src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()

        logger.info(f"[MemoryDB] 备份完成：{backup_path}")
        return str(backup_path)

    except Exception as e:
        logger.error(f"[MemoryDB] 备份失败：{e}")
        return ""


def restore_latest_backup() -> bool:
    """
    从最新备份恢复记忆数据库

    Returns:
        是否成功
    """
    if not BACKUP_DIR.exists():
        logger.warning("[MemoryDB] 备份目录不存在")
        return False

    backups = sorted(BACKUP_DIR.glob("memory_*.db"), reverse=True)
    if not backups:
        logger.warning("[MemoryDB] 没有备份文件")
        return False

    latest = backups[0]
    target_path = DB_PATH

    try:
        # 先备份当前文件 (防止恢复失败)
        if target_path.exists():
            emergency_backup = target_path.with_suffix(".db.emergency")
            shutil.copy2(target_path, emergency_backup)

        # 恢复
        shutil.copy2(latest, target_path)

        # 验证恢复后的数据库
        db = get_memory_db()
        if db.check_integrity():
            logger.info(f"[MemoryDB] 已从 {latest} 恢复")
            # 清理紧急备份
            if emergency_backup.exists():
                emergency_backup.unlink()
            return True
        else:
            logger.error("[MemoryDB] 恢复后完整性检查失败，回滚")
            shutil.copy2(emergency_backup, target_path)
            return False

    except Exception as e:
        logger.error(f"[MemoryDB] 恢复失败：{e}")
        # 尝试回滚
        if emergency_backup.exists():
            shutil.copy2(emergency_backup, target_path)
        return False


def cleanup_old_backups(keep_days: int = 7):
    """清理旧备份，保留最近 N 天"""
    if not BACKUP_DIR.exists():
        return

    cutoff = datetime.now().timestamp() - (keep_days * 86400)

    for backup_file in BACKUP_DIR.glob("memory_*.db"):
        mtime = backup_file.stat().st_mtime
        if mtime < cutoff:
            backup_file.unlink()
            logger.info(f"[MemoryDB] 清理旧备份：{backup_file.name}")


def start_backup_scheduler(interval_hours: int = 24):
    """
    启动定时备份线程

    Args:
        interval_hours: 备份间隔 (小时)
    """
    def _run():
        while True:
            time.sleep(interval_hours * 3600)
            backup_memory_db()
            cleanup_old_backups()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    logger.info(f"[MemoryDB] 备份调度Started (间隔={interval_hours}h)")

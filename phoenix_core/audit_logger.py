#!/usr/bin/env python3
"""
Phoenix Core - 审计日志模块 (Audit Logger)

功能:
1. 记录所有协议消息
2. 记录用户操作
3. 记录 Bot 操作
4. 记录异常和错误
5. 支持查询和导出

日志格式 (JSONL):
{"timestamp": "...", "type": "...", "user_id": "...", "request_id": "...", ...}
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
import sqlite3

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """审计日志条目"""
    timestamp: str
    entry_type: str        # message, operation, error, alert
    user_id: Optional[str]
    request_id: Optional[str]
    sub_task_id: Optional[str]
    sender: Optional[str]
    target: Optional[str]
    message_type: Optional[str]
    content: str
    metadata: Dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


class AuditLogger:
    """
    审计日志记录器

    日志存储:
    - JSONL 文件 (用于实时写入)
    - SQLite 数据库 (用于查询分析)
    """

    def __init__(
        self,
        log_dir: str = "logs/audit",
        db_path: Optional[str] = None,
        retention_days: int = 30
    ):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path or str(self.log_dir / "audit.db")
        self.retention_days = retention_days

        # 当前日志文件 (按日期分片)
        self.current_log_file = None
        self.current_date = None

        # SQLite 连接缓存
        self._db_conn = None

        # 初始化
        self._init_db()
        logger.info(f"审计日志初始化完成：{self.log_dir}")

    def _get_log_file(self) -> Path:
        """获取当前日期的日志文件"""
        today = datetime.now().strftime("%Y-%m-%d")
        if self.current_date != today:
            self.current_date = today
            self.current_log_file = self.log_dir / f"audit-{today}.jsonl"
        return self.current_log_file

    def _init_db(self):
        """初始化 SQLite 数据库"""
        conn = self._get_db_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                entry_type TEXT NOT NULL,
                user_id TEXT,
                request_id TEXT,
                sub_task_id TEXT,
                sender TEXT,
                target TEXT,
                message_type TEXT,
                content TEXT,
                metadata TEXT,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)

        # 创建索引加速查询
        conn.execute("CREATE INDEX IF NOT EXISTS idx_request_id ON audit_log(request_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON audit_log(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_log(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_entry_type ON audit_log(entry_type)")

        conn.commit()
        logger.debug("审计数据库初始化完成")

    def _get_db_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._db_conn is None:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            self._db_conn = conn
        return self._db_conn

    # ============ 记录方法 ============

    def log_message(
        self,
        content: str,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        sub_task_id: Optional[str] = None,
        sender: Optional[str] = None,
        target: Optional[str] = None,
        message_type: Optional[str] = None,
        metadata: Dict = None
    ):
        """
        记录协议消息

        Args:
            content: 消息内容
            user_id: 用户 ID
            request_id: 请求 ID
            sub_task_id: 子任务 ID
            sender: 发送者
            target: 目标
            message_type: ASK, RESPONSE, etc.
            metadata: 额外元数据
        """
        entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            entry_type="message",
            user_id=user_id,
            request_id=request_id,
            sub_task_id=sub_task_id,
            sender=sender,
            target=target,
            message_type=message_type,
            content=content[:2000],  # 限制长度
            metadata=metadata or {}
        )
        self._write_entry(entry)

    def log_operation(
        self,
        operation: str,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        details: str = "",
        metadata: Dict = None
    ):
        """
        记录用户/Bot 操作

        Args:
            operation: 操作名称 (如 "create_task", "cancel_task")
            user_id: 用户 ID
            request_id: 请求 ID
            details: 操作详情
            metadata: 额外元数据
        """
        entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            entry_type="operation",
            user_id=user_id,
            request_id=request_id,
            sub_task_id=None,
            sender=None,
            target=None,
            message_type=None,
            content=f"{operation}: {details}",
            metadata=metadata or {"operation": operation}
        )
        self._write_entry(entry)

    def log_error(
        self,
        error: str,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        sub_task_id: Optional[str] = None,
        traceback: Optional[str] = None,
        metadata: Dict = None
    ):
        """
        记录错误

        Args:
            error: 错误信息
            user_id: 用户 ID
            request_id: 请求 ID
            sub_task_id: 子任务 ID
            traceback: 堆栈跟踪
            metadata: 额外元数据
        """
        entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            entry_type="error",
            user_id=user_id,
            request_id=request_id,
            sub_task_id=sub_task_id,
            sender=None,
            target=None,
            message_type=None,
            content=error[:2000],
            metadata={**(metadata or {}), "traceback": traceback} if traceback else (metadata or {})
        )
        self._write_entry(entry)

    def log_alert(
        self,
        severity: str,  # LOW, MEDIUM, HIGH, CRITICAL
        message: str,
        bot_id: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Dict = None
    ):
        """
        记录告警

        Args:
            severity: 严重级别
            message: 告警内容
            bot_id: Bot ID
            request_id: 请求 ID
            metadata: 额外元数据
        """
        entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            entry_type="alert",
            user_id=None,
            request_id=request_id,
            sub_task_id=None,
            sender=bot_id,
            target=None,
            message_type=None,
            content=f"[{severity}] {message}",
            metadata={**(metadata or {}), "severity": severity}
        )
        self._write_entry(entry)

    # ============ 内部方法 ============

    def _write_entry(self, entry: AuditEntry):
        """写入日志条目"""
        # 写入 JSONL 文件
        log_file = self._get_log_file()
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry.to_json() + "\n")

        # 写入 SQLite
        try:
            conn = self._get_db_connection()
            conn.execute(
                """INSERT INTO audit_log
                   (timestamp, entry_type, user_id, request_id, sub_task_id,
                    sender, target, message_type, content, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.timestamp,
                    entry.entry_type,
                    entry.user_id,
                    entry.request_id,
                    entry.sub_task_id,
                    entry.sender,
                    entry.target,
                    entry.message_type,
                    entry.content,
                    json.dumps(entry.metadata, ensure_ascii=False) if entry.metadata else None
                )
            )
            conn.commit()
        except Exception as e:
            logger.warning(f"写入数据库失败：{e}")

    # ============ 查询方法 ============

    def query_by_request(self, request_id: str) -> List[AuditEntry]:
        """根据请求 ID 查询日志"""
        conn = self._get_db_connection()
        cursor = conn.execute(
            "SELECT * FROM audit_log WHERE request_id = ? ORDER BY timestamp",
            (request_id,)
        )
        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def query_by_user(self, user_id: str, limit: int = 100) -> List[AuditEntry]:
        """根据用户 ID 查询日志"""
        conn = self._get_db_connection()
        cursor = conn.execute(
            "SELECT * FROM audit_log WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
            (user_id, limit)
        )
        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def query_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        entry_type: Optional[str] = None
    ) -> List[AuditEntry]:
        """根据时间范围查询日志"""
        conn = self._get_db_connection()

        query = "SELECT * FROM audit_log WHERE timestamp BETWEEN ? AND ?"
        params = [start_time.isoformat(), end_time.isoformat()]

        if entry_type:
            query += " AND entry_type = ?"
            params.append(entry_type)

        query += " ORDER BY timestamp"

        cursor = conn.execute(query, params)
        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def query_errors(self, request_id: Optional[str] = None, limit: int = 100) -> List[AuditEntry]:
        """查询错误日志"""
        conn = self._get_db_connection()

        query = "SELECT * FROM audit_log WHERE entry_type = 'error'"
        params = []

        if request_id:
            query += " AND request_id = ?"
            params.append(request_id)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor = conn.execute(query, params)
        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def _row_to_entry(self, row: sqlite3.Row) -> AuditEntry:
        """将数据库行转为 AuditEntry"""
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}
        return AuditEntry(
            timestamp=row["timestamp"],
            entry_type=row["entry_type"],
            user_id=row["user_id"],
            request_id=row["request_id"],
            sub_task_id=row["sub_task_id"],
            sender=row["sender"],
            target=row["target"],
            message_type=row["message_type"],
            content=row["content"],
            metadata=metadata
        )

    # ============ 导出和清理 ============

    def export_to_json(self, output_path: str, request_id: Optional[str] = None):
        """导出日志为 JSON"""
        if request_id:
            entries = self.query_by_request(request_id)
        else:
            entries = self.query_by_time_range(
                datetime.now().replace(hour=0, minute=0, second=0),
                datetime.now()
            )

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump([e.to_dict() for e in entries], f, indent=2, ensure_ascii=False)

        logger.info(f"导出 {len(entries)} 条日志到 {output_path}")

    def cleanup_old_logs(self):
        """清理过期日志"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=self.retention_days)

        # 清理 SQLite
        conn = self._get_db_connection()
        cursor = conn.execute(
            "DELETE FROM audit_log WHERE timestamp < ?",
            (cutoff.isoformat(),)
        )
        deleted = cursor.rowcount
        conn.commit()
        logger.info(f"清理 {deleted} 条过期数据库记录")

        # 清理 JSONL 文件
        for log_file in self.log_dir.glob("audit-*.jsonl"):
            try:
                file_date = datetime.strptime(log_file.stem, "audit-%Y-%m-%d")
                if file_date < cutoff:
                    log_file.unlink()
                    logger.info(f"删除过期日志文件：{log_file}")
            except ValueError:
                pass

    def close(self):
        """关闭日志记录器"""
        if self._db_conn:
            self._db_conn.close()
            self._db_conn = None
        logger.info("审计日志已关闭")


# ============ 便捷函数 ============

_global_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """获取全局审计日志实例"""
    global _global_audit_logger
    if _global_audit_logger is None:
        _global_audit_logger = AuditLogger()
    return _global_audit_logger


def log_message(content: str, **kwargs):
    """便捷函数：记录消息"""
    get_audit_logger().log_message(content, **kwargs)


def log_operation(operation: str, **kwargs):
    """便捷函数：记录操作"""
    get_audit_logger().log_operation(operation, **kwargs)


def log_error(error: str, **kwargs):
    """便捷函数：记录错误"""
    get_audit_logger().log_error(error, **kwargs)


def log_alert(severity: str, message: str, **kwargs):
    """便捷函数：记录告警"""
    get_audit_logger().log_alert(severity, message, **kwargs)


# ============ 命令行工具 ============

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    logger_instance = AuditLogger()

    if len(sys.argv) < 2:
        print("Phoenix Core - 审计日志工具")
        print()
        print("Usage:")
        print("  python3 audit_logger.py query <request_id>    # 查询请求日志")
        print("  python3 audit_logger.py errors [request_id]   # 查询错误日志")
        print("  python3 audit_logger.py export [output.json]  # 导出日志")
        print("  python3 audit_logger.py cleanup               # 清理过期日志")
        print()
        print("便捷函数:")
        print("  from phoenix_core import log_message, log_error, log_alert")
        sys.exit(0)

    command = sys.argv[1]

    if command == "query" and len(sys.argv) > 2:
        request_id = sys.argv[2]
        entries = logger_instance.query_by_request(request_id)
        print(f"请求 {request_id} 的日志 ({len(entries)} 条):")
        for entry in entries:
            print(f"  [{entry.timestamp}] {entry.entry_type}: {entry.content[:100]}")

    elif command == "errors":
        request_id = sys.argv[2] if len(sys.argv) > 2 else None
        entries = logger_instance.query_errors(request_id)
        print(f"错误日志 ({len(entries)} 条):")
        for entry in entries:
            print(f"  [{entry.timestamp}] {entry.content[:100]}")

    elif command == "export":
        output_path = sys.argv[2] if len(sys.argv) > 2 else "audit_export.json"
        logger_instance.export_to_json(output_path)
        print(f"日志已导出到 {output_path}")

    elif command == "cleanup":
        logger_instance.cleanup_old_logs()
        print("过期日志已清理")

    else:
        print(f"未知命令：{command}")

    logger_instance.close()

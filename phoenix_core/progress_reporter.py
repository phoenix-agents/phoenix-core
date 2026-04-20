#!/usr/bin/env python3
"""
Phoenix Core - 进度汇报模块 (Progress Reporter)

功能:
1. 任务进度跟踪 (百分比、阶段、描述)
2. 定期进度更新
3. 进度事件推送 (支持回调)
4. 与链路追踪集成 (Span 关联)
5. 与审计日志集成 (进度记录)

使用场景:
1. 多步骤任务执行时的进度汇报
2. 长时间操作的定期更新
3. 并行子任务的进度汇总
4. 用户可见的进度条显示

进度状态:
┌─────────────────────────────────────────────────────────┐
│ Task: user123-20260417-001                               │
│ Progress: 60% (3/5 子任务完成)                            │
│ ├─ ✓ 子任务 1: 订单查询完成 (20%)                         │
│ ├─ ✓ 子任务 2: 物流查询完成 (20%)                         │
│ ├─ ⟳ 子任务 3: 退款处理中 (20%)                           │
│ ├─ ⏳ 子任务 4: 等待中 (0%)                                │
│ └─ ⏳ 子任务 5: 等待中 (0%)                                │
└─────────────────────────────────────────────────────────┘
"""

import json
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
import sqlite3
import asyncio

logger = logging.getLogger(__name__)


class ProgressStatus(Enum):
    """进度状态"""
    PENDING = "pending"       # 等待中
    RUNNING = "running"       # 执行中
    COMPLETED = "completed"   # 已完成
    PAUSED = "paused"         # 已暂停
    FAILED = "failed"         # 失败
    CANCELLED = "cancelled"   # 已取消


@dataclass
class SubTaskProgress:
    """子任务进度"""
    sub_task_id: str
    status: str = "pending"
    progress_percent: float = 0.0
    description: str = ""
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class TaskProgress:
    """任务整体进度"""
    task_id: str              # 任务 ID (request_id)
    user_id: str              # 用户 ID
    total_percent: float = 0.0  # 总进度百分比 (0-100)
    status: str = "pending"   # 整体状态
    description: str = ""     # 当前描述
    total_subtasks: int = 0   # 子任务总数
    completed_subtasks: int = 0  # 已完成子任务数
    subtasks: Dict[str, SubTaskProgress] = field(default_factory=dict)
    started_at: Optional[float] = None
    updated_at: Optional[float] = None
    completed_at: Optional[float] = None
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            **asdict(self),
            "subtasks": {k: v.to_dict() if hasattr(v, 'to_dict') else v for k, v in self.subtasks.items()}
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)

    def add_subtask(self, sub_task_id: str, description: str = ""):
        """添加子任务"""
        self.subtasks[sub_task_id] = SubTaskProgress(
            sub_task_id=sub_task_id,
            status="pending",
            description=description
        )
        self.total_subtasks = len(self.subtasks)

    def update_subtask(
        self,
        sub_task_id: str,
        status: Optional[str] = None,
        progress_percent: Optional[float] = None,
        description: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        """更新子任务进度"""
        if sub_task_id not in self.subtasks:
            self.add_subtask(sub_task_id)

        subtask = self.subtasks[sub_task_id]
        if status is not None:
            subtask.status = status
        if progress_percent is not None:
            subtask.progress_percent = progress_percent
        if description is not None:
            subtask.description = description
        if error_message is not None:
            subtask.error_message = error_message
        if status == "running" and subtask.started_at is None:
            subtask.started_at = time.time()
        if status in ("completed", "failed", "cancelled"):
            subtask.completed_at = time.time()

        # 重新计算总进度
        self._recalculate_total()
        self.updated_at = time.time()

    def _recalculate_total(self):
        """重新计算总进度"""
        if not self.subtasks:
            self.total_percent = 0.0
            return

        # 简单平均 (每个子任务权重相同)
        total = sum(s.progress_percent for s in self.subtasks.values())
        self.total_percent = total / len(self.subtasks)

        # 更新完成子任务数
        self.completed_subtasks = sum(
            1 for s in self.subtasks.values()
            if s.status in ("completed",)
        )


class ProgressReporter:
    """
    进度汇报器

    职责:
    1. 创建和管理任务进度
    2. 更新子任务进度
    3. 推送进度事件给订阅者
    4. 持久化进度到 SQLite
    5. 与链路追踪、审计日志集成
    """

    def __init__(
        self,
        storage_path: str = "logs/progress",
        db_path: Optional[str] = None,
        callback: Optional[Callable] = None
    ):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path or str(self.storage_path / "progress.db")
        self._callback = callback  # 进度更新回调

        # 内存缓存 (活跃进度)
        self._active_progress: Dict[str, TaskProgress] = {}

        # 数据库连接
        self._db_conn: Optional[sqlite3.Connection] = None

        # 初始化
        self._init_db()
        logger.info(f"进度汇报初始化完成：{self.storage_path}")

    def _init_db(self):
        """初始化 SQLite 数据库"""
        conn = self._get_db_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL UNIQUE,
                user_id TEXT,
                total_percent REAL,
                status TEXT,
                description TEXT,
                total_subtasks INTEGER,
                completed_subtasks INTEGER,
                subtasks_json TEXT,
                started_at REAL,
                updated_at REAL,
                completed_at REAL,
                metadata TEXT
            )
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON task_progress(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON task_progress(status)")

        conn.commit()
        logger.debug("进度汇报数据库初始化完成")

    def _get_db_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._db_conn is None:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            self._db_conn = conn
        return self._db_conn

    # ============ 核心方法 ============

    def create_progress(
        self,
        task_id: str,
        user_id: str,
        description: str = "",
        subtasks: Optional[List[str]] = None,
        metadata: Dict = None
    ) -> TaskProgress:
        """
        创建任务进度

        Args:
            task_id: 任务 ID (通常是 request_id)
            user_id: 用户 ID
            description: 任务描述
            subtasks: 子任务 ID 列表
            metadata: 额外元数据

        Returns:
            TaskProgress: 任务进度对象
        """
        progress = TaskProgress(
            task_id=task_id,
            user_id=user_id,
            status="pending",
            description=description,
            metadata=metadata or {},
            started_at=time.time()
        )

        if subtasks:
            for sub_task_id in subtasks:
                progress.add_subtask(sub_task_id)

        # 保存到内存
        self._active_progress[task_id] = progress

        # 持久化到数据库
        self._save_progress(progress)

        # 触发回调
        self._notify_progress(progress)

        logger.info(f"创建进度追踪：task_id={task_id}, subtasks={len(subtasks or [])}")
        return progress

    def update_progress(
        self,
        task_id: str,
        sub_task_id: Optional[str] = None,
        status: Optional[str] = None,
        progress_percent: Optional[float] = None,
        description: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Optional[TaskProgress]:
        """
        更新任务进度

        Args:
            task_id: 任务 ID
            sub_task_id: 子任务 ID (不提供则更新整体进度)
            status: 状态
            progress_percent: 进度百分比
            description: 描述
            error_message: 错误信息

        Returns:
            TaskProgress: 更新后的进度对象，如果不存在则返回 None
        """
        progress = self._active_progress.get(task_id)
        if progress is None:
            # 尝试从数据库加载
            progress = self._load_progress(task_id)
            if progress:
                self._active_progress[task_id] = progress
            else:
                logger.warning(f"进度不存在：task_id={task_id}")
                return None

        if sub_task_id:
            # 更新子任务
            progress.update_subtask(
                sub_task_id=sub_task_id,
                status=status,
                progress_percent=progress_percent,
                description=description,
                error_message=error_message
            )
        else:
            # 更新整体进度
            if status is not None:
                progress.status = status
            if description is not None:
                progress.description = description
            if progress_percent is not None:
                progress.total_percent = progress_percent
            progress.updated_at = time.time()

        # 持久化
        self._save_progress(progress)

        # 触发回调
        self._notify_progress(progress)

        return progress

    def mark_subtask_done(
        self,
        task_id: str,
        sub_task_id: str,
        result: str = "",
        metadata: Dict = None
    ):
        """标记子任务完成"""
        self.update_progress(
            task_id=task_id,
            sub_task_id=sub_task_id,
            status="completed",
            progress_percent=100.0,
            description=result or "已完成"
        )

    def mark_subtask_failed(
        self,
        task_id: str,
        sub_task_id: str,
        error_message: str
    ):
        """标记子任务失败"""
        self.update_progress(
            task_id=task_id,
            sub_task_id=sub_task_id,
            status="failed",
            error_message=error_message
        )

    def get_progress(self, task_id: str) -> Optional[TaskProgress]:
        """获取任务进度"""
        if task_id in self._active_progress:
            return self._active_progress[task_id]
        return self._load_progress(task_id)

    def get_progress_summary(self, task_id: str) -> Dict:
        """
        获取进度摘要 (用户友好格式)

        Returns:
            {
                "task_id": "...",
                "progress": "60%",
                "status": "running",
                "description": "退款处理中",
                "completed": 3,
                "total": 5,
                "subtasks": [...]
            }
        """
        progress = self.get_progress(task_id)
        if not progress:
            return {}

        return {
            "task_id": progress.task_id,
            "progress": f"{progress.total_percent:.1f}%",
            "status": progress.status,
            "description": progress.description,
            "completed": progress.completed_subtasks,
            "total": progress.total_subtasks,
            "subtasks": [
                {
                    "id": s.sub_task_id,
                    "status": s.status,
                    "progress": f"{s.progress_percent:.1f}%",
                    "description": s.description
                }
                for s in progress.subtasks.values()
            ]
        }

    # ============ 异步方法 ============

    async def wait_for_completion(
        self,
        task_id: str,
        timeout_seconds: float = 300,
        poll_interval: float = 1.0
    ) -> TaskProgress:
        """
        等待任务完成

        Args:
            task_id: 任务 ID
            timeout_seconds: 超时时间
            poll_interval: 轮询间隔

        Returns:
            TaskProgress: 完成时的进度
        """
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            progress = self.get_progress(task_id)
            if progress and progress.status in ("completed", "failed", "cancelled"):
                return progress
            await asyncio.sleep(poll_interval)

        # 超时
        raise TimeoutError(f"任务 {task_id} 超时 ({timeout_seconds}s)")

    # ============ 内部方法 ============

    def _save_progress(self, progress: TaskProgress):
        """保存进度到数据库"""
        conn = self._get_db_connection()
        conn.execute(
            """INSERT OR REPLACE INTO task_progress
               (task_id, user_id, total_percent, status, description,
                total_subtasks, completed_subtasks, subtasks_json,
                started_at, updated_at, completed_at, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                progress.task_id,
                progress.user_id,
                progress.total_percent,
                progress.status,
                progress.description,
                progress.total_subtasks,
                progress.completed_subtasks,
                json.dumps({k: v.to_dict() for k, v in progress.subtasks.items()}, ensure_ascii=False),
                progress.started_at,
                progress.updated_at,
                progress.completed_at,
                json.dumps(progress.metadata, ensure_ascii=False) if progress.metadata else None
            )
        )
        conn.commit()

    def _load_progress(self, task_id: str) -> Optional[TaskProgress]:
        """从数据库加载进度"""
        conn = self._get_db_connection()
        cursor = conn.execute(
            "SELECT * FROM task_progress WHERE task_id = ?",
            (task_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        subtasks_json = json.loads(row["subtasks_json"]) if row["subtasks_json"] else {}
        subtasks = {
            k: SubTaskProgress(**v) for k, v in subtasks_json.items()
        }

        progress = TaskProgress(
            task_id=row["task_id"],
            user_id=row["user_id"],
            total_percent=row["total_percent"],
            status=row["status"],
            description=row["description"],
            total_subtasks=row["total_subtasks"],
            completed_subtasks=row["completed_subtasks"],
            subtasks=subtasks,
            started_at=row["started_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {}
        )

        return progress

    def _notify_progress(self, progress: TaskProgress):
        """触发进度回调"""
        if self._callback:
            try:
                self._callback(progress)
            except Exception as e:
                logger.warning(f"进度回调失败：{e}")

    # ============ 工具方法 ============

    def format_progress_text(self, task_id: str) -> str:
        """
        格式化进度为文本 (用于消息回复)

        Returns:
            "进度：60% (3/5)
             ✓ 子任务 1: 订单查询完成
             ✓ 子任务 2: 物流查询完成
             ⟳ 子任务 3: 退款处理中..."
        """
        summary = self.get_progress_summary(task_id)
        if not summary:
            return "未找到任务进度"

        status_symbols = {
            "completed": "✓",
            "running": "⟳",
            "pending": "⏳",
            "failed": "✗",
            "cancelled": "⊘"
        }

        lines = [
            f"进度：{summary['progress']} ({summary['completed']}/{summary['total']})",
            f"状态：{summary['status']}",
            f"描述：{summary['description']}",
            ""
        ]

        for sub in summary.get("subtasks", []):
            symbol = status_symbols.get(sub["status"], "?")
            lines.append(f"  {symbol} {sub['description']} ({sub['progress']})")

        return "\n".join(lines)

    # ============ 清理 ============

    def cleanup_completed(self, retention_hours: int = 24):
        """清理已完成的进度"""
        cutoff = time.time() - (retention_hours * 60 * 60)

        conn = self._get_db_connection()
        cursor = conn.execute(
            "DELETE FROM task_progress WHERE completed_at < ? AND status IN ('completed', 'failed', 'cancelled')",
            (cutoff,)
        )
        deleted = cursor.rowcount
        conn.commit()

        # 清理内存
        to_remove = [
            task_id for task_id, p in self._active_progress.items()
            if p.completed_at and p.completed_at < cutoff
        ]
        for task_id in to_remove:
            del self._active_progress[task_id]

        logger.info(f"清理 {deleted} 条已完成进度")

    def close(self):
        """关闭进度汇报器"""
        if self._db_conn:
            self._db_conn.close()
            self._db_conn = None
        logger.info("进度汇报已关闭")


# ============ 全局实例 ============

_global_reporter: Optional[ProgressReporter] = None


def get_progress_reporter() -> ProgressReporter:
    """获取全局进度汇报器实例"""
    global _global_reporter
    if _global_reporter is None:
        _global_reporter = ProgressReporter()
    return _global_reporter


def create_progress(task_id: str, user_id: str, **kwargs) -> TaskProgress:
    """便捷函数：创建进度"""
    return get_progress_reporter().create_progress(task_id, user_id, **kwargs)


def update_progress(task_id: str, **kwargs) -> Optional[TaskProgress]:
    """便捷函数：更新进度"""
    return get_progress_reporter().update_progress(task_id, **kwargs)


def get_progress_summary(task_id: str) -> Dict:
    """便捷函数：获取进度摘要"""
    return get_progress_reporter().get_progress_summary(task_id)


# ============ 命令行工具 ============

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    reporter = ProgressReporter()

    if len(sys.argv) < 2:
        print("Phoenix Core - 进度汇报工具")
        print()
        print("Usage:")
        print("  python3 progress_reporter.py summary <task_id>    # 查看进度摘要")
        print("  python3 progress_reporter.py text <task_id>       # 查看进度文本")
        print("  python3 progress_reporter.py cleanup [hours]      # 清理已完成")
        print()
        print("便捷函数:")
        print("  from phoenix_core import create_progress, update_progress")
        sys.exit(0)

    command = sys.argv[1]

    if command == "summary" and len(sys.argv) > 2:
        task_id = sys.argv[2]
        summary = reporter.get_progress_summary(task_id)
        print(json.dumps(summary, indent=2, ensure_ascii=False))

    elif command == "text" and len(sys.argv) > 2:
        task_id = sys.argv[2]
        print(reporter.format_progress_text(task_id))

    elif command == "cleanup":
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        reporter.cleanup_completed(hours)
        print(f"已清理 {hours} 小时前的已完成任务")

    else:
        print(f"未知命令：{command}")

    reporter.close()

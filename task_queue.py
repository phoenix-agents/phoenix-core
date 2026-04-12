#!/usr/bin/env python3
"""
Phoenix Core Task Queue - Bot 协作任务队列

功能:
1. 任务优先级调度
2. 跨 Bot 上下文共享
3. 任务依赖管理
4. 协作状态跟踪

Usage:
    from task_queue import TaskQueue
    queue = TaskQueue()
    queue.add_task("编导", "策划直播", priority="high")
    task = queue.get_next_task("编导")
"""

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = "critical"  # 紧急
    HIGH = "high"          # 高
    NORMAL = "normal"      # 普通
    LOW = "low"            # 低


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"       # 待处理
    IN_PROGRESS = "in_progress"  # 进行中
    BLOCKED = "blocked"       # 已阻塞
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 失败
    CANCELLED = "cancelled"   # 已取消


@dataclass
class Task:
    """任务定义"""
    id: str
    title: str
    description: str
    assigned_to: str  # 负责 Bot
    created_by: str   # 创建 Bot
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = field(default_factory=list)  # 依赖的任务 ID
    context: Dict[str, Any] = field(default_factory=dict)  # 共享上下文
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "assigned_to": self.assigned_to,
            "created_by": self.created_by,
            "priority": self.priority.value,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "context": self.context,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "retry_count": self.retry_count
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Task":
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            assigned_to=data["assigned_to"],
            created_by=data["created_by"],
            priority=TaskPriority(data.get("priority", "normal")),
            status=TaskStatus(data.get("status", "pending")),
            dependencies=data.get("dependencies", []),
            context=data.get("context", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            error_message=data.get("error_message"),
            retry_count=data.get("retry_count", 0)
        )


class SharedContext:
    """跨 Bot 共享上下文"""

    def __init__(self, persist_path: Optional[Path] = None):
        self._data: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._persist_path = persist_path
        self._subscribers: Dict[str, Set[str]] = {}  # key -> subscriber bots

        if persist_path and persist_path.exists():
            self._load()

    def set(self, key: str, value: Any, notify_bots: Optional[List[str]] = None):
        """设置共享数据"""
        with self._lock:
            self._data[key] = value

            if notify_bots:
                self._subscribers[key] = set(notify_bots)

            self._save()
            logger.debug(f"Context set: {key}")

    def get(self, key: str, default: Any = None) -> Any:
        """获取共享数据"""
        with self._lock:
            return self._data.get(key, default)

    def delete(self, key: str):
        """删除共享数据"""
        with self._lock:
            if key in self._data:
                del self._data[key]
            if key in self._subscribers:
                del self._subscribers[key]
            self._save()

    def get_subscribers(self, key: str) -> Set[str]:
        """获取订阅者"""
        with self._lock:
            return self._subscribers.get(key, set())

    def _save(self):
        """持久化"""
        if self._persist_path:
            try:
                self._persist_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self._persist_path, "w") as f:
                    json.dump({
                        "data": self._data,
                        "subscribers": {k: list(v) for k, v in self._subscribers.items()}
                    }, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to persist context: {e}")

    def _load(self):
        """加载持久化"""
        try:
            with open(self._persist_path, "r") as f:
                data = json.load(f)
                self._data = data.get("data", {})
                self._subscribers = {
                    k: set(v) for k, v in data.get("subscribers", {}).items()
                }
        except Exception as e:
            logger.error(f"Failed to load context: {e}")


class TaskQueue:
    """
    Bot 协作任务队列

    功能:
    1. 优先级调度
    2. 依赖管理
    3. 跨 Bot 上下文
    4. 自动重试
    """

    def __init__(self, persist_dir: Optional[Path] = None):
        self._tasks: Dict[str, Task] = {}
        self._bot_queues: Dict[str, List[str]] = {}  # bot_id -> [task_ids]
        self._lock = threading.RLock()

        self._persist_dir = persist_dir or Path(__file__).parent / ".task_queue"
        self._persist_dir.mkdir(parents=True, exist_ok=True)

        # 共享上下文
        self.context = SharedContext(self._persist_dir / "shared_context.json")

        # 加载持久化任务
        self._load_tasks()

        logger.info(f"TaskQueue initialized: {len(self._tasks)} tasks")

    def add_task(
        self,
        assigned_to: str,
        title: str,
        description: str = "",
        created_by: str = "system",
        priority: TaskPriority = TaskPriority.NORMAL,
        dependencies: Optional[List[str]] = None,
        context: Optional[Dict] = None
    ) -> str:
        """
        添加任务

        Args:
            assigned_to: 负责 Bot
            title: 任务标题
            description: 任务描述
            created_by: 创建 Bot
            priority: 优先级
            dependencies: 依赖的任务 ID 列表
            context: 共享上下文数据

        Returns:
            str: 任务 ID
        """
        with self._lock:
            task_id = f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(self._tasks)}"

            task = Task(
                id=task_id,
                title=title,
                description=description,
                assigned_to=assigned_to,
                created_by=created_by,
                priority=priority,
                dependencies=dependencies or [],
                context=context or {}
            )

            self._tasks[task_id] = task

            # 添加到 Bot 队列
            if assigned_to not in self._bot_queues:
                self._bot_queues[assigned_to] = []
            self._bot_queues[assigned_to].append(task_id)

            self._save_tasks()
            logger.info(f"Added task {task_id} for {assigned_to}")

            return task_id

    def get_next_task(self, bot_name: str) -> Optional[Task]:
        """
        获取 Bot 的下一个任务 (按优先级)

        Args:
            bot_name: Bot 名称

        Returns:
            Task: 下一个任务，如果没有则返回 None
        """
        with self._lock:
            task_ids = self._bot_queues.get(bot_name, [])

            # 获取所有待处理任务
            pending_tasks = []
            for tid in task_ids:
                task = self._tasks.get(tid)
                if task and task.status == TaskStatus.PENDING:
                    # 检查依赖
                    if self._check_dependencies(task):
                        pending_tasks.append(task)

            if not pending_tasks:
                return None

            # 按优先级排序
            priority_order = {
                TaskPriority.CRITICAL: 0,
                TaskPriority.HIGH: 1,
                TaskPriority.NORMAL: 2,
                TaskPriority.LOW: 3
            }
            pending_tasks.sort(key=lambda t: (priority_order[t.priority], t.created_at))

            return pending_tasks[0]

    def start_task(self, task_id: str) -> bool:
        """开始任务"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task or task.status != TaskStatus.PENDING:
                return False

            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.now()
            self._save_tasks()
            logger.info(f"Started task {task_id}")
            return True

    def complete_task(self, task_id: str, result: Optional[Dict] = None) -> bool:
        """完成任务"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task or task.status != TaskStatus.IN_PROGRESS:
                return False

            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()

            # 将结果添加到共享上下文
            if result:
                context_key = f"task_result_{task_id}"
                self.context.set(context_key, result, notify_bots=[task.assigned_to])

            self._save_tasks()
            logger.info(f"Completed task {task_id}")
            return True

    def fail_task(self, task_id: str, error: str) -> bool:
        """失败任务 (支持重试)"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False

            task.retry_count += 1
            task.error_message = error

            if task.retry_count < task.max_retries:
                # 重试
                task.status = TaskStatus.PENDING
                logger.warning(f"Task {task_id} failed, will retry ({task.retry_count}/{task.max_retries})")
            else:
                task.status = TaskStatus.FAILED
                logger.error(f"Task {task_id} failed permanently: {error}")

            self._save_tasks()
            return True

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False

            task.status = TaskStatus.CANCELLED
            self._save_tasks()
            logger.info(f"Cancelled task {task_id}")
            return True

    def _check_dependencies(self, task: Task) -> bool:
        """检查任务依赖是否满足"""
        for dep_id in task.dependencies:
            dep_task = self._tasks.get(dep_id)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                return False
        return True

    def get_bot_tasks(self, bot_name: str, status: Optional[TaskStatus] = None) -> List[Task]:
        """获取 Bot 的任务列表"""
        with self._lock:
            task_ids = self._bot_queues.get(bot_name, [])
            tasks = []

            for tid in task_ids:
                task = self._tasks.get(tid)
                if task:
                    if status is None or task.status == status:
                        tasks.append(task)

            return tasks

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务详情"""
        return self._tasks.get(task_id)

    def _save_tasks(self):
        """保存任务"""
        tasks_file = self._persist_dir / "tasks.json"
        try:
            with open(tasks_file, "w") as f:
                json.dump({
                    "tasks": {tid: t.to_dict() for tid, t in self._tasks.items()},
                    "bot_queues": self._bot_queues
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save tasks: {e}")

    def _load_tasks(self):
        """加载任务"""
        tasks_file = self._persist_dir / "tasks.json"
        if not tasks_file.exists():
            return

        try:
            with open(tasks_file, "r") as f:
                data = json.load(f)

            for tid, tdata in data.get("tasks", {}).items():
                self._tasks[tid] = Task.from_dict(tdata)

            self._bot_queues = data.get("bot_queues", {})
            logger.info(f"Loaded {len(self._tasks)} tasks")
        except Exception as e:
            logger.error(f"Failed to load tasks: {e}")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self._lock:
            stats = {
                "total_tasks": len(self._tasks),
                "by_status": {},
                "by_bot": {},
                "by_priority": {}
            }

            for task in self._tasks.values():
                # 按状态
                status = task.status.value
                stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

                # 按 Bot
                bot = task.assigned_to
                stats["by_bot"][bot] = stats["by_bot"].get(bot, 0) + 1

                # 按优先级
                priority = task.priority.value
                stats["by_priority"][priority] = stats["by_priority"].get(priority, 0) + 1

            return stats


# 全局实例
_task_queue: Optional[TaskQueue] = None


def get_task_queue() -> TaskQueue:
    """获取任务队列实例"""
    global _task_queue

    if _task_queue is None:
        _task_queue = TaskQueue()

    return _task_queue


# 协作工具函数
def request_collaboration(
    from_bot: str,
    to_bot: str,
    request: str,
    priority: TaskPriority = TaskPriority.NORMAL
) -> str:
    """
    请求 Bot 协作

    Args:
        from_bot: 请求方 Bot
        to_bot: 被请求方 Bot
        request: 请求内容
        priority: 优先级

    Returns:
        str: 任务 ID
    """
    queue = get_task_queue()
    task_id = queue.add_task(
        assigned_to=to_bot,
        title=f"协作请求：{from_bot}",
        description=request,
        created_by=from_bot,
        priority=priority
    )

    # 添加到共享上下文
    queue.context.set(
        f"collab_request_{task_id}",
        {"from": from_bot, "to": to_bot, "request": request},
        notify_bots=[to_bot]
    )

    return task_id

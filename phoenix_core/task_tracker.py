"""
任务追踪模块 - Task Tracker

追踪任务状态，支持超时和重试管理。

任务状态机：
pending → sent → confirmed → done
                     ↓
                   failed
"""

import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Set, Callable
from enum import Enum


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"       # 待发送
    SENT = "sent"            # 已发送
    CONFIRMED = "confirmed"  # 已确认
    DONE = "done"            # 已完成
    FAILED = "failed"        # 已失败
    TIMEOUT = "timeout"      # 已超时


@dataclass
class Task:
    """任务对象"""

    request_id: str
    intent_type: str
    target_bot: str
    content: str
    protocol: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    sent_at: Optional[float] = None
    confirmed_at: Optional[float] = None
    completed_at: Optional[float] = None
    timeout_at: Optional[float] = None
    response: Optional[str] = None  # Bot 回复内容
    retry_count: int = 0
    max_retries: int = 2
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "request_id": self.request_id,
            "intent_type": self.intent_type,
            "target_bot": self.target_bot,
            "content": self.content,
            "protocol": self.protocol,
            "status": self.status.value,
            "created_at": self.created_at,
            "sent_at": self.sent_at,
            "confirmed_at": self.confirmed_at,
            "completed_at": self.completed_at,
            "timeout_at": self.timeout_at,
            "response": self.response,
            "retry_count": self.retry_count,
        }


class TaskTracker:
    """
    任务追踪器

    负责：
    1. 任务状态管理
    2. 超时检查
    3. 重试管理
    4. 任务清理
    """

    # 默认超时配置（秒）
    DEFAULT_TIMEOUTS = {
        "inquiry": 30,       # 简单询问 30 秒
        "task": 300,         # 执行任务 5 分钟
        "status": 30,        # 状态查询 30 秒
        "chat": 30,          # 闲聊 30 秒
        "forward": 60,       # 转发 60 秒
    }

    def __init__(self, timeout_config: Optional[Dict[str, int]] = None):
        """
        初始化任务追踪器

        Args:
            timeout_config: 超时配置（秒），不传则使用默认值
        """
        self._tasks: Dict[str, Task] = {}
        self._timeout_config = timeout_config or self.DEFAULT_TIMEOUTS
        self._on_timeout_callbacks: list = []
        self._on_complete_callbacks: list = []

    def create_task(
        self,
        request_id: str,
        intent_type: str,
        target_bot: str,
        content: str,
        protocol: str,
        timeout: Optional[int] = None
    ) -> Task:
        """
        创建新任务

        Args:
            request_id: 请求 ID
            intent_type: 意图类型
            target_bot: 目标 Bot
            content: 任务内容
            protocol: 协议消息
            timeout: 超时时间（秒），不传则根据意图类型自动设置

        Returns:
            创建的任务对象
        """
        # 确定超时时间
        if timeout is None:
            timeout = self._timeout_config.get(
                intent_type,
                self.DEFAULT_TIMEOUTS.get("inquiry", 30)
            )

        task = Task(
            request_id=request_id,
            intent_type=intent_type,
            target_bot=target_bot,
            content=content,
            protocol=protocol,
            status=TaskStatus.PENDING,
            created_at=time.time(),
            timeout_at=time.time() + timeout
        )

        self._tasks[request_id] = task
        return task

    def mark_sent(self, request_id: str):
        """标记任务已发送"""
        task = self._tasks.get(request_id)
        if task:
            task.status = TaskStatus.SENT
            task.sent_at = time.time()

    def mark_confirmed(self, request_id: str, response: Optional[str] = None):
        """标记任务已确认"""
        task = self._tasks.get(request_id)
        if task:
            task.status = TaskStatus.CONFIRMED
            task.confirmed_at = time.time()
            if response:
                task.response = response

    def mark_done(self, request_id: str, response: Optional[str] = None):
        """标记任务已完成"""
        task = self._tasks.get(request_id)
        if task:
            task.status = TaskStatus.DONE
            task.completed_at = time.time()
            if response:
                task.response = response

            # 触发完成回调
            for callback in self._on_complete_callbacks:
                try:
                    callback(task)
                except Exception:
                    pass

    def mark_failed(self, request_id: str, error_message: str):
        """标记任务失败"""
        task = self._tasks.get(request_id)
        if task:
            task.status = TaskStatus.FAILED
            task.completed_at = time.time()
            task.error_message = error_message
            if error_message:
                task.response = error_message

    def mark_timeout(self, request_id: str):
        """标记任务超时"""
        task = self._tasks.get(request_id)
        if task:
            task.status = TaskStatus.TIMEOUT
            task.completed_at = time.time()

            # 触发超时回调
            for callback in self._on_timeout_callbacks:
                try:
                    callback(task)
                except Exception:
                    pass

    def get_task(self, request_id: str) -> Optional[Task]:
        """获取任务"""
        return self._tasks.get(request_id)

    def get_status(self, request_id: str) -> Optional[TaskStatus]:
        """获取任务状态"""
        task = self._tasks.get(request_id)
        return task.status if task else None

    def is_pending(self, request_id: str) -> bool:
        """检查任务是否待处理"""
        task = self._tasks.get(request_id)
        return task and task.status == TaskStatus.PENDING

    def is_completed(self, request_id: str) -> bool:
        """检查任务是否已完成（成功或失败）"""
        task = self._tasks.get(request_id)
        return task and task.status in {
            TaskStatus.DONE,
            TaskStatus.FAILED,
            TaskStatus.TIMEOUT
        }

    def check_timeouts(self) -> list:
        """
        检查超时任务

        Returns:
            超时任务列表
        """
        current_time = time.time()
        timed_out_tasks = []

        for task in self._tasks.values():
            if task.status in {TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.TIMEOUT}:
                continue

            if task.timeout_at and current_time > task.timeout_at:
                self.mark_timeout(task.request_id)
                timed_out_tasks.append(task)

        return timed_out_tasks

    def can_retry(self, request_id: str) -> bool:
        """检查任务是否可以重试"""
        task = self._tasks.get(request_id)
        if not task:
            return False

        return (
            task.status in {TaskStatus.TIMEOUT, TaskStatus.FAILED}
            and task.retry_count < task.max_retries
        )

    def retry_task(self, request_id: str) -> bool:
        """
        重试任务

        Returns:
            是否成功重置
        """
        task = self._tasks.get(request_id)
        if not task or not self.can_retry(request_id):
            return False

        task.status = TaskStatus.PENDING
        task.retry_count += 1
        task.sent_at = None
        task.confirmed_at = None
        task.completed_at = None
        task.timeout_at = time.time() + (
            self._timeout_config.get(task.intent_type, 30)
        )
        task.error_message = None

        return True

    def cleanup_completed(self, max_age_seconds: int = 3600):
        """
        清理已完成的任务

        Args:
            max_age_seconds: 保留时间（秒），默认 1 小时
        """
        current_time = time.time()
        to_remove = []

        for request_id, task in self._tasks.items():
            if task.status in {TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.TIMEOUT}:
                if task.completed_at:
                    age = current_time - task.completed_at
                    if age > max_age_seconds:
                        to_remove.append(request_id)

        for request_id in to_remove:
            del self._tasks[request_id]

        return len(to_remove)

    def get_active_tasks(self) -> list:
        """获取所有活跃任务（未完成/失败/超时）"""
        return [
            task for task in self._tasks.values()
            if task.status not in {TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.TIMEOUT}
        ]

    def get_pending_tasks(self) -> list:
        """获取所有待处理任务"""
        return [
            task for task in self._tasks.values()
            if task.status == TaskStatus.PENDING
        ]

    def on_timeout(self, callback: Callable[[Task], None]):
        """注册超时回调"""
        self._on_timeout_callbacks.append(callback)

    def on_complete(self, callback: Callable[[Task], None]):
        """注册完成回调"""
        self._on_complete_callbacks.append(callback)

    def clear(self):
        """清空所有任务"""
        self._tasks.clear()

    def __len__(self) -> int:
        """获取任务数量"""
        return len(self._tasks)

    def __repr__(self) -> str:
        """字符串表示"""
        total = len(self._tasks)
        pending = len(self.get_pending_tasks())
        active = len(self.get_active_tasks())
        return f"<TaskTracker total={total} pending={pending} active={active}>"


# 全局单例
_global_tracker: Optional[TaskTracker] = None


def get_tracker() -> TaskTracker:
    """获取全局任务追踪器"""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = TaskTracker()
    return _global_tracker


# 命令行测试
if __name__ == "__main__":
    import json

    tracker = TaskTracker()

    print("=" * 60)
    print("任务追踪测试")
    print("=" * 60)

    # 创建任务
    print("\n1. 创建任务:")
    task1 = tracker.create_task(
        request_id="20260416-001",
        intent_type="inquiry",
        target_bot="场控",
        content="在不在？",
        protocol="<@1479053473038467212> [ASK|20260416-001|XiaoXiaoQian] 在不在？",
        timeout=30
    )
    print(f"   创建任务：{task1.request_id}")
    print(f"   状态：{task1.status.value}")
    print(f"   超时时间：{task1.timeout_at - time.time():.1f}秒")

    # 标记发送
    print("\n2. 标记发送:")
    tracker.mark_sent("20260416-001")
    task1 = tracker.get_task("20260416-001")
    print(f"   状态：{task1.status.value}")

    # 标记确认
    print("\n3. 标记确认:")
    tracker.mark_confirmed("20260416-001", "在的！")
    task1 = tracker.get_task("20260416-001")
    print(f"   状态：{task1.status.value}")
    print(f"   回复：{task1.response}")

    # 标记完成
    print("\n4. 标记完成:")
    tracker.mark_done("20260416-001")
    task1 = tracker.get_task("20260416-001")
    print(f"   状态：{task1.status.value}")

    # 创建多个任务
    print("\n5. 创建多个任务:")
    for i in range(2, 5):
        tracker.create_task(
            request_id=f"20260416-{i:03d}",
            intent_type="task",
            target_bot="运营",
            content=f"任务{i}",
            protocol=f"<@1479047738371870730> [DO|20260416-{i:03d}|XiaoXiaoQian] 任务{i}"
        )

    print(f"   总任务数：{len(tracker)}")
    print(f"   活跃任务：{len(tracker.get_active_tasks())}")
    print(f"   待处理任务：{len(tracker.get_pending_tasks())}")

    # 超时检查（模拟）
    print("\n6. 超时检查:")
    # 手动设置一个任务超时
    task2 = tracker.get_task("20260416-002")
    task2.timeout_at = time.time() - 1  # 设置为过去时间

    timed_out = tracker.check_timeouts()
    print(f"   超时任务：{len(timed_out)}")
    for t in timed_out:
        print(f"   - {t.request_id}: {t.intent_type}")

    # 任务统计
    print("\n7. 任务统计:")
    print(f"   tracker 状态：{tracker}")
    print(f"   已完成任务：{sum(1 for t in tracker._tasks.values() if t.status == TaskStatus.DONE)}")
    print(f"   已超时任务：{sum(1 for t in tracker._tasks.values() if t.status == TaskStatus.TIMEOUT)}")

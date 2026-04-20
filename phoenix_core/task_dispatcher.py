#!/usr/bin/env python3
"""
Phoenix Core - 任务分发器 (Task Dispatcher) v1.3

功能:
1. 跨 Bot 任务分发
2. 并行执行子任务
3. 任务追踪 ID 管理
4. 结果汇总
5. 支持 Handoff 上下文传递（v1.3 新增）

架构:
┌─────────────────────────────────────────┐
│         CoreBrain.process()              │
│              ↓                           │
│    TaskDispatcher.dispatch()             │
│         │    │    │                      │
│         ▼    ▼    ▼                      │
│    ┌────┐ ┌────┐ ┌────┐                 │
│    │运营 │ │编导 │ │场控 │                 │
│    └────┘ └────┘ └────┘                 │
└─────────────────────────────────────────┘

Usage:
    dispatcher = TaskDispatcher(gateway)
    results = await dispatcher.dispatch(task_id, subtasks)
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

from phoenix_core.protocol_v2 import create_handoff, parse_handoff, HandoffPayload, PROTOCOL_VERSION

logger = logging.getLogger(__name__)


@dataclass
class SubTask:
    """子任务定义（v1.3 增强版）"""
    bot_id: str           # 目标 Bot 名称 (如 "运营", "编导", "场控")
    prompt: str           # 具体任务描述
    deadline: datetime    # 期望完成时间
    priority: int = 5     # 1-10，数字越小优先级越高
    timeout_seconds: int = 300  # 超时时间 (秒)

    # Handoff 增强字段（v1.3）
    handoff_context: Optional[HandoffPayload] = None  # 交接上下文

    @classmethod
    def simple(cls, bot_id: str, prompt: str, deadline: datetime = None):
        """创建简单子任务（无 Handoff 上下文）"""
        return cls(
            bot_id=bot_id,
            prompt=prompt,
            deadline=deadline or datetime.now() + timedelta(minutes=5),
            priority=5,
            timeout_seconds=300,
            handoff_context=None
        )

    @classmethod
    def with_handoff(cls, bot_id: str, prompt: str, context: HandoffPayload,
                     deadline: datetime = None, priority: int = 5):
        """创建带 Handoff 上下文的子任务"""
        return cls(
            bot_id=bot_id,
            prompt=prompt,
            deadline=deadline or datetime.now() + timedelta(minutes=5),
            priority=priority,
            timeout_seconds=300,
            handoff_context=context
        )


@dataclass
class TaskRecord:
    """任务记录"""
    task_id: str
    user_id: str
    query: str
    created_at: datetime
    status: str  # "pending", "running", "completed", "failed"
    subtasks: List[SubTask]
    results: Dict[str, str] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)


class TaskDispatcher:
    """
    任务分发器

    负责将大脑的复杂任务分解并分发给多个 Bot 并行执行
    """

    def __init__(self, gateway=None):
        """
        Args:
            gateway: PhoenixCoreGateway 实例，用于发送消息给 Bot
        """
        self.gateway = gateway
        self.active_tasks: Dict[str, TaskRecord] = {}
        self.storage_path = Path("data/tasks")
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def generate_task_id(self, user_id: str) -> str:
        """生成任务 ID"""
        user_prefix = user_id[-4:] if len(user_id) >= 4 else "user"
        date_str = datetime.now().strftime("%Y%m%d")
        timestamp = datetime.now().strftime("%H%M%S")
        return f"TASK-{user_prefix}-{date_str}-{timestamp}"

    async def dispatch(
        self,
        task_id: str,
        user_id: str,
        query: str,
        subtasks: List[SubTask]
    ) -> Dict[str, str]:
        """
        并行分发子任务给各 Bot

        Args:
            task_id: 任务 ID
            user_id: 用户 ID
            query: 原始请求
            subtasks: 子任务列表

        Returns:
            {bot_id: response} 各 Bot 的回复
        """
        # 创建任务记录
        task = TaskRecord(
            task_id=task_id,
            user_id=user_id,
            query=query,
            created_at=datetime.now(),
            status="running",
            subtasks=subtasks
        )
        self.active_tasks[task_id] = task

        logger.info(f"创建任务 {task_id}: {len(subtasks)} 个子任务，分发给 {[st.bot_id for st in subtasks]}")

        # 保存任务到文件
        self._save_task(task)

        # 并行执行所有子任务
        results = await self._execute_parallel(task_id, subtasks)

        # 更新任务状态
        task.results = {k: v for k, v in results.items() if not k.startswith("error_")}
        task.errors = {k: v for k, v in results.items() if k.startswith("error_")}
        task.status = "completed"

        # 保存最终结果
        self._save_task(task)

        return results

    async def _execute_parallel(
        self,
        task_id: str,
        subtasks: List[SubTask]
    ) -> Dict[str, str]:
        """
        并行执行所有子任务

        Returns:
            {bot_id: response}
        """
        if not self.gateway:
            # 没有 gateway，返回模拟结果
            logger.warning("Gateway 未设置，返回模拟结果")
            return {st.bot_id: f"[模拟] {st.bot_id} 收到任务：{st.prompt[:50]}..." for st in subtasks}

        # 创建并发任务
        tasks = []
        for i, subtask in enumerate(subtasks):
            sub_task_id = f"{task_id}-sub{i}"
            task = asyncio.create_task(
                self._execute_single_subtask(sub_task_id, subtask)
            )
            tasks.append(task)

        # 等待所有任务完成
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # 汇总结果
        results = {}
        for i, result in enumerate(results_list):
            bot_id = subtasks[i].bot_id
            if isinstance(result, Exception):
                results[f"error_{bot_id}"] = str(result)
                logger.error(f"子任务 {bot_id} 执行失败：{result}")
            else:
                results[bot_id] = result
                logger.info(f"子任务 {bot_id} 完成")

        return results

    async def _execute_single_subtask(
        self,
        sub_task_id: str,
        subtask: SubTask
    ) -> str:
        """
        执行单个子任务（v1.3 增强版）

        通过 gateway 发送消息给指定 Bot 并等待回复
        如果 subtask 包含 handoff_context，使用 HANDOFF 协议发送
        """
        logger.info(f"执行子任务：{sub_task_id} -> {subtask.bot_id}")

        # 通过 gateway 发送给 Bot
        if self.gateway and hasattr(self.gateway, 'send_to_bot'):
            try:
                # 检查是否有 Handoff 上下文
                if subtask.handoff_context:
                    # 使用增强的 HANDOFF 协议
                    ctx = subtask.handoff_context
                    message = create_handoff(
                        target_bot=subtask.bot_id,
                        request_id=sub_task_id,
                        sub_task_id="main",
                        sender=ctx.from_bot,
                        from_bot=ctx.from_bot,
                        to_bot=ctx.to_bot,
                        original_request=ctx.original_request,
                        handoff_reason=ctx.handoff_reason,
                        essential_entities=ctx.essential_entities,
                        conversation_context=ctx.conversation_context,
                        constraints=ctx.constraints,
                        expectations=ctx.expectations,
                        return_channel=ctx.return_channel,
                        deadline_seconds=ctx.deadline_seconds
                    )
                    logger.info(f"发送 HANDOFF 到 {subtask.bot_id}: 原始请求={ctx.original_request[:50]}...")
                else:
                    # 使用简单消息
                    message = subtask.prompt

                response = await self.gateway.send_to_bot(
                    bot_id=subtask.bot_id,
                    message=message,
                    request_id=sub_task_id
                )
                return response
            except Exception as e:
                logger.error(f"send_to_bot 失败：{e}")
                return f"错误：{e}"

        # 如果没有 gateway，返回模拟结果
        await asyncio.sleep(0.1)  # 模拟延迟
        if subtask.handoff_context:
            return f"[模拟] {subtask.bot_id} 收到 HANDOFF: {subtask.handoff_context.original_request[:50]}..."
        return f"[模拟] {subtask.bot_id} 收到任务：{subtask.prompt[:50]}..."

    def _save_task(self, task: TaskRecord):
        """保存任务到文件"""
        file_path = self.storage_path / f"{task.task_id}.json"

        data = {
            "task_id": task.task_id,
            "user_id": task.user_id,
            "query": task.query,
            "created_at": task.created_at.isoformat(),
            "status": task.status,
            "subtasks": [
                {
                    "bot_id": st.bot_id,
                    "prompt": st.prompt,
                    "deadline": st.deadline.isoformat(),
                    "priority": st.priority
                }
                for st in task.subtasks
            ],
            "results": task.results,
            "errors": task.errors
        }

        import json
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """查询任务状态"""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            return {
                "task_id": task.task_id,
                "status": task.status,
                "created_at": task.created_at.isoformat(),
                "subtasks_count": len(task.subtasks),
                "completed_count": len(task.results),
                "error_count": len(task.errors),
                "results": task.results,
                "errors": task.errors
            }

        # 从文件加载
        file_path = self.storage_path / f"{task_id}.json"
        if file_path.exists():
            import json
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)

        return None


# 单例模式
_dispatcher: Optional[TaskDispatcher] = None


def get_dispatcher(gateway=None) -> TaskDispatcher:
    """获取任务分发器单例"""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = TaskDispatcher(gateway)
    return _dispatcher

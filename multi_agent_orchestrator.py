#!/usr/bin/env python3
"""
Phoenix Core Multi-Agent Orchestrator

多 Agent 编排系统 - 协调 7 个 Bot 协同工作：
1. 编导 - 内容策划、创意构思、IP 定位
2. 剪辑 - 视频剪辑、节奏把控、爆款制作
3. 美工 - 视觉设计、个人品牌打造
4. 场控 - 气氛控制、粉丝互动、节奏调节
5. 客服 - 粉丝运营、私域流量、用户维护
6. 运营 - 数据分析、增长策略、商业变现
7. 渠道 - 渠道拓展、商务合作

Usage:
    from multi_agent_orchestrator import AgentOrchestrator

    orchestrator = AgentOrchestrator()
    orchestrator.start()

    # 分配任务
    orchestrator.assign_task("编导", "策划本周直播内容")

    # 获取状态
    status = orchestrator.get_all_agents_status()
"""

import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from pathlib import Path
import threading
import time

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Agent 角色定义"""
    DIRECTOR = "编导"       # 内容策划
    EDITOR = "剪辑"         # 视频制作
    DESIGNER = "美工"       # 视觉设计
    CONTROLLER = "场控"     # 气氛控制
    SUPPORT = "客服"       # 粉丝运营
    OPERATOR = "运营"       # 数据分析
    CHANNEL = "渠道"       # 商务合作
    COORDINATOR = "小小谦"  # 系统协调


class AgentStatus(Enum):
    """Agent 状态"""
    IDLE = "idle"           # 空闲
    WORKING = "working"     # 工作中
    BUSY = "busy"           # 忙碌（任务队列满）
    OFFLINE = "offline"     # 离线
    ERROR = "error"         # 错误


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class Task:
    """任务定义"""

    def __init__(self, task_id: str, role: AgentRole, description: str,
                 priority: TaskPriority = TaskPriority.NORMAL,
                 context: Dict[str, Any] = None,
                 dependencies: List[str] = None):
        self.task_id = task_id
        self.role = role
        self.description = description
        self.priority = priority
        self.context = context or {}
        self.dependencies = dependencies or []

        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.status = "pending"  # pending, running, completed, failed
        self.result: Optional[str] = None
        self.error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "role": self.role.value,
            "description": self.description,
            "priority": self.priority.value,
            "context": self.context,
            "dependencies": self.dependencies,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
        }


class Agent:
    """单个 Agent 定义"""

    def __init__(self, role: AgentRole, name: str, model: str, provider: str):
        self.role = role
        self.name = name
        self.model = model
        self.provider = provider
        self.status = AgentStatus.IDLE

        self.current_task: Optional[Task] = None
        self.task_history: List[Task] = []
        self.capabilities: List[str] = []

        self.last_seen: datetime = datetime.now()
        self.created_at: datetime = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role.value,
            "name": self.name,
            "model": self.model,
            "provider": self.provider,
            "status": self.status.value,
            "current_task": self.current_task.to_dict() if self.current_task else None,
            "task_count": len(self.task_history),
            "last_seen": self.last_seen.isoformat(),
        }


class AgentOrchestrator:
    """
    多 Agent 编排器

    职责：
    1. 管理所有 Agent 的状态和任务分配
    2. 处理任务依赖和优先级
    3. 提供任务队列和调度
    4. 记录 Agent 活动和性能指标
    """

    def __init__(self, config_path: str = None):
        self.agents: Dict[AgentRole, Agent] = {}
        self.task_queue: List[Task] = []
        self.completed_tasks: List[Task] = []
        self.config_path = config_path

        self._lock = threading.Lock()
        self._running = False
        self._scheduler_thread: Optional[threading.Thread] = None

        # 回调函数
        self._on_task_assigned: Optional[Callable] = None
        self._on_task_completed: Optional[Callable] = None
        self._on_agent_status_changed: Optional[Callable] = None

        # 初始化默认 Agents
        self._init_default_agents()

    def _init_default_agents(self):
        """初始化默认 Agent 配置"""
        default_agents = [
            (AgentRole.DIRECTOR, "编导", "deepseek-ai/DeepSeek-V3.2", "compshare"),
            (AgentRole.EDITOR, "剪辑", "gpt-5.1", "compshare"),
            (AgentRole.DESIGNER, "美工", "gpt-5.1", "compshare"),
            (AgentRole.CONTROLLER, "场控", "claude-haiku-4-5-20251001", "compshare"),
            (AgentRole.SUPPORT, "客服", "qwen3.5-plus", "coding-plan"),
            (AgentRole.OPERATOR, "运营", "claude-sonnet-4-6", "compshare"),
            (AgentRole.CHANNEL, "渠道", "gpt-5.1", "compshare"),
            (AgentRole.COORDINATOR, "小小谦", "kimi-k2.5", "moonshot"),
        ]

        for role, name, model, provider in default_agents:
            agent = Agent(role, name, model, provider)
            agent.capabilities = self._get_default_capabilities(role)
            self.agents[role] = agent
            logger.info(f"Agent initialized: {name} ({role.value})")

    def _get_default_capabilities(self, role: AgentRole) -> List[str]:
        """获取角色的默认能力"""
        capabilities = {
            AgentRole.DIRECTOR: ["content_planning", "creative_ideation", "ip_positioning"],
            AgentRole.EDITOR: ["video_editing", "rhythm_control", "viral_content"],
            AgentRole.DESIGNER: ["visual_design", "brand_identity", "thumbnail_creation"],
            AgentRole.CONTROLLER: ["atmosphere_control", "fan_interaction", "rhythm_adjustment"],
            AgentRole.SUPPORT: ["fan_management", "private_traffic", "user_support"],
            AgentRole.OPERATOR: ["data_analysis", "growth_strategy", "monetization"],
            AgentRole.CHANNEL: ["partnership_development", "business_collaboration"],
            AgentRole.COORDINATOR: ["system_coordination", "technical_support", "task_routing"],
        }
        return capabilities.get(role, [])

    def assign_task(self, role: AgentRole | str, description: str,
                    priority: TaskPriority = TaskPriority.NORMAL,
                    context: Dict[str, Any] = None,
                    dependencies: List[str] = None) -> Optional[str]:
        """
        分配任务给指定角色

        Args:
            role: 角色名称或 AgentRole
            description: 任务描述
            priority: 任务优先级
            context: 任务上下文
            dependencies: 依赖的任务 ID 列表

        Returns:
            任务 ID，如果失败返回 None
        """
        with self._lock:
            # 解析角色
            if isinstance(role, str):
                role_map = {r.value: r for r in AgentRole}
                role = role_map.get(role)
                if not role:
                    logger.error(f"Unknown role: {description}")
                    return None

            # 创建任务
            task_id = f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}_{id(description)}"
            task = Task(task_id, role, description, priority, context, dependencies)

            # 检查依赖
            if dependencies:
                pending_deps = [tid for tid in dependencies
                               if not any(t.task_id == tid and t.status == "completed"
                                         for t in self.completed_tasks)]
                if pending_deps:
                    task.status = "waiting"
                    logger.info(f"Task {task_id} waiting for dependencies: {pending_deps}")

            # 添加到队列
            self.task_queue.append(task)
            self.task_queue.sort(key=lambda t: (-t.priority.value, t.created_at))

            logger.info(f"Task assigned: {task_id} -> {role.value}: {description}")

            if self._on_task_assigned:
                self._on_task_assigned(task)

            return task_id

    def get_agent_status(self, role: AgentRole | str) -> Optional[Dict[str, Any]]:
        """获取指定 Agent 的状态"""
        if isinstance(role, str):
            role_map = {r.value: r for r in AgentRole}
            role = role_map.get(role)

        agent = self.agents.get(role)
        if not agent:
            return None

        return agent.to_dict()

    def get_all_agents_status(self) -> Dict[str, Any]:
        """获取所有 Agent 的状态"""
        return {
            "agents": {role.value: agent.to_dict() for role, agent in self.agents.items()},
            "queue_size": len(self.task_queue),
            "completed_count": len(self.completed_tasks),
            "timestamp": datetime.now().isoformat(),
        }

    def get_task_queue(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取任务队列"""
        with self._lock:
            return [t.to_dict() for t in self.task_queue[:limit]]

    def start(self):
        """启动编排器"""
        if self._running:
            logger.warning("Orchestrator already running")
            return

        self._running = True
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            daemon=True,
            name="AgentOrchestrator-Scheduler"
        )
        self._scheduler_thread.start()
        logger.info("Agent orchestrator started")

    def stop(self):
        """停止编排器"""
        self._running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
        logger.info("Agent orchestrator stopped")

    def _scheduler_loop(self):
        """调度器主循环"""
        while self._running:
            try:
                self._process_task_queue()
                self._check_agent_status()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")

            time.sleep(1)  # 每秒检查一次

    def _process_task_queue(self):
        """处理任务队列"""
        with self._lock:
            for task in list(self.task_queue):
                if task.status != "pending":
                    continue

                # 检查依赖是否完成
                if task.dependencies:
                    pending_deps = [tid for tid in task.dependencies
                                   if not any(t.task_id == tid and t.status == "completed"
                                             for t in self.completed_tasks)]
                    if pending_deps:
                        continue

                # 获取目标 Agent
                agent = self.agents.get(task.role)
                if not agent or agent.status not in (AgentStatus.IDLE, AgentStatus.WORKING):
                    continue

                # 分配任务
                self._assign_task_to_agent(task, agent)

    def _assign_task_to_agent(self, task: Task, agent: Agent):
        """将任务分配给 Agent"""
        task.status = "running"
        task.started_at = datetime.now()

        agent.status = AgentStatus.WORKING
        agent.current_task = task

        logger.info(f"Task {task.task_id} started by {agent.name}")

        if self._on_agent_status_changed:
            self._on_agent_status_changed(agent)

        # 异步执行任务（这里模拟，实际需要连接 LLM）
        threading.Thread(
            target=self._execute_task,
            args=(task, agent),
            daemon=True
        ).start()

    def _execute_task(self, task: Task, agent: Agent):
        """执行任务（模拟）"""
        try:
            # 这里应该调用 LLM API
            # 现在只是模拟
            time.sleep(2)  # 模拟执行时间

            task.status = "completed"
            task.completed_at = datetime.now()
            task.result = f"Task completed by {agent.name}"

        except Exception as e:
            task.status = "failed"
            task.error = str(e)

        finally:
            with self._lock:
                agent.status = AgentStatus.IDLE
                agent.current_task = None
                agent.task_history.append(task)

                if task.status == "completed":
                    self.completed_tasks.append(task)

                # 从队列移除
                if task in self.task_queue:
                    self.task_queue.remove(task)

            agent.last_seen = datetime.now()

            if self._on_task_completed:
                self._on_task_completed(task)

            logger.info(f"Task {task.task_id} {task.status} by {agent.name}")

    def _check_agent_status(self):
        """检查 Agent 状态"""
        for agent in self.agents.values():
            # 检查是否超时
            if agent.status == AgentStatus.WORKING and agent.current_task:
                elapsed = (datetime.now() - agent.current_task.started_at).total_seconds()
                if elapsed > 300:  # 5 分钟超时
                    logger.warning(f"Agent {agent.name} task timeout after {elapsed}s")
                    agent.current_task.error = "Task timeout"
                    agent.current_task.status = "failed"
                    agent.status = AgentStatus.IDLE
                    agent.current_task = None


# 单例实例
_orchestrator: Optional[AgentOrchestrator] = None


def get_orchestrator() -> AgentOrchestrator:
    """获取或创建编排器单例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator


# 便捷函数
def assign_task(role: str, description: str, priority: int = 2) -> Optional[str]:
    """分配任务的便捷函数"""
    orch = get_orchestrator()
    priority_map = {1: TaskPriority.LOW, 2: TaskPriority.NORMAL, 3: TaskPriority.HIGH, 4: TaskPriority.URGENT}
    return orch.assign_task(role, description, priority_map.get(priority, TaskPriority.NORMAL))


def get_status() -> Dict[str, Any]:
    """获取所有 Agent 状态"""
    return get_orchestrator().get_all_agents_status()

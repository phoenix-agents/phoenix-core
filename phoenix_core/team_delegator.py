#!/usr/bin/env python3
"""
Phoenix Core - 团队委托管理器 (Team Delegation Manager) v1.3

功能:
1. 将整个团队作为可调用的"技能"
2. 支持多种完成策略 (ALL/ANY/QUORUM)
3. 链式调用多个团队形成"技能流水线"
4. 与 SkillRegistry 集成

架构:
┌─────────────────────────────────────────┐
│    协调者 Bot 调用"运营团队"技能          │
│              ↓                           │
│   TeamDelegator.delegate_to_team()       │
│         │    │    │                      │
│         ▼    ▼    ▼                      │
│    ┌────┐ ┌────┐ ┌────┐                 │
│    │运营 │ │场控 │ │客服 │                 │
│    └────┘ └────┘ └────┘                 │
│         │    │    │                      │
│         ▼    ▼    ▼                      │
│      汇总结果 → 返回协调者                 │
└─────────────────────────────────────────┘

Usage:
    delegator = get_team_delegator(gateway)
    result = await delegator.delegate_to_team(
        team_name="运营",
        brief="策划直播活动",
        policy=TeamDelegationPolicy.ALL_COMPLETED
    )
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class TeamDelegationPolicy(Enum):
    """团队完成策略"""
    ALL_COMPLETED = "all"      # 所有成员都返回才算完成
    ANY_COMPLETED = "any"      # 任一成员返回即完成（竞速模式）
    QUORUM = "quorum"          # 超过半数返回即完成（投票模式）


@dataclass
class TeamConfig:
    """团队配置"""
    team_name: str
    bot_ids: List[str]           # 团队成员 Bot ID 列表
    description: str             # 团队描述
    skills: List[str]            # 团队技能标签
    policy: TeamDelegationPolicy = TeamDelegationPolicy.ALL_COMPLETED
    quorum_ratio: float = 0.5    # QUORUM 策略时的比例（默认 50%）
    timeout_seconds: int = 300   # 团队任务超时时间
    priority: int = 5            # 1-10 优先级


@dataclass
class TeamTask:
    """团队任务记录"""
    task_id: str
    team_name: str
    brief: str
    created_at: datetime
    deadline: datetime
    policy: TeamDelegationPolicy
    bot_results: Dict[str, str] = field(default_factory=dict)  # {bot_id: result}
    bot_errors: Dict[str, str] = field(default_factory=dict)   # {bot_id: error}
    status: str = "running"      # running, completed, failed, timeout
    final_result: Optional[str] = None  # 汇总结果


class TeamDelegator:
    """
    团队委托器

    负责将任务委托给整个团队，并根据策略汇总结果
    """

    def __init__(self, gateway=None, config_loader=None):
        """
        Args:
            gateway: PhoenixCoreGateway 实例
            config_loader: 配置加载器，用于获取团队配置
        """
        self.gateway = gateway
        self.config_loader = config_loader
        self.active_tasks: Dict[str, TeamTask] = {}
        self.teams: Dict[str, TeamConfig] = {}

        # 加载团队配置
        self._load_team_configs()

    def _load_team_configs(self):
        """从配置加载团队信息"""
        if not self.config_loader:
            # 使用默认团队配置
            self.teams = {
                "内容团队": TeamConfig(
                    team_name="内容团队",
                    bot_ids=["运营", "场控", "编导"],
                    description="负责内容策划、直播运营和弹幕管理",
                    skills=["活动策划", "内容创作", "直播间管理"],
                    policy=TeamDelegationPolicy.ALL_COMPLETED
                ),
                "制作团队": TeamConfig(
                    team_name="制作团队",
                    bot_ids=["剪辑", "美工"],
                    description="负责视频剪辑和美术设计",
                    skills=["视频剪辑", "美术设计"],
                    policy=TeamDelegationPolicy.ALL_COMPLETED
                ),
                "商务团队": TeamConfig(
                    team_name="商务团队",
                    bot_ids=["客服", "渠道"],
                    description="负责客户支持和商务合作",
                    skills=["客户支持", "商务合作"],
                    policy=TeamDelegationPolicy.ANY_COMPLETED
                ),
            }
            logger.info(f"加载默认团队配置：{list(self.teams.keys())}")
            return

        # 从配置文件加载
        try:
            config = self.config_loader.get_config()
            teams_config = config.get("teams", {})

            for team_name, team_data in teams_config.items():
                self.teams[team_name] = TeamConfig(
                    team_name=team_name,
                    bot_ids=team_data.get("bots", []),
                    description=team_data.get("description", ""),
                    skills=team_data.get("skills", []),
                    policy=TeamDelegationPolicy(team_data.get("policy", "all")),
                    timeout_seconds=team_data.get("timeout", 300)
                )

            logger.info(f"从配置加载团队：{list(self.teams.keys())}")
        except Exception as e:
            logger.error(f"加载团队配置失败：{e}")
            # 使用默认配置
            self._load_team_configs()

    def get_team_bots(self, team_name: str) -> List[str]:
        """获取团队成员列表"""
        if team_name in self.teams:
            return self.teams[team_name].bot_ids
        return []

    def get_all_teams(self) -> List[Dict]:
        """获取所有团队信息"""
        return [
            {
                "name": team.team_name,
                "bots": team.bot_ids,
                "description": team.description,
                "skills": team.skills,
                "policy": team.policy.value
            }
            for team in self.teams.values()
        ]

    async def delegate_to_team(
        self,
        team_name: str,
        brief: str,
        policy: TeamDelegationPolicy = None,
        timeout_seconds: int = None,
        context: Dict[str, Any] = None,
        on_result: Callable[[str, str], None] = None  # 回调：(bot_id, result)
    ) -> Dict[str, Any]:
        """
        将任务委托给指定团队

        Args:
            team_name: 团队名称
            brief: 任务简述
            policy: 完成策略（默认使用团队配置）
            timeout_seconds: 超时时间（秒）
            context: 上下文信息（传递给各 Bot）
            on_result: 结果回调函数

        Returns:
            {
                "success": bool,
                "team_name": str,
                "results": {bot_id: result},
                "errors": {bot_id: error},
                "summary": str,  # 汇总结果
                "policy_used": str
            }
        """
        if team_name not in self.teams:
            logger.error(f"团队不存在：{team_name}")
            return {
                "success": False,
                "error": f"团队不存在：{team_name}",
                "available_teams": list(self.teams.keys())
            }

        team = self.teams[team_name]
        policy = policy or team.policy
        timeout = timeout_seconds or team.timeout_seconds

        # 创建团队任务
        task_id = f"TEAM-{team_name}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        task = TeamTask(
            task_id=task_id,
            team_name=team_name,
            brief=brief,
            created_at=datetime.now(),
            deadline=datetime.now() + timedelta(seconds=timeout),
            policy=policy
        )
        self.active_tasks[task_id] = task

        logger.info(f"创建团队任务 {task_id}: 团队={team_name}, 策略={policy.value}, 成员={team.bot_ids}")

        # 并行执行各 Bot 任务
        results = await self._execute_team_tasks(task, team, brief, context, on_result)

        # 根据策略判断完成状态
        task.status = "completed"
        task.final_result = self._summarize_results(team_name, brief, results)

        logger.info(f"团队任务 {task_id} 完成：{len(results['results'])} 成功，{len(results['errors'])} 失败")

        return {
            "success": True,
            "team_name": team_name,
            "task_id": task_id,
            "results": results["results"],
            "errors": results["errors"],
            "summary": task.final_result,
            "policy_used": policy.value,
            "bots_responded": list(results["results"].keys()),
            "bots_failed": list(results["errors"].keys())
        }

    async def _execute_team_tasks(
        self,
        task: TeamTask,
        team: TeamConfig,
        brief: str,
        context: Dict[str, Any] = None,
        on_result: Callable = None
    ) -> Dict[str, Any]:
        """
        并行执行团队任务

        Returns:
            {"results": {bot_id: result}, "errors": {bot_id: error}}
        """
        if not self.gateway:
            logger.warning("Gateway 未设置，返回模拟结果")
            return {
                "results": {bot_id: f"[模拟] {bot_id} 收到：{brief[:30]}..." for bot_id in team.bot_ids},
                "errors": {}
            }

        # 创建并发任务
        tasks = []
        for bot_id in team.bot_ids:
            task_coro = self._execute_single_bot_task(task, bot_id, brief, context)
            tasks.append(asyncio.create_task(task_coro))

        # 等待任务完成（带超时和策略判断）
        results = {"results": {}, "errors": {}}

        # 简单模式：等待所有任务完成
        # TODO: 实现策略感知的提前结束逻辑
        done_list = await asyncio.gather(*tasks, return_exceptions=True)

        # 汇总结果
        for i, bot_id in enumerate(team.bot_ids):
            result = done_list[i]
            if isinstance(result, Exception):
                results["errors"][bot_id] = str(result)
                task.bot_errors[bot_id] = str(result)
                logger.error(f"团队任务 {bot_id} 失败：{result}")
            else:
                results["results"][bot_id] = result
                task.bot_results[bot_id] = result
                logger.info(f"团队任务 {bot_id} 完成")

                # 调用回调
                if on_result:
                    on_result(bot_id, result)

        return results

    async def _execute_single_bot_task(
        self,
        task: TeamTask,
        bot_id: str,
        brief: str,
        context: Dict[str, Any] = None
    ) -> str:
        """
        执行单个 Bot 任务

        构建定制化的 Prompt，包含团队上下文
        """
        # 构建团队上下文 Prompt
        team_prompt = f"""【团队任务 - {task.team_name}】

你正在作为团队成员执行协作任务。

【任务简述】
{brief}

【上下文信息】
"""
        if context:
            for key, value in context.items():
                team_prompt += f"- {key}: {value}\n"

        team_prompt += """
请从你的专业角度给出方案（简洁，200 字以内）。"""

        # 通过 gateway 发送
        if hasattr(self.gateway, 'send_to_bot'):
            response = await self.gateway.send_to_bot(
                bot_id=bot_id,
                message=team_prompt,
                request_id=task.task_id
            )
            return response

        # 模拟
        await asyncio.sleep(0.1)
        return f"[模拟] {bot_id} 回复：收到团队任务"

    def _summarize_results(
        self,
        team_name: str,
        brief: str,
        results: Dict[str, Any]
    ) -> str:
        """
        汇总团队结果

        TODO: 可以集成 LLM 进行智能汇总
        """
        summary_parts = []

        # 成功结果
        for bot_id, result in results["results"].items():
            summary_parts.append(f"【{bot_id}】{result[:100]}...")

        # 错误结果
        for bot_id, error in results["errors"].items():
            summary_parts.append(f"【{bot_id}】失败：{error}")

        if not summary_parts:
            return "团队任务无结果"

        return "\n".join(summary_parts)

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取团队任务状态"""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            return {
                "task_id": task.task_id,
                "team_name": task.team_name,
                "status": task.status,
                "brief": task.brief,
                "created_at": task.created_at.isoformat(),
                "deadline": task.deadline.isoformat(),
                "policy": task.policy.value,
                "results": task.bot_results,
                "errors": task.bot_errors,
                "final_result": task.final_result
            }
        return None


# 全局实例
_delegator: Optional[TeamDelegator] = None


def get_team_delegator(gateway=None, config_loader=None) -> TeamDelegator:
    """获取全局 TeamDelegator 实例"""
    global _delegator
    if _delegator is None:
        _delegator = TeamDelegator(gateway, config_loader)
    return _delegator


def delegate_to_team(
    team_name: str,
    brief: str,
    policy: TeamDelegationPolicy = None,
    gateway=None
) -> typing.Any:
    """便捷函数：委托团队任务"""
    delegator = get_team_delegator(gateway)
    return delegator.delegate_to_team(team_name, brief, policy)


def register_team_as_skill(
    team_name: str,
    coordinator_bot: str,
    description: str = None,
    gateway=None
) -> bool:
    """
    将团队注册为协调者 Bot 的可调用技能

    Args:
        team_name: 团队名称
        coordinator_bot: 协调者 Bot 名称
        description: 技能描述
        gateway: Gateway 实例

    Returns:
        是否成功注册
    """
    delegator = get_team_delegator(gateway)
    team = delegator.teams.get(team_name)

    if not team:
        logger.error(f"团队不存在：{team_name}")
        return False

    # 导入 SkillRegistry
    try:
        from phoenix_core.skill_registry import get_skill_registry
        registry = get_skill_registry()

        # 构建技能描述
        if not description:
            description = f"可以调用{team_name}（成员：{team.bot_ids}）执行{team.description}"

        # 注册技能
        registry.register(
            bot_name=coordinator_bot,
            skill_name=f"调用{team_name}",
            description=description,
            capabilities=team.skills + ["团队协作", "自动执行"]
        )

        logger.info(f"团队技能注册成功：{coordinator_bot} - 调用{team_name}")
        return True

    except Exception as e:
        logger.error(f"注册团队技能失败：{e}")
        return False

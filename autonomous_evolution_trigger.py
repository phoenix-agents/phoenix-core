#!/usr/bin/env python3
"""
Autonomous Evolution Trigger - 自主进化触发器

Phoenix Core Phoenix v2.0 核心模块

功能:
1. 成功任务自动检测 (5+ 步骤，用户满意)
2. 失败率追踪 (执行计数/失败计数)
3. 自动触发器 (失败率>30% 自动进化)
4. AI 辅助分析 (生成进化方案)

Usage:
    from autonomous_evolution_trigger import EvolutionTrigger

    trigger = EvolutionTrigger(bot_name="编导")
    trigger.track_execution("skill_name", success=True)
    trigger.check_and_trigger_evolution("skill_name")
"""

import json
import logging
import os
import urllib.request
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
PHOENIX_CORE_DIR = Path(__file__).parent
EVOLUTION_TRIGGER_DIR = PHOENIX_CORE_DIR / "evolution_triggers"
EVOLUTION_TRIGGER_DIR.mkdir(parents=True, exist_ok=True)

# AI 配置 (用于进化分析)
AI_CONFIG = {
    "base_url": "https://coding.dashscope.aliyuncs.com/v1",
    "api_key": os.environ.get("DASHSCOPE_API_KEY"),
    "model": "qwen3-coder-next",
    "max_tokens": 2000,
    "temperature": 0.2
}


class EvolutionReason(Enum):
    """进化触发原因"""
    HIGH_FAILURE_RATE = "high_failure_rate"  # 失败率过高
    LOW_SUCCESS_SCORE = "low_success_score"  # 成功分数低
    USER_FEEDBACK = "user_feedback"  # 用户反馈
    PERFORMANCE_DEGRADATION = "performance_degradation"  # 性能下降


class EvolutionTrigger:
    """
    自主进化触发器

    追踪技能执行，自动触发进化
    """

    def __init__(self, bot_name: str):
        self.bot_name = bot_name
        self.trigger_dir = EVOLUTION_TRIGGER_DIR / bot_name
        self.trigger_dir.mkdir(parents=True, exist_ok=True)

        # 配置
        self.config = {
            "auto_extract_skills": True,
            "auto_evolve_threshold": 0.3,  # 失败率>30% 自动进化
            "success_score_threshold": 0.6,  # 成功分数<60% 触发进化
            "min_executions_before_evolve": 5,  # 至少执行 5 次后才考虑进化
        }

        # 加载追踪数据
        self._tracking_data: Dict[str, Dict] = {}
        self._load_tracking_data()

    def _load_tracking_data(self):
        """加载追踪数据"""
        data_file = self.trigger_dir / "tracking_data.json"
        if data_file.exists():
            try:
                with open(data_file, "r", encoding="utf-8") as f:
                    self._tracking_data = json.load(f)
                logger.info(f"[{self.bot_name}] Loaded tracking data for {len(self._tracking_data)} skills")
            except Exception as e:
                logger.error(f"Failed to load tracking data: {e}")
                self._tracking_data = {}

    def _save_tracking_data(self):
        """保存追踪数据"""
        data_file = self.trigger_dir / "tracking_data.json"
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(self._tracking_data, f, indent=2, ensure_ascii=False)

    def track_execution(self, skill_name: str, success: bool,
                        execution_time_ms: int = None,
                        user_feedback: str = None,
                        steps_completed: int = None):
        """
        追踪技能执行

        Args:
            skill_name: 技能名称
            success: 是否成功
            execution_time_ms: 执行时间 (毫秒)
            user_feedback: 用户反馈
            steps_completed: 完成的步骤数
        """
        if skill_name not in self._tracking_data:
            self._tracking_data[skill_name] = {
                "skill_name": skill_name,
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "total_execution_time_ms": 0,
                "last_execution": None,
                "user_feedbacks": [],
                "evolution_history": [],
                "created_at": datetime.now().isoformat()
            }

        data = self._tracking_data[skill_name]
        data["total_executions"] += 1
        data["last_execution"] = datetime.now().isoformat()

        if success:
            data["successful_executions"] += 1
        else:
            data["failed_executions"] += 1

        if execution_time_ms:
            data["total_execution_time_ms"] += execution_time_ms

        if user_feedback:
            data["user_feedbacks"].append({
                "feedback": user_feedback,
                "timestamp": datetime.now().isoformat(),
                "success": success
            })

        self._save_tracking_data()
        logger.debug(f"[{self.bot_name}] Tracked execution: {skill_name} (success={success})")

    def get_failure_rate(self, skill_name: str) -> float:
        """获取失败率"""
        if skill_name not in self._tracking_data:
            return 0.0

        data = self._tracking_data[skill_name]
        total = data["total_executions"]
        if total == 0:
            return 0.0

        return data["failed_executions"] / total

    def get_success_score(self, skill_name: str) -> float:
        """获取成功分数"""
        if skill_name not in self._tracking_data:
            return 0.0

        data = self._tracking_data[skill_name]
        total = data["total_executions"]
        if total == 0:
            return 0.0

        return data["successful_executions"] / total

    def get_avg_execution_time(self, skill_name: str) -> float:
        """获取平均执行时间"""
        if skill_name not in self._tracking_data:
            return 0.0

        data = self._tracking_data[skill_name]
        total = data["total_executions"]
        if total == 0:
            return 0.0

        return data["total_execution_time_ms"] / total

    def check_and_trigger_evolution(self, skill_name: str) -> Optional[Dict]:
        """
        检查并触发进化

        Args:
            skill_name: 技能名称

        Returns:
            进化触发结果 (如有)
        """
        if skill_name not in self._tracking_data:
            return None

        data = self._tracking_data[skill_name]

        # 检查是否达到最小执行次数
        if data["total_executions"] < self.config["min_executions_before_evolve"]:
            logger.debug(f"[{self.bot_name}] {skill_name}: Not enough executions ({data['total_executions']}/{self.config['min_executions_before_evolve']})")
            return None

        # 检查失败率
        failure_rate = self.get_failure_rate(skill_name)
        if failure_rate > self.config["auto_evolve_threshold"]:
            return self._trigger_evolution(
                skill_name,
                EvolutionReason.HIGH_FAILURE_RATE,
                f"失败率 {failure_rate:.1%} > 阈值 {self.config['auto_evolve_threshold']:.1%}"
            )

        # 检查成功分数
        success_score = self.get_success_score(skill_name)
        if success_score < self.config["success_score_threshold"]:
            return self._trigger_evolution(
                skill_name,
                EvolutionReason.LOW_SUCCESS_SCORE,
                f"成功分数 {success_score:.1%} < 阈值 {self.config['success_score_threshold']:.1%}"
            )

        # 检查用户反馈
        negative_feedbacks = [
            f for f in data.get("user_feedbacks", [])
            if not f.get("success", True)
        ]
        if len(negative_feedbacks) >= 3:
            return self._trigger_evolution(
                skill_name,
                EvolutionReason.USER_FEEDBACK,
                f"连续 {len(negative_feedbacks)} 次负面反馈"
            )

        return None

    def _trigger_evolution(self, skill_name: str, reason: EvolutionReason,
                           details: str) -> Dict:
        """
        触发进化

        Args:
            skill_name: 技能名称
            reason: 触发原因
            details: 详细信息

        Returns:
            进化触发结果
        """
        logger.info(f"[{self.bot_name}] Triggering evolution for {skill_name}: {reason.value}")

        # 记录进化历史
        if skill_name in self._tracking_data:
            self._tracking_data[skill_name]["evolution_history"].append({
                "reason": reason.value,
                "details": details,
                "triggered_at": datetime.now().isoformat()
            })
            self._save_tracking_data()

        # 生成进化分析
        analysis = self._analyze_evolution(skill_name, reason)

        return {
            "skill_name": skill_name,
            "reason": reason.value,
            "details": details,
            "triggered_at": datetime.now().isoformat(),
            "analysis": analysis,
            "status": "pending"
        }

    def _analyze_evolution(self, skill_name: str, reason: EvolutionReason) -> Dict:
        """
        分析进化需求

        使用 AI 分析技能问题并生成改进建议
        """
        # 获取技能数据
        data = self._tracking_data.get(skill_name, {})

        # 构建分析 prompt
        prompt = f"""分析以下技能的进化需求:

技能名称：{skill_name}
执行次数：{data.get('total_executions', 0)}
成功次数：{data.get('successful_executions', 0)}
失败次数：{data.get('failed_executions', 0)}
失败率：{self.get_failure_rate(skill_name):.1%}
成功分数：{self.get_success_score(skill_name):.1%}
平均执行时间：{self.get_avg_execution_time(skill_name):.0f}ms

触发原因：{reason.value}

请分析:
1. 可能的问题根源
2. 建议的改进方向
3. 具体的修改步骤
"""

        # 调用 AI (简化实现，实际应该调用 API)
        analysis = {
            "root_causes": self._analyze_root_causes(skill_name, reason),
            "improvement_directions": self._suggest_improvements(skill_name, reason),
            "modification_steps": self._generate_modification_steps(skill_name, reason)
        }

        return analysis

    def _analyze_root_causes(self, skill_name: str, reason: EvolutionReason) -> List[str]:
        """分析问题根源"""
        causes = []

        if reason == EvolutionReason.HIGH_FAILURE_RATE:
            causes.append("技能步骤可能存在模糊或不完整的描述")
            causes.append("错误处理逻辑可能不足")
            causes.append("前置条件检查可能缺失")

        elif reason == EvolutionReason.LOW_SUCCESS_SCORE:
            causes.append("技能可能不适合当前使用场景")
            causes.append("技能参数可能需要调整")
            causes.append("技能可能需要更多上下文信息")

        elif reason == EvolutionReason.USER_FEEDBACK:
            causes.append("用户期望与技能输出不匹配")
            causes.append("技能输出格式可能需要优化")
            causes.append("技能可能需要更多自定义选项")

        return causes

    def _suggest_improvements(self, skill_name: str, reason: EvolutionReason) -> List[str]:
        """建议改进方向"""
        improvements = []

        if reason == EvolutionReason.HIGH_FAILURE_RATE:
            improvements.append("增加详细的错误处理步骤")
            improvements.append("添加前置条件验证")
            improvements.append("提供故障排除指南")

        elif reason == EvolutionReason.LOW_SUCCESS_SCORE:
            improvements.append("重新评估技能适用场景")
            improvements.append("优化技能参数配置")
            improvements.append("增加技能变体以适应不同场景")

        elif reason == EvolutionReason.USER_FEEDBACK:
            improvements.append("收集更详细的用户反馈")
            improvements.append("A/B 测试不同输出格式")
            improvements.append("增加用户自定义选项")

        return improvements

    def _generate_modification_steps(self, skill_name: str, reason: EvolutionReason) -> List[str]:
        """生成修改步骤"""
        return [
            f"1. 审查 {skill_name} 的当前实现",
            "2. 识别问题步骤",
            "3. 设计改进方案",
            "4. 生成新版本技能 (v2.0)",
            "5. A/B 测试新旧版本",
            "6. 根据测试结果决定是否废弃旧版本"
        ]

    def get_skill_stats(self, skill_name: str) -> Optional[Dict]:
        """获取技能统计"""
        if skill_name not in self._tracking_data:
            return None

        data = self._tracking_data[skill_name]
        return {
            "skill_name": skill_name,
            "total_executions": data["total_executions"],
            "successful_executions": data["successful_executions"],
            "failed_executions": data["failed_executions"],
            "failure_rate": self.get_failure_rate(skill_name),
            "success_score": self.get_success_score(skill_name),
            "avg_execution_time_ms": self.get_avg_execution_time(skill_name),
            "evolution_count": len(data.get("evolution_history", [])),
            "last_execution": data.get("last_execution")
        }

    def get_all_skills_stats(self) -> List[Dict]:
        """获取所有技能统计"""
        return [
            self.get_skill_stats(name)
            for name in self._tracking_data.keys()
        ]

    def get_evolution_candidates(self) -> List[Dict]:
        """获取需要进化的技能候选"""
        candidates = []

        for skill_name in self._tracking_data.keys():
            result = self.check_and_trigger_evolution(skill_name)
            if result:
                candidates.append(result)

        return candidates


# 全局实例
_triggers: Dict[str, EvolutionTrigger] = {}


def get_evolution_trigger(bot_name: str) -> EvolutionTrigger:
    """获取 Bot 的进化触发器实例"""
    if bot_name not in _triggers:
        _triggers[bot_name] = EvolutionTrigger(bot_name)
    return _triggers[bot_name]


def track_skill_execution(bot_name: str, skill_name: str, success: bool,
                          execution_time_ms: int = None,
                          user_feedback: str = None):
    """追踪技能执行（便捷函数）"""
    trigger = get_evolution_trigger(bot_name)
    trigger.track_execution(
        skill_name, success, execution_time_ms, user_feedback
    )


def check_skill_evolution(bot_name: str, skill_name: str) -> Optional[Dict]:
    """检查技能是否需要进化（便捷函数）"""
    trigger = get_evolution_trigger(bot_name)
    return trigger.check_and_trigger_evolution(skill_name)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Autonomous Evolution Trigger - 自主进化触发器")
        print("\nUsage:")
        print("  python3 autonomous_evolution_trigger.py <bot_name> test")
        sys.exit(1)

    bot_name = sys.argv[1]
    trigger = EvolutionTrigger(bot_name)

    if len(sys.argv) > 2 and sys.argv[2] == "test":
        print(f"\nTesting Evolution Trigger for {bot_name}\n")

        # 模拟多次执行
        print("Simulating skill executions...")
        for i in range(10):
            success = i < 7  # 70% 成功率
            trigger.track_execution(
                skill_name="策划直播",
                success=success,
                execution_time_ms=1000 + i * 100,
                user_feedback="good" if success else "needs improvement"
            )

        # 获取统计
        stats = trigger.get_skill_stats("策划直播")
        print(f"\nSkill Stats:")
        print(f"  Total Executions: {stats['total_executions']}")
        print(f"  Success Rate: {stats['success_score']:.1%}")
        print(f"  Failure Rate: {stats['failure_rate']:.1%}")

        # 检查是否需要进化
        result = trigger.check_and_trigger_evolution("策划直播")
        if result:
            print(f"\nEvolution Triggered!")
            print(f"  Reason: {result['reason']}")
            print(f"  Details: {result['details']}")
        else:
            print(f"\nNo evolution needed")

        # 获取进化候选
        candidates = trigger.get_evolution_candidates()
        print(f"\nEvolution Candidates: {len(candidates)}")

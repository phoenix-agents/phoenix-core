#!/usr/bin/env python3
"""
Phoenix Core - Skill Evaluator (技能评估器)

评估技能执行效果，追踪成功率，生成优化建议。

设计理念：
1. 每次技能执行后记录结果
2. 定期分析技能质量
3. 低质量技能告警
4. 生成优化建议

调用流程:
```
技能执行完成
    ↓
SkillEvaluator.record_execution(skill_name, success, latency, feedback)
    ↓
更新成功率统计
    ↓
定期分析 → 生成优化建议
```

Usage:
    evaluator = SkillEvaluator()
    evaluator.record_execution("活动策划", success=True, latency=2.5)
    stats = evaluator.get_skill_stats("活动策划")
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from phoenix_core.skill_registry import get_skill_registry

logger = logging.getLogger(__name__)


@dataclass
class SkillStats:
    """技能统计信息"""
    skill_name: str
    bot_name: str
    success_count: int
    fail_count: int
    success_rate: float
    avg_latency: float = 0.0
    last_executed: Optional[str] = None
    quality_level: str = "unknown"  # excellent, good, fair, poor


@dataclass
class SkillRecommendation:
    """技能优化建议"""
    skill_name: str
    bot_name: str
    issue: str
    suggestion: str
    priority: str  # high, medium, low


class SkillEvaluator:
    """技能评估器"""

    def __init__(self):
        """初始化 SkillEvaluator"""
        self.skill_registry = get_skill_registry()

        # 质量阈值
        self._excellent_threshold = 0.9  # 成功率 >= 90%
        self._good_threshold = 0.7  # 成功率 >= 70%
        self._fair_threshold = 0.5  # 成功率 >= 50%

        # 告警阈值
        self._low_quality_threshold = 0.3  # 成功率 < 30% 触发告警
        self._min_samples = 5  # 最少样本数

    def record_execution(
        self,
        bot_name: str,
        skill_name: str,
        success: bool,
        latency: float = None,
        feedback: str = None
    ):
        """
        记录技能执行结果

        Args:
            bot_name: Bot 名称
            skill_name: 技能名称
            success: 是否成功
            latency: 执行耗时（秒）
            feedback: 用户反馈
        """
        if success:
            self.skill_registry.record_success(bot_name, skill_name)
        else:
            self.skill_registry.record_failure(bot_name, skill_name)

        logger.info(f"记录技能执行：{bot_name} - {skill_name} - {'成功' if success else '失败'}")

        # TODO: 延迟追踪和反馈可以扩展到单独的表

    def get_skill_stats(self, bot_name: str, skill_name: str) -> Optional[SkillStats]:
        """
        获取技能统计信息

        Args:
            bot_name: Bot 名称
            skill_name: 技能名称

        Returns:
            技能统计信息
        """
        skills = self.skill_registry.get_skills(bot_name)

        for skill in skills:
            if skill["name"] == skill_name:
                total = skill["success_count"] + skill["fail_count"]
                success_rate = skill["success_count"] / total if total > 0 else 0

                quality = self._calculate_quality_level(success_rate, total)

                return SkillStats(
                    skill_name=skill_name,
                    bot_name=bot_name,
                    success_count=skill["success_count"],
                    fail_count=skill["fail_count"],
                    success_rate=round(success_rate, 3),
                    quality_level=quality
                )

        return None

    def _calculate_quality_level(self, success_rate: float, samples: int) -> str:
        """计算质量等级"""
        if samples < self._min_samples:
            return "insufficient_data"

        if success_rate >= self._excellent_threshold:
            return "excellent"
        elif success_rate >= self._good_threshold:
            return "good"
        elif success_rate >= self._fair_threshold:
            return "fair"
        else:
            return "poor"

    def get_all_skills_stats(self) -> List[SkillStats]:
        """获取所有技能的统计信息"""
        all_skills = self.skill_registry.get_all_skills()
        stats = []

        for skill in all_skills:
            total = skill["success_count"] + skill["fail_count"]
            success_rate = skill["success_count"] / total if total > 0 else 0
            quality = self._calculate_quality_level(success_rate, total)

            stats.append(SkillStats(
                skill_name=skill["skill_name"],
                bot_name=skill["bot_name"],
                success_count=skill["success_count"],
                fail_count=skill["fail_count"],
                success_rate=round(success_rate, 3),
                quality_level=quality
            ))

        return stats

    def analyze_and_recommend(self) -> List[SkillRecommendation]:
        """
        分析技能质量并生成优化建议

        Returns:
            优化建议列表
        """
        recommendations = []
        all_skills = self.get_all_skills_stats()

        for skill_stat in all_skills:
            # 跳过数据不足的技能
            if skill_stat.quality_level == "insufficient_data":
                continue

            # 低质量技能告警
            if skill_stat.quality_level == "poor":
                recommendations.append(SkillRecommendation(
                    skill_name=skill_stat.skill_name,
                    bot_name=skill_stat.bot_name,
                    issue=f"成功率过低 ({skill_stat.success_rate:.1%})",
                    suggestion="检查技能描述是否准确，或考虑重新训练",
                    priority="high"
                ))

            # 公平等级技能 - 有改进空间
            elif skill_stat.quality_level == "fair":
                recommendations.append(SkillRecommendation(
                    skill_name=skill_stat.skill_name,
                    bot_name=skill_stat.bot_name,
                    issue=f"成功率有提升空间 ({skill_stat.success_rate:.1%})",
                    suggestion="优化技能触发词或描述",
                    priority="medium"
                ))

        return recommendations

    def get_low_quality_skills(self) -> List[SkillStats]:
        """获取低质量技能列表"""
        all_skills = self.get_all_skills_stats()
        return [s for s in all_skills if s.quality_level == "poor"]

    def get_excellent_skills(self) -> List[SkillStats]:
        """获取优秀技能列表"""
        all_skills = self.get_all_skills_stats()
        return [s for s in all_skills if s.quality_level == "excellent"]

    def get_summary_report(self) -> Dict:
        """
        生成技能评估摘要报告

        Returns:
            摘要报告字典
        """
        all_skills = self.get_all_skills_stats()
        recommendations = self.analyze_and_recommend()

        quality_distribution = {}
        for skill in all_skills:
            level = skill.quality_level
            quality_distribution[level] = quality_distribution.get(level, 0) + 1

        return {
            "total_skills": len(all_skills),
            "quality_distribution": quality_distribution,
            "high_priority_issues": len([r for r in recommendations if r.priority == "high"]),
            "recommendations": [asdict(r) for r in recommendations[:10]],  # 前 10 条
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def log_daily_report(self):
        """记录每日评估报告到文件"""
        report = self.get_summary_report()

        log_dir = Path("/Users/wangsai/phoenix-core/data/skill_evaluation")
        log_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        log_file = log_dir / f"evaluation_{today}.md"

        content = f"""# 技能评估日报 - {today}

## 总览
- 技能总数：{report['total_skills']}
- 高优先级问题：{report['high_priority_issues']}

## 质量分布
"""
        for level, count in report['quality_distribution'].items():
            content += f"- {level}: {count}\n"

        content += "\n## 优化建议\n"
        for rec in report['recommendations']:
            content += f"\n### {rec['skill_name']} ({rec['bot_name']})\n"
            content += f"- **问题**: {rec['issue']}\n"
            content += f"- **建议**: {rec['suggestion']}\n"
            content += f"- **优先级**: {rec['priority']}\n"

        with open(log_file, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"已生成技能评估日报：{log_file}")


# 全局实例
_evaluator: Optional[SkillEvaluator] = None


def get_evaluator() -> SkillEvaluator:
    """获取全局 SkillEvaluator 实例"""
    global _evaluator
    if _evaluator is None:
        _evaluator = SkillEvaluator()
    return _evaluator


def record_skill_execution(
    bot_name: str,
    skill_name: str,
    success: bool,
    latency: float = None,
    feedback: str = None
):
    """便捷函数：记录技能执行"""
    get_evaluator().record_execution(bot_name, skill_name, success, latency, feedback)


def get_skill_evaluation(bot_name: str, skill_name: str) -> Optional[Dict]:
    """便捷函数：获取技能评估"""
    stats = get_evaluator().get_skill_stats(bot_name, skill_name)
    return asdict(stats) if stats else None


def generate_skill_report() -> Dict:
    """便捷函数：生成技能评估报告"""
    return get_evaluator().get_summary_report()

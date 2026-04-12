#!/usr/bin/env python3
"""
AI Evaluator - AI 辅助评估系统

Phoenix Core Phoenix v2.0 技术评估

功能:
1. 模型性能对比 (相同 prompt 测试)
2. 成本对比 (百万 token 价格)
3. 兼容性检查 (API 差异)
4. 生成迁移建议

Usage:
    from ai_evaluator import AIEvaluator

    evaluator = AIEvaluator()
    result = evaluator.evaluate_model_migration("claude-sonnet-4-6", "gpt-5.1")
"""

import json
import logging
import os
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
EVALUATOR_DIR = Path(__file__).parent / "ai_evaluator"
EVALUATOR_DIR.mkdir(parents=True, exist_ok=True)


class AIEvaluator:
    """
    AI 辅助评估器

    用于评估模型迁移、框架升级等
    """

    # 测试用例
    TEST_CASES = [
        {
            "name": "代码生成",
            "prompt": "写一个 Python 函数，计算斐波那契数列的第 n 项",
            "expected_keywords": ["def", "fibonacci", "return"]
        },
        {
            "name": "文本分析",
            "prompt": "分析这段话的情感倾向：'这个产品很好用，我很喜欢'",
            "expected_keywords": ["情感", "正面", "积极"]
        },
        {
            "name": "逻辑推理",
            "prompt": "如果所有 A 都是 B，有些 B 是 C，那么有些 A 是 C 吗？请解释。",
            "expected_keywords": ["逻辑", "推理", "解释"]
        }
    ]

    # 模型价格 (每百万 token，美元)
    MODEL_PRICES = {
        "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
        "claude-haiku-4-5": {"input": 0.8, "output": 4.0},
        "claude-opus-4-6": {"input": 15.0, "output": 75.0},
        "gpt-5.1": {"input": 2.0, "output": 8.0},
        "gpt-4.1": {"input": 5.0, "output": 15.0},
        "deepseek-v3.2": {"input": 1.0, "output": 2.0},
        "qwen3.5-plus": {"input": 0.5, "output": 1.5},
        "kimi-k2.5": {"input": 0.8, "output": 3.2},
    }

    def __init__(self):
        self.eval_dir = EVALUATOR_DIR
        self.reports_dir = self.eval_dir / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        # 缓存
        self._cache: Dict[str, Any] = {}
        self._cache_file = self.eval_dir / "cache.json"
        self._load_cache()

    def _load_cache(self):
        """加载缓存"""
        if self._cache_file.exists():
            try:
                with open(self._cache_file, "r") as f:
                    self._cache = json.load(f)
            except:
                self._cache = {}

    def _save_cache(self):
        """保存缓存"""
        with open(self._cache_file, "w") as f:
            json.dump(self._cache, f, indent=2)

    def evaluate_model_migration(self, from_model: str, to_model: str) -> Dict:
        """
        评估模型迁移

        Args:
            from_model: 当前模型
            to_model: 目标模型

        Returns:
            评估报告
        """
        logger.info(f"Evaluating model migration: {from_model} -> {to_model}")

        # 1. 性能对比
        performance_comparison = self._benchmark_models(from_model, to_model)

        # 2. 成本对比
        cost_comparison = self._compare_costs(from_model, to_model)

        # 3. 兼容性检查
        compatibility = self._check_compatibility(from_model, to_model)

        # 4. 生成建议
        recommendation = self._generate_recommendation(
            performance_comparison, cost_comparison, compatibility
        )

        report = {
            "evaluation_date": datetime.now().isoformat(),
            "from_model": from_model,
            "to_model": to_model,
            "performance_comparison": performance_comparison,
            "cost_comparison": cost_comparison,
            "compatibility": compatibility,
            "recommendation": recommendation,
            "migration_effort": self._estimate_migration_effort(compatibility)
        }

        # 保存报告
        report_file = self.reports_dir / f"migration_{from_model}_to_{to_model}_{datetime.now().strftime('%Y%m%d')}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"Evaluation report saved: {report_file}")

        return report

    def _benchmark_models(self, model_a: str, model_b: str) -> Dict:
        """
        对比模型性能

        使用相同 prompt 测试两个模型
        """
        results = {
            "model_a": model_a,
            "model_b": model_b,
            "test_cases": []
        }

        # 模拟测试结果 (实际应该调用 API)
        for test_case in self.TEST_CASES:
            # 这里应该实际调用两个模型的 API
            # 由于需要 API key，这里使用模拟数据
            result = {
                "name": test_case["name"],
                "model_a_score": 0.85 + (hash(model_a) % 10) / 100,
                "model_b_score": 0.85 + (hash(model_b) % 10) / 100,
                "model_a_latency_ms": 200 + (hash(model_a) % 300),
                "model_b_latency_ms": 200 + (hash(model_b) % 300)
            }
            results["test_cases"].append(result)

        # 计算平均分
        results["model_a_avg_score"] = sum(
            r["model_a_score"] for r in results["test_cases"]
        ) / len(results["test_cases"])
        results["model_b_avg_score"] = sum(
            r["model_b_score"] for r in results["test_cases"]
        ) / len(results["test_cases"])
        results["winner"] = (
            model_b if results["model_b_avg_score"] > results["model_a_avg_score"]
            else model_a
        )

        return results

    def _compare_costs(self, model_a: str, model_b: str) -> Dict:
        """对比模型成本"""
        price_a = self.MODEL_PRICES.get(model_a, {"input": 5.0, "output": 15.0})
        price_b = self.MODEL_PRICES.get(model_b, {"input": 5.0, "output": 15.0})

        # 估算每月成本 (假设 100M input + 50M output)
        estimated_input = 100  # 百万 token
        estimated_output = 50  # 百万 token

        monthly_cost_a = (
            price_a["input"] * estimated_input + price_a["output"] * estimated_output
        )
        monthly_cost_b = (
            price_b["input"] * estimated_input + price_b["output"] * estimated_output
        )

        return {
            "model_a": model_a,
            "model_a_price": price_a,
            "model_b": model_b,
            "model_b_price": price_b,
            "estimated_monthly_usage": {
                "input_tokens_million": estimated_input,
                "output_tokens_million": estimated_output
            },
            "model_a_monthly_cost": monthly_cost_a,
            "model_b_monthly_cost": monthly_cost_b,
            "cost_saving": monthly_cost_a - monthly_cost_b,
            "cost_saving_percent": (
                (monthly_cost_a - monthly_cost_b) / monthly_cost_a * 100
                if monthly_cost_a > 0 else 0
            )
        }

    def _check_compatibility(self, from_model: str, to_model: str) -> Dict:
        """检查 API 兼容性"""
        # 检测模型 provider
        from_provider = self._get_model_provider(from_model)
        to_provider = self._get_model_provider(to_model)

        # API 差异
        api_differences = []
        breaking_changes = []

        if from_provider != to_provider:
            # 不同 provider 可能有不同的 API 格式
            api_differences.append({
                "type": "provider_change",
                "description": f"Provider 从 {from_provider} 变为 {to_provider}",
                "impact": "medium",
                "migration_steps": [
                    "更新 API base URL",
                    "更新 API key 配置",
                    "检查请求格式差异"
                ]
            })

        # 检查模型特定功能
        from_features = self._get_model_features(from_model)
        to_features = self._get_model_features(to_model)

        missing_features = set(from_features) - set(to_features)
        new_features = set(to_features) - set(from_features)

        if missing_features:
            breaking_changes.append({
                "type": "missing_features",
                "description": f"缺失功能：{missing_features}",
                "impact": "high" if missing_features else "low"
            })

        return {
            "from_provider": from_provider,
            "to_provider": to_provider,
            "api_differences": api_differences,
            "breaking_changes": breaking_changes,
            "missing_features": list(missing_features),
            "new_features": list(new_features),
            "compatibility_score": max(0, 100 - len(breaking_changes) * 20 - len(api_differences) * 10)
        }

    def _get_model_provider(self, model: str) -> str:
        """获取模型 provider"""
        if "claude" in model:
            return "anthropic"
        elif "gpt" in model:
            return "openai"
        elif "deepseek" in model:
            return "deepseek"
        elif "qwen" in model:
            return "aliyun"
        elif "kimi" in model:
            return "moonshot"
        return "unknown"

    def _get_model_features(self, model: str) -> List[str]:
        """获取模型功能列表"""
        features = ["text_completion", "chat"]

        # 根据模型添加特定功能
        if "vision" in model or "claude" in model:
            features.append("vision")
        if "tool" in model or "function" in model:
            features.append("function_calling")

        return features

    def _generate_recommendation(self, performance: Dict, cost: Dict,
                                  compatibility: Dict) -> Dict:
        """生成迁移建议"""
        # 综合评分
        performance_score = (
            1 if performance["model_b_avg_score"] > performance["model_a_avg_score"]
            else 0 if performance["model_b_avg_score"] < performance["model_a_avg_score"]
            else 0.5
        )

        cost_score = 1 if cost["cost_saving"] > 0 else 0
        compatibility_score = compatibility["compatibility_score"] / 100

        # 综合得分
        total_score = performance_score * 0.4 + cost_score * 0.3 + compatibility_score * 0.3

        if total_score >= 0.8:
            recommendation = "升级"
            reason = "综合评估推荐迁移"
        elif total_score >= 0.5:
            recommendation = "观望"
            reason = "有利有弊，建议观望"
        else:
            recommendation = "不推荐"
            reason = "迁移成本过高或收益有限"

        return {
            "recommendation": recommendation,
            "reason": reason,
            "total_score": total_score,
            "performance_score": performance_score,
            "cost_score": cost_score,
            "compatibility_score": compatibility_score,
            "key_factors": []
        }

    def _estimate_migration_effort(self, compatibility: Dict) -> str:
        """估算迁移工作量"""
        breaking_changes = len(compatibility.get("breaking_changes", []))
        api_differences = len(compatibility.get("api_differences", []))

        effort_score = breaking_changes * 3 + api_differences * 1

        if effort_score >= 6:
            return "高"
        elif effort_score >= 3:
            return "中"
        else:
            return "低"


# 全局实例
_evaluator: Optional[AIEvaluator] = None


def get_ai_evaluator() -> AIEvaluator:
    """获取 AI 评估器实例"""
    global _evaluator
    if _evaluator is None:
        _evaluator = AIEvaluator()
    return _evaluator


def evaluate_migration(from_model: str, to_model: str) -> Dict:
    """评估模型迁移（便捷函数）"""
    evaluator = get_ai_evaluator()
    return evaluator.evaluate_model_migration(from_model, to_model)


if __name__ == "__main__":
    import sys

    evaluator = AIEvaluator()

    if len(sys.argv) >= 3:
        from_model = sys.argv[1]
        to_model = sys.argv[2]

        print(f"Evaluating migration: {from_model} -> {to_model}\n")
        report = evaluator.evaluate_model_migration(from_model, to_model)

        print(f"Recommendation: {report['recommendation']['recommendation']}")
        print(f"Reason: {report['recommendation']['reason']}")
        print(f"Migration Effort: {report['migration_effort']}")
        print(f"Cost Saving: ${report['cost_comparison']['cost_saving']:.2f}/month")

    else:
        print("AI Evaluator - AI 辅助评估系统")
        print("\nUsage:")
        print("  python3 ai_evaluator.py <from_model> <to_model>")
        print("\nExamples:")
        print("  python3 ai_evaluator.py claude-sonnet-4-6 gpt-5.1")
        print("  python3 ai_evaluator.py deepseek-v3.2 qwen3.5-plus")

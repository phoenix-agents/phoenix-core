#!/usr/bin/env python3
"""
Phoenix Core - Skill Learner (技能学习者)

从历史对话和成功任务中自动学习新技能模式。

设计理念：
1. 成功任务 → 提取新模式 → 注册新技能
2. 每天凌晨分析昨日任务
3. 收到正面反馈自动提升权重

调用流程:
```
成功任务完成
    ↓
SkillLearner.analyze_task_result()
    ↓
提取 (任务类型，处理模式，结果特征)
    ↓
生成技能描述 → SkillRegistry.register()
```

Usage:
    learner = SkillLearner()
    await learner.analyze_task_result(task_id, user_input, bot_response, success=True)
"""

import json
import logging
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict

from phoenix_core.skill_registry import get_skill_registry
from phoenix_core.memory_db import get_memory_db

logger = logging.getLogger(__name__)


@dataclass
class SkillPattern:
    """学习到的技能模式"""
    trigger_keywords: List[str]  # 触发关键词
    bot_name: str  # 执行 Bot
    skill_name: str  # 技能名称
    description: str  # 技能描述
    success_count: int = 1  # 成功次数
    pattern_source: str = "auto_learned"  # 来源标记


class SkillLearner:
    """技能学习者"""

    def __init__(self, db_path: str = None):
        """
        初始化 SkillLearner

        Args:
            db_path: 记忆数据库路径
        """
        self.db_path = db_path
        self.skill_registry = get_skill_registry()
        self.memory_db = get_memory_db()

        # 学习缓存 - 待确认的技能模式
        self._pending_patterns: Dict[str, SkillPattern] = {}

        # 配置
        self._confirmation_threshold = 3  # 成功多少次后自动注册
        self._min_pattern_length = 3  # 最小触发词长度

    async def analyze_task_result(
        self,
        task_id: str,
        user_input: str,
        bot_response: str,
        bot_name: str,
        success: bool = True
    ) -> Optional[str]:
        """
        分析任务执行结果，学习新模式

        Args:
            task_id: 任务 ID
            user_input: 用户输入
            bot_response: Bot 回复
            bot_name: 执行 Bot 名称
            success: 是否成功

        Returns:
            如果学习了新技能，返回技能名称；否则返回 None
        """
        if not success:
            logger.info(f"任务失败，不学习：{task_id}")
            return None

        logger.info(f"分析成功任务：{task_id}")

        # Step 1: 提取任务特征
        task_type = self._extract_task_type(user_input)
        trigger_keywords = self._extract_trigger_keywords(user_input)

        if not trigger_keywords:
            logger.info("未提取到有效触发词，跳过学习")
            return None

        # Step 2: 生成技能名称和描述
        skill_name = self._generate_skill_name(task_type, bot_name)
        description = self._generate_skill_description(user_input, bot_response)

        # Step 3: 创建技能模式
        pattern = SkillPattern(
            trigger_keywords=trigger_keywords,
            bot_name=bot_name,
            skill_name=skill_name,
            description=description
        )

        # Step 4: 更新缓存或注册
        pattern_key = f"{bot_name}:{skill_name}"

        if pattern_key in self._pending_patterns:
            # 已存在，增加成功计数
            existing = self._pending_patterns[pattern_key]
            existing.success_count += 1
            logger.info(f"技能模式计数 +1: {skill_name} ({existing.success_count}/{self._confirmation_threshold})")

            # 达到阈值，正式注册
            if existing.success_count >= self._confirmation_threshold:
                return self._register_learned_skill(existing)
        else:
            # 新技能，加入缓存
            self._pending_patterns[pattern_key] = pattern
            logger.info(f"新技能模式加入缓存：{skill_name}")

        return None

    def _extract_task_type(self, user_input: str) -> str:
        """提取任务类型"""
        # 简单版本：基于关键词分类
        task_types = {
            "活动策划": ["策划", "活动", "方案", "设计"],
            "弹幕管理": ["弹幕", "评论", "管理", "秩序"],
            "内容脚本": ["脚本", "内容", "节目", "编排"],
            "推广方案": ["推广", "营销", "宣传", "引流"],
            "技术支持": ["技术", "设备", "推流", "故障"],
            "视觉设计": ["设计", "视觉", "图片", "美工"],
            "视频剪辑": ["剪辑", "视频", "后期", "制作"],
            "客服回复": ["客服", "咨询", "问题", "解答"],
            "商务合作": ["商务", "合作", "渠道", "对接"]
        }

        input_lower = user_input.lower()

        for task_type, keywords in task_types.items():
            for kw in keywords:
                if kw in input_lower:
                    return task_type

        return "通用任务"

    def _extract_trigger_keywords(self, user_input: str) -> List[str]:
        """提取触发关键词"""
        # 中文分词（简单版本：按 2-4 字组合提取）
        keywords = []

        # 移除停用词
        stopwords = {"的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "一个"}

        # 提取 2-4 字词组
        words = re.findall(r'[\u4e00-\u9fa5]{2,4}', user_input)

        for word in words:
            if word not in stopwords and len(word) >= self._min_pattern_length:
                keywords.append(word)

        # 去重，保留前 5 个
        unique_keywords = list(dict.fromkeys(keywords))[:5]

        return unique_keywords

    def _generate_skill_name(self, task_type: str, bot_name: str) -> str:
        """生成技能名称"""
        # 格式：任务类型 + Bot 名（简化版）
        return f"{task_type}"

    def _generate_skill_description(self, user_input: str, bot_response: str) -> str:
        """生成技能描述"""
        # 简单版本：使用用户输入作为基础
        # 复杂版本：可以用 LLM 总结
        return f"处理{user_input[:30]}类任务"

    def _register_learned_skill(self, pattern: SkillPattern) -> str:
        """
        正式注册学习到的技能

        Args:
            pattern: 技能模式

        Returns:
            技能名称
        """
        # 从缓存移除
        pattern_key = f"{pattern.bot_name}:{pattern.skill_name}"
        self._pending_patterns.pop(pattern_key, None)

        # 注册到 SkillRegistry
        capabilities = pattern.trigger_keywords  # 使用触发词作为能力标签

        success = self.skill_registry.register(
            bot_name=pattern.bot_name,
            skill_name=pattern.skill_name,
            description=pattern.description,
            capabilities=capabilities
        )

        if success:
            logger.info(f"✅ 自动学习并注册新技能：{pattern.bot_name} - {pattern.skill_name}")
            logger.info(f"   触发词：{pattern.trigger_keywords}")
            logger.info(f"   描述：{pattern.description}")

            # 记录学习日志
            self._log_learning(pattern)

            return pattern.skill_name
        else:
            logger.error(f"技能注册失败：{pattern.skill_name}")
            return None

    def _log_learning(self, pattern: SkillPattern):
        """记录学习日志到文件"""
        log_dir = Path("/Users/wangsai/phoenix-core/data/skill_learning")
        log_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        log_file = log_dir / f"learning_{today}.md"

        entry = f"""
## {pattern.skill_name} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

- **Bot**: {pattern.bot_name}
- **触发词**: {', '.join(pattern.trigger_keywords)}
- **描述**: {pattern.description}
- **来源**: {pattern.pattern_source}

"""

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry)

    async def analyze_historical_tasks(self, days: int = 1) -> int:
        """
        分析历史任务，批量学习

        Args:
            days: 分析过去多少天的任务

        Returns:
            学习到的新技能数量
        """
        logger.info(f"开始分析过去 {days} 天的历史任务...")

        # 从记忆数据库查询历史对话
        conn = self.memory_db._get_connection()

        cutoff_date = datetime.now() - timedelta(days=days)

        cursor = conn.execute("""
            SELECT bot_id, role, content, timestamp
            FROM memory
            WHERE timestamp >= ?
            ORDER BY timestamp
        """, (cutoff_date.strftime("%Y-%m-%d %H:%M:%S"),))

        conversations = []
        for row in cursor.fetchall():
            conversations.append({
                "bot_id": row[0],
                "role": row[1],
                "content": row[2],
                "timestamp": row[3]
            })

        conn.close()

        if not conversations:
            logger.info("没有历史对话数据")
            return 0

        # 分组对话（按用户输入 + Bot 回复配对）
        learned_count = 0
        i = 0
        while i < len(conversations) - 1:
            conv = conversations[i]
            next_conv = conversations[i + 1]

            # 检测用户输入 → Bot 回复的配对
            if conv["role"] == "user" and next_conv["role"] == "assistant":
                task_id = f"hist-{conv['timestamp']}"
                await self.analyze_task_result(
                    task_id=task_id,
                    user_input=conv["content"],
                    bot_response=next_conv["content"],
                    bot_name=next_conv["bot_id"],
                    success=True
                )
                learned_count += 1

            i += 1

        logger.info(f"历史任务学习完成，共分析 {learned_count} 个任务")
        return learned_count

    def get_pending_patterns(self) -> List[Dict]:
        """获取待确认的技能模式"""
        return [asdict(p) for p in self._pending_patterns.values()]

    async def learn_from_feedback(
        self,
        bot_name: str,
        skill_name: str,
        rating: int,
        feedback: str = ""
    ):
        """
        从用户反馈中学习

        Args:
            bot_name: Bot 名称
            skill_name: 技能名称
            rating: 评分 (1-5)
            feedback: 反馈内容
        """
        if rating >= 4:
            # 正面反馈，增加权重
            self.skill_registry.record_success(bot_name, skill_name)
            logger.info(f"正面反馈：{bot_name} - {skill_name} 权重 +1")
        elif rating <= 2:
            # 负面反馈，记录失败
            self.skill_registry.record_failure(bot_name, skill_name)
            logger.warning(f"负面反馈：{bot_name} - {skill_name} 失败计数 +1")


# 全局实例
_learner: Optional[SkillLearner] = None


def get_learner() -> SkillLearner:
    """获取全局 SkillLearner 实例"""
    global _learner
    if _learner is None:
        _learner = SkillLearner()
    return _learner


async def analyze_task(
    task_id: str,
    user_input: str,
    bot_response: str,
    bot_name: str,
    success: bool = True
) -> Optional[str]:
    """便捷函数：分析任务并学习"""
    return await get_learner().analyze_task_result(
        task_id, user_input, bot_response, bot_name, success
)


async def learn_from_history(days: int = 1) -> int:
    """便捷函数：从历史任务学习"""
    return await get_learner().analyze_historical_tasks(days)

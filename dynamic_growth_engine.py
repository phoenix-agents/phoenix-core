#!/usr/bin/env python3
"""
Dynamic Growth Engine - 动态成长引擎

Phoenix Core Phoenix v2.0 核心模块

功能:
1. 互动日志记录 (log_interaction)
2. 成功任务分析 (analyze_successful_task)
3. 技能自动提取 (extract_skill)
4. 人设更新建议 (update_persona)
5. 用户审批流程 (request_approval)

核心理念: 静态人设 + 动态成长 = 会进化的数字团队
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class InteractionLog:
    """互动日志条目"""

    def __init__(self, bot_name: str, user_message: str, bot_response: str,
                 tool_iterations: int = 0, success: bool = True,
                 user_feedback: str = None):
        self.bot_name = bot_name
        self.timestamp = datetime.now()
        self.user_message = user_message
        self.bot_response = bot_response
        self.tool_iterations = tool_iterations
        self.success = success
        self.user_feedback = user_feedback

        # 分析结果
        self.task_steps = 0
        self.collaboration_bots = []
        self.skills_used = []

    def to_dict(self) -> Dict:
        return {
            "bot_name": self.bot_name,
            "timestamp": self.timestamp.isoformat(),
            "user_message": self.user_message,
            "bot_response": self.bot_response,
            "tool_iterations": self.tool_iterations,
            "success": self.success,
            "user_feedback": self.user_feedback,
            "task_steps": self.task_steps,
            "collaboration_bots": self.collaboration_bots,
            "skills_used": self.skills_used
        }


class DynamicGrowthEngine:
    """
    动态成长引擎 - 让 Bot 从互动中学习

    每个 Bot 拥有独立的成长引擎，记录互动、提取技能、进化人设
    """

    def __init__(self, bot_name: str):
        self.bot_name = bot_name
        self.workspace_dir = Path(f"workspaces/{bot_name}")
        self.dynamic_dir = self.workspace_dir / "DYNAMIC"
        self.learnings_dir = self.dynamic_dir / "learnings"
        self.skills_dir = self.dynamic_dir / "skills"
        self.relationships_dir = self.dynamic_dir / "relationships"

        # 创建目录结构
        self._init_directories()

        # 加载配置
        self._load_config()

    def _init_directories(self):
        """初始化目录结构"""
        self.dynamic_dir.mkdir(parents=True, exist_ok=True)
        self.learnings_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.relationships_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"{self.bot_name} DYNAMIC directories initialized")

    def _load_config(self):
        """加载配置"""
        self.config = {
            "auto_log_interactions": True,
            "auto_extract_skills": True,
            "require_approval_for_skills": False,  # 改为自动批准，无需手动审批
            "success_threshold_iterations": 4,  # 4+ 步骤认为是复杂任务
            "positive_feedback_keywords": ["很好", "不错", "优秀", "完美", "谢谢", "好的"],
            "negative_feedback_keywords": ["不对", "错误", "不好", "重新", "再试"]
        }

    def log_interaction(self, user_message: str, bot_response: str,
                        tool_iterations: int = 0, user_feedback: str = None) -> InteractionLog:
        """
        记录互动日志

        Args:
            user_message: 用户消息
            bot_response: Bot 回复
            tool_iterations: 工具调用次数
            user_feedback: 用户反馈（可选）

        Returns:
            InteractionLog: 互动日志条目
        """
        # 分析成功/失败
        success = True
        if user_feedback:
            # 根据用户反馈判断
            for keyword in self.config["negative_feedback_keywords"]:
                if keyword in user_feedback:
                    success = False
                    break
            for keyword in self.config["positive_feedback_keywords"]:
                if keyword in user_feedback:
                    success = True
                    break
        elif isinstance(tool_iterations, int) and tool_iterations > 20:
            # 工具调用过多，可能有问题
            success = False
        elif isinstance(tool_iterations, list):
            # 如果传入的是列表，计算总迭代次数
            total_iterations = sum(item.get("iterations", 0) for item in tool_iterations if isinstance(item, dict))
            if total_iterations > 20:
                success = False
            tool_iterations = total_iterations

        # 创建日志条目
        log = InteractionLog(
            bot_name=self.bot_name,
            user_message=user_message,
            bot_response=bot_response,
            tool_iterations=tool_iterations,
            success=success,
            user_feedback=user_feedback
        )

        # 分析任务步骤
        log.task_steps = self._analyze_task_steps(bot_response)

        # 分析协作 Bot
        log.collaboration_bots = self._analyze_collaboration(bot_response)

        # 分析使用的技能
        log.skills_used = self._analyze_skills_used(bot_response)

        # 保存日志
        if self.config["auto_log_interactions"]:
            self._save_interaction_log(log)

        logger.info(f"[{self.bot_name}] Interaction logged: success={success}, steps={log.task_steps}")

        return log

    def _analyze_task_steps(self, response: str) -> int:
        """分析任务步骤数量"""
        # 查找序号列表 (1. 2. 3. 或 第一步、第二步)
        numbered_steps = re.findall(r'^\s*(\d+)[\.、]\s*', response, re.MULTILINE)
        if numbered_steps:
            return len(numbered_steps)

        # 查找步骤关键词
        step_keywords = ["第一步", "第二步", "第三步", "第四步", "第五步",
                        "首先", "然后", "接着", "最后", "步骤"]
        count = sum(1 for kw in step_keywords if kw in response)

        return min(count, 10)  # 最多算 10 步

    def _analyze_collaboration(self, response: str) -> List[str]:
        """分析协作的 Bot"""
        bots = []
        bot_names = ["编导", "剪辑", "美工", "场控", "客服", "运营", "渠道", "小小谦"]

        for bot_name in bot_names:
            # 查找 @mention 格式
            if f"@{bot_name}" in response or f"<@{bot_name}>" in response:
                bots.append(bot_name)

        return bots

    def _analyze_skills_used(self, response: str) -> List[str]:
        """分析使用的技能"""
        skills = []

        # 查找技能关键词
        skill_keywords = {
            "策划直播": ["直播", "策划", "流程", "福袋"],
            "视频剪辑": ["剪辑", "视频", "节奏", "转场"],
            "数据分析": ["数据", "分析", "增长", "转化"],
            "粉丝运营": ["粉丝", "互动", "私域", "社群"],
            "内容创作": ["内容", "创意", "脚本", "文案"]
        }

        for skill_name, keywords in skill_keywords.items():
            if any(kw in response for kw in keywords):
                skills.append(skill_name)

        return skills

    def _save_interaction_log(self, log: InteractionLog):
        """保存互动日志"""
        # 按日期生成日志文件
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = self.learnings_dir / f"{date_str}.md"

        # 准备日志内容
        log_entry = f"""
## [{log.timestamp.strftime("%H:%M")}] {"✅ 成功" if log.success else "❌ 失败"}

**用户消息**: {log.user_message[:200]}...

**Bot 回复**: {log.bot_response[:200]}...

**工具调用**: {log.tool_iterations} 次
**任务步骤**: {log.task_steps} 步
**协作 Bot**: {', '.join(log.collaboration_bots) if log.collaboration_bots else '无'}
**使用技能**: {', '.join(log.skills_used) if log.skills_used else '无'}

**用户反馈**: {log.user_feedback or '无'}

---
"""

        # 追加到日志文件
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)

    def analyze_successful_task(self, log: InteractionLog) -> Optional[Dict]:
        """
        分析成功任务，提取关键步骤

        Args:
            log: 互动日志条目

        Returns:
            Dict: 任务分析结果
        """
        if not log.success:
            return None

        if log.task_steps < self.config["success_threshold_iterations"]:
            return None

        # 提取任务结构
        analysis = {
            "trigger": log.user_message[:100],
            "steps": self._extract_steps(log.bot_response),
            "tips": self._extract_tips(log.bot_response),
            "collaboration": self._extract_collaboration_tips(log),
            "tools_used": log.skills_used,
            "iteration_count": log.tool_iterations,
            "timestamp": log.timestamp.isoformat()
        }

        logger.info(f"[{self.bot_name}] Analyzed successful task: {len(analysis['steps'])} steps")

        return analysis

    def _extract_steps(self, response: str) -> List[str]:
        """从回复中提取步骤"""
        steps = []

        # 匹配序号列表
        pattern = r'^\s*(?:\d+|[一二三四五六七八九十]+)[\.、]\s*(.+?)$'
        for match in re.finditer(pattern, response, re.MULTILINE):
            steps.append(match.group(1).strip())

        # 如果没有找到序号列表，尝试分段
        if not steps:
            paragraphs = response.split('\n\n')
            steps = [p.strip() for p in paragraphs if len(p) > 20][:5]

        return steps

    def _extract_tips(self, response: str) -> List[str]:
        """从回复中提取技巧提示"""
        tips = []

        # 查找提示关键词
        tip_keywords = ["注意", "提示", "建议", "技巧", "关键", "重要", "小心"]
        for line in response.split('\n'):
            for kw in tip_keywords:
                if kw in line:
                    tips.append(line.strip())
                    break

        return tips[:5]  # 最多 5 条

    def _extract_collaboration_tips(self, log: InteractionLog) -> List[str]:
        """提取协作提示"""
        tips = []

        if log.collaboration_bots:
            for bot in log.collaboration_bots:
                tips.append(f"与 {bot} 协作完成")

        return tips

    def extract_skill(self, analysis: Dict) -> str:
        """
        从任务分析中提取技能

        Args:
            analysis: 任务分析结果

        Returns:
            str: 生成的 SKILL.md 内容
        """
        skill_name = analysis.get("trigger", "未命名技能")[:50]
        skill_name = re.sub(r'[^\w\s\u4e00-\u9fff]', '', skill_name).strip()

        skill_md = f"""---
name: {skill_name}
description: 自动生成的技能
auto_generated: true
version: 1.0.0
created_at: {datetime.now().isoformat()}
---

# {skill_name}

## 触发条件
{analysis.get('trigger', 'N/A')}

## 执行步骤
"""
        # 添加步骤
        for i, step in enumerate(analysis.get('steps', []), 1):
            skill_md += f"\n{i}. {step}"

        # 添加技巧提示
        if analysis.get('tips'):
            skill_md += "\n\n## 技巧提示\n"
            for tip in analysis.get('tips', []):
                skill_md += f"- {tip}\n"

        # 添加协作提示
        if analysis.get('collaboration'):
            skill_md += "\n\n## 协作提示\n"
            for tip in analysis.get('collaboration', []):
                skill_md += f"- {tip}\n"

        return skill_md

    def save_skill(self, skill_md: str, skill_name: str = None) -> Path:
        """
        保存技能到文件

        Args:
            skill_md: SKILL.md 内容
            skill_name: 技能名称（可选）

        Returns:
            Path: 保存的文件路径
        """
        if not skill_name:
            skill_name = f"skill_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 清理文件名
        skill_name = re.sub(r'[^\w\s\u4e00-\u9fff]', '_', skill_name).strip()
        skill_file = self.skills_dir / f"{skill_name}.md"

        with open(skill_file, "w", encoding="utf-8") as f:
            f.write(skill_md)

        logger.info(f"[{self.bot_name}] Skill saved to {skill_file}")

        return skill_file

    def request_user_approval(self, skill_md: str, skill_name: str) -> Dict:
        """
        请求用户批准新技能

        Args:
            skill_md: SKILL.md 内容
            skill_name: 技能名称

        Returns:
            Dict: 审批请求信息
        """
        approval_request = {
            "type": "skill_approval",
            "bot_name": self.bot_name,
            "skill_name": skill_name,
            "skill_preview": skill_md[:500] + "..." if len(skill_md) > 500 else skill_md,
            "timestamp": datetime.now().isoformat(),
            "status": "pending"
        }

        # 保存审批请求
        approval_file = self.dynamic_dir / f"approval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(approval_file, "w", encoding="utf-8") as f:
            json.dump(approval_request, f, indent=2, ensure_ascii=False)

        logger.info(f"[{self.bot_name}] Approval request saved: {skill_name}")

        return approval_request

    def process_interaction(self, user_message: str, bot_response: str,
                           tool_iterations: int = 0, user_feedback: str = None) -> Optional[Dict]:
        """
        处理互动并尝试提取技能

        Args:
            user_message: 用户消息
            bot_response: Bot 回复
            tool_iterations: 工具调用次数
            user_feedback: 用户反馈

        Returns:
            Dict: 处理结果（如有新技能）
        """
        # 1. 记录互动
        log = self.log_interaction(user_message, bot_response, tool_iterations, user_feedback)

        # 2. 分析成功任务
        if log.success and log.task_steps >= self.config["success_threshold_iterations"]:
            analysis = self.analyze_successful_task(log)

            if analysis and self.config["auto_extract_skills"]:
                # 3. 提取技能
                skill_md = self.extract_skill(analysis)

                # 4. 请求用户批准
                if self.config["require_approval_for_skills"]:
                    approval = self.request_user_approval(skill_md, analysis.get("trigger", "新技能"))
                    return {
                        "action": "approval_pending",
                        "log": log.to_dict(),
                        "analysis": analysis,
                        "approval_request": approval
                    }
                else:
                    # 直接保存技能
                    skill_file = self.save_skill(skill_md)
                    return {
                        "action": "skill_saved",
                        "log": log.to_dict(),
                        "analysis": analysis,
                        "skill_file": str(skill_file)
                    }

        return {
            "action": "logged",
            "log": log.to_dict()
        }

    def get_learning_summary(self, days: int = 3) -> Dict:
        """
        获取学习摘要

        Args:
            days: 最近 N 天

        Returns:
            Dict: 学习摘要
        """
        summary = {
            "bot_name": self.bot_name,
            "period_days": days,
            "total_interactions": 0,
            "successful_interactions": 0,
            "failed_interactions": 0,
            "skills_created": 0,
            "collaboration_count": 0
        }

        # 读取最近的日志文件
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=days)

        for log_file in self.learnings_dir.glob("*.md"):
            content = log_file.read_text(encoding="utf-8")

            # 统计成功/失败
            summary["total_interactions"] += content.count("## [")
            summary["successful_interactions"] += content.count("✅ 成功")
            summary["failed_interactions"] += content.count("❌ 失败")

        # 统计技能
        summary["skills_created"] = len(list(self.skills_dir.glob("*.md")))

        return summary


# 全局实例
_engines: Dict[str, DynamicGrowthEngine] = {}


def get_growth_engine(bot_name: str) -> DynamicGrowthEngine:
    """获取 Bot 的成长引擎实例"""
    if bot_name not in _engines:
        _engines[bot_name] = DynamicGrowthEngine(bot_name)
    return _engines[bot_name]


def process_bot_interaction(bot_name: str, user_message: str, bot_response: str,
                            tool_iterations: int = 0, user_feedback: str = None) -> Optional[Dict]:
    """
    处理 Bot 互动并尝试提取技能

    便捷函数，用于 Bot 主程序调用

    Args:
        bot_name: Bot 名称
        user_message: 用户消息
        bot_response: Bot 回复
        tool_iterations: 工具调用次数
        user_feedback: 用户反馈

    Returns:
        Dict: 处理结果
    """
    engine = get_growth_engine(bot_name)
    return engine.process_interaction(user_message, bot_response, tool_iterations, user_feedback)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Dynamic Growth Engine - 动态成长引擎")
        print("\nUsage:")
        print("  python3 dynamic_growth_engine.py <bot_name>")
        print("  python3 dynamic_growth_engine.py 编导 test")
        sys.exit(1)

    bot_name = sys.argv[1]
    engine = DynamicGrowthEngine(bot_name)

    if len(sys.argv) > 2 and sys.argv[2] == "test":
        # 测试模式
        print(f"\nTesting Dynamic Growth Engine for {bot_name}\n")

        # 模拟互动
        result = engine.process_interaction(
            user_message="策划一场生日直播",
            bot_response="""
好的，我来策划一场生日直播：

1. 确认直播时间、时长、预算
2. 设计流程（开场→互动→高潮→结尾）
3. 规划福袋（数量、时机、内容）
4. 准备应急预案

注意：提前与场控沟通节奏
""",
            tool_iterations=8,
            user_feedback="很好"
        )

        print(f"Result: {json.dumps(result, indent=2, ensure_ascii=False)}")

        # 获取学习摘要
        summary = engine.get_learning_summary()
        print(f"\nLearning Summary: {json.dumps(summary, indent=2, ensure_ascii=False)}")

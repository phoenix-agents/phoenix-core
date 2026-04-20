#!/usr/bin/env python3
"""
Phoenix Core - Skill Executor (技能执行器)

职责：
1. 加载可执行技能（Python 文件）
2. 执行技能并返回结果
3. 支持 SKILL.md 格式的技能定义

Usage:
    executor = SkillExecutor()
    result = await executor.execute("Sandbox Execution", {"command": "ls -la"})
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SkillDefinition:
    """技能定义"""
    name: str
    description: str
    triggers: List[str]
    steps: List[str]
    examples: List[str]
    source_file: Path


class SkillExecutor:
    """技能执行器"""

    def __init__(self, skills_dir: str = None):
        """
        初始化技能执行器

        Args:
            skills_dir: 技能目录路径
        """
        if skills_dir:
            self.skills_dir = Path(skills_dir)
        else:
            self.skills_dir = Path("/Users/wangsai/phoenix-core/skills")

        self._loaded_skills: Dict[str, SkillDefinition] = {}
        self._executors: Dict[str, Callable] = {}

        self._load_skills()
        self._load_python_executors()

    def _load_skills(self):
        """从 SKILL.md 加载技能定义"""
        skill_file = self.skills_dir / "SKILL.md"
        if not skill_file.exists():
            logger.warning(f"SKILL.md 不存在：{skill_file}")
            return

        content = skill_file.read_text(encoding="utf-8")

        # 解析 SKILL.md 格式
        sections = content.split("§\n")

        for section in sections:
            if not section.strip():
                continue

            skill = self._parse_skill_section(section.strip())
            if skill:
                # 使用最新的技能定义（允许覆盖）
                self._loaded_skills[skill.name] = skill

        logger.info(f"已加载 {len(self._loaded_skills)} 个技能定义")

    def _parse_skill_section(self, section: str) -> Optional[SkillDefinition]:
        """解析单个技能段落"""
        lines = section.split("\n")

        name = None
        description = ""
        triggers = []
        steps = []
        examples = []

        for line in lines:
            line = line.strip()

            if line.startswith("[SKILL]"):
                # 提取技能名称
                match = re.match(r'\[SKILL\]\s*(.+?)(?:\n|$)', line)
                if match:
                    name = match.group(1).strip()

            elif line.startswith("Description:"):
                description = line.replace("Description:", "").strip()

            elif line.startswith("Triggers:"):
                trigger_text = line.replace("Triggers:", "").strip()
                # 支持逗号分隔或列表格式
                if "," in trigger_text:
                    triggers = [t.strip() for t in trigger_text.split(",")]
                else:
                    triggers = [trigger_text]

            elif line.startswith("Steps:"):
                steps_text = line.replace("Steps:", "").strip()
                # 支持列表格式或字符串格式
                if steps_text.startswith("[") and steps_text.endswith("]"):
                    try:
                        steps = json.loads(steps_text)
                    except json.JSONDecodeError:
                        # JSON 解析失败，按逗号分隔
                        steps = [s.strip().strip('"').strip("'") for s in steps_text[1:-1].split(",")]
                else:
                    # 按句号分割步骤
                    steps = [s.strip() for s in steps_text.split(".") if s.strip()]

            elif line.startswith("Examples:"):
                examples_text = line.replace("Examples:", "").strip()
                if examples_text.startswith("[") and examples_text.endswith("]"):
                    try:
                        examples = json.loads(examples_text)
                    except json.JSONDecodeError:
                        # JSON 解析失败，按逗号分隔
                        examples = [e.strip().strip('"').strip("'") for e in examples_text[1:-1].split(",")]
                else:
                    examples = [examples_text]

        if name:
            return SkillDefinition(
                name=name,
                description=description,
                triggers=triggers,
                steps=steps,
                examples=examples,
                source_file=self.skills_dir / "SKILL.md"
            )

        return None

    def _load_python_executors(self):
        """加载 Python 技能执行器"""
        # 查找 skills 目录下的 Python 文件
        if not self.skills_dir.exists():
            return

        for py_file in self.skills_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            try:
                # 动态导入 Python 技能模块
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    py_file.stem, py_file
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # 查找 execute 函数
                if hasattr(module, "execute"):
                    self._executors[py_file.stem] = module.execute
                    logger.info(f"已加载 Python 技能执行器：{py_file.stem}")

            except Exception as e:
                logger.warning(f"加载 Python 技能失败 {py_file.name}: {e}")

    def get_skill_definition(self, skill_name: str) -> Optional[SkillDefinition]:
        """获取技能定义"""
        return self._loaded_skills.get(skill_name)

    def find_skill_by_trigger(self, trigger: str) -> Optional[str]:
        """根据触发词查找技能"""
        trigger_lower = trigger.lower()

        for name, skill in self._loaded_skills.items():
            for t in skill.triggers:
                if t.lower() in trigger_lower:
                    return name

        return None

    async def execute(self, skill_name: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        执行技能

        Args:
            skill_name: 技能名称
            context: 执行上下文（参数）

        Returns:
            执行结果
        """
        context = context or {}

        # Step 1: 查找技能定义
        skill = self.get_skill_definition(skill_name)
        if not skill:
            # 尝试直接执行 Python 技能
            if skill_name in self._executors:
                try:
                    result = await self._executors[skill_name](context)
                    return {"success": True, "result": result}
                except Exception as e:
                    logger.error(f"技能执行失败 {skill_name}: {e}")
                    return {"success": False, "error": str(e)}

            return {
                "success": False,
                "error": f"技能未找到：{skill_name}"
            }

        # Step 2: 执行技能步骤
        logger.info(f"执行技能：{skill_name}")
        logger.info(f"步骤：{skill.steps[:3]}...")  # 只记录前 3 个步骤

        # 简单版本：返回技能定义，由调用者（LLM）来解释执行
        # 复杂版本：可以解析步骤并自动执行
        return {
            "success": True,
            "skill_name": skill.name,
            "description": skill.description,
            "steps": skill.steps,
            "suggested_action": f"请按照以下步骤执行：{skill.steps}"
        }

    def get_all_skills(self) -> List[Dict]:
        """获取所有已加载的技能"""
        return [
            {
                "name": skill.name,
                "description": skill.description,
                "triggers": skill.triggers,
                "source": str(skill.source_file)
            }
            for skill in self._loaded_skills.values()
        ]


# 全局实例
_executor: Optional[SkillExecutor] = None


def get_executor(skills_dir: str = None) -> SkillExecutor:
    """获取全局 SkillExecutor 实例"""
    global _executor
    if _executor is None:
        _executor = SkillExecutor(skills_dir)
    return _executor


async def execute_skill(skill_name: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """便捷函数：执行技能"""
    return await get_executor().execute(skill_name, context)


def find_skill_for_task(task_description: str) -> Optional[str]:
    """便捷函数：为任务匹配技能"""
    return get_executor().find_skill_by_trigger(task_description)

#!/usr/bin/env python3
"""
Skill Loader - 通用技能加载和执行系统

功能:
1. 自动发现已安装的技能
2. 解析 SKILL.md 文件提取技能信息
3. 动态加载技能函数
4. 提供统一的技能调用接口

Usage:
    from skill_loader import SkillLoader
    loader = SkillLoader("场控")
    skills = loader.get_available_skills()
    result = loader.execute_skill("create_word_doc", title="标题", content="内容")
"""

import importlib
import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable

logger = logging.getLogger(__name__)


class SkillLoader:
    """技能加载器和执行器"""

    def __init__(self, bot_name: str, skills_dir: str = None, shared_skills_dir: str = None):
        self.bot_name = bot_name

        # Bot's own skills directory
        self.skills_dir = Path(skills_dir) if skills_dir else Path(f"workspaces/{bot_name}/DYNAMIC/skills")
        self.skills_dir.mkdir(parents=True, exist_ok=True)

        # Shared skills directory (all bots can use)
        self.shared_skills_dir = Path(shared_skills_dir) if shared_skills_dir else Path(__file__).parent / "skills"

        # Skill registry - maps skill names to their metadata and functions
        self.skills: Dict[str, Dict[str, Any]] = {}

        # Load skills from both directories
        self._load_all_skills()

    def _load_all_skills(self):
        """Load skills from both bot's own directory and shared directory."""
        # Load shared skills first (lower priority)
        if self.shared_skills_dir.exists():
            self._load_skills_from_dir(self.shared_skills_dir)

        # Load bot's own skills (higher priority - can override shared skills)
        if self.skills_dir.exists():
            self._load_skills_from_dir(self.skills_dir)

        logger.info(f"[{self.bot_name}] Loaded {len(self.skills)} skills")

    def _load_skills_from_dir(self, skills_dir: Path):
        """Load all skills from a directory - supports both directory and single-file formats."""
        for item in skills_dir.iterdir():
            # Skip README and other non-skill files
            if item.name in ["README.md", "INSTALL.md"]:
                continue

            # Format 1: Directory format (skill_name/SKILL.md) - for installed skills
            if item.is_dir():
                skill_md = item / "SKILL.md"
                if skill_md.exists():
                    self._parse_skill_md(item, skill_md)
                else:
                    # Check for Python skill module
                    py_module = item / "skill.py"
                    if py_module.exists():
                        self._load_python_skill(item, py_module)

            # Format 2: Single file format (skill_name.md or skill_timestamp.md) - for bot-generated skills
            elif item.suffix == ".md" and item.stem != "SKILL":
                self._load_single_file_skill(item)

    def _parse_skill_md(self, skill_dir: Path, skill_md: Path):
        """Parse SKILL.md file to extract skill metadata."""
        content = skill_md.read_text(encoding='utf-8')

        # Extract skill name from directory name
        skill_name = skill_dir.name

        # Extract usage patterns from SKILL.md
        usage_patterns = self._extract_usage_patterns(content)

        # Extract function signatures if documented
        functions = self._extract_functions(content)

        # Register skill
        self.skills[skill_name] = {
            "name": skill_name,
            "path": str(skill_dir),
            "content": content,
            "usage_patterns": usage_patterns,
            "functions": functions,
            "source": "shared" if "shared" in str(skill_dir) else "bot"
        }

        logger.debug(f"[{self.bot_name}] Loaded skill: {skill_name}")

    def _load_single_file_skill(self, skill_file: Path):
        """Load a single-file skill (bot-generated learning)."""
        try:
            content = skill_file.read_text(encoding='utf-8')

            # Use filename as skill name (without .md extension)
            skill_name = skill_file.stem

            # Register skill
            self.skills[skill_name] = {
                "name": skill_name,
                "path": str(skill_file),
                "content": content,
                "usage_patterns": [],
                "functions": [],
                "source": "bot-generated",
                "format": "single-file"
            }

            logger.debug(f"[{self.bot_name}] Loaded single-file skill: {skill_name}")

        except Exception as e:
            logger.warning(f"[{self.bot_name}] Failed to load single-file skill {skill_file.name}: {e}")

    def _extract_usage_patterns(self, content: str) -> List[str]:
        """Extract usage patterns from SKILL.md content."""
        patterns = []

        # Look for usage examples
        usage_sections = re.findall(r'## 使用方法.*?(?=##|\Z)', content, re.DOTALL)
        for section in usage_sections:
            # Extract code examples
            examples = re.findall(r'```(?:python|bash|text)?\n(.*?)```', section, re.DOTALL)
            patterns.extend(examples)

            # Extract natural language examples
            nl_examples = re.findall(r'@[\w]+\s+.*?(?=\n|\Z)', section)
            patterns.extend(nl_examples)

        return patterns

    def _extract_functions(self, content: str) -> List[Dict[str, Any]]:
        """Extract documented function signatures."""
        functions = []

        # Look for Python code blocks with function definitions
        func_defs = re.findall(r'def\s+(\w+)\(([^)]*)\)\s*(?:->\s*([\w\[\],\s]+))?:', content)
        for func_name, params, return_type in func_defs:
            functions.append({
                "name": func_name,
                "params": params,
                "return_type": return_type or "Any"
            })

        return functions

    def _load_python_skill(self, skill_dir: Path, py_module: Path):
        """Load a Python skill module."""
        try:
            # Add skill directory to Python path
            sys.path.insert(0, str(skill_dir))

            # Import the module
            spec = importlib.util.spec_from_file_location(f"skill_{skill_dir.name}", py_module)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Look for skill class or functions
            skill_name = skill_dir.name

            # Register skill
            self.skills[skill_name] = {
                "name": skill_name,
                "path": str(skill_dir),
                "module": module,
                "source": "python"
            }

            logger.debug(f"[{self.bot_name}] Loaded Python skill: {skill_name}")

        except Exception as e:
            logger.warning(f"[{self.bot_name}] Failed to load Python skill {skill_dir.name}: {e}")

    def get_available_skills(self) -> List[Dict[str, Any]]:
        """Get list of available skills."""
        return list(self.skills.values())

    def has_skill(self, skill_name: str) -> bool:
        """Check if a skill is available."""
        return skill_name in self.skills

    def get_skill_info(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed info about a skill."""
        return self.skills.get(skill_name)

    def execute_skill(self, skill_name: str, **kwargs) -> Any:
        """Execute a skill with given parameters."""
        if skill_name not in self.skills:
            raise ValueError(f"Skill not found: {skill_name}")

        skill = self.skills[skill_name]
        skill_format = skill.get("format", "directory")

        # Single-file skills (bot-generated learnings) are knowledge, not executable
        if skill_format == "single-file":
            logger.info(f"[{self.bot_name}] Skill {skill_name} is knowledge reference, not executable")
            return f"📚 技能 '{skill_name}' 是知识点，可在执行时参考内容"

        # Handle Python module skills
        if "module" in skill:
            module = skill["module"]
            # Look for main function or class
            if hasattr(module, "execute"):
                return module.execute(**kwargs)
            elif hasattr(module, "main"):
                return module.main(**kwargs)
            else:
                # Look for skill-specific functions
                for attr_name in dir(module):
                    if attr_name.startswith(skill_name.replace("-", "_")):
                        func = getattr(module, attr_name)
                        if callable(func):
                            return func(**kwargs)

        # Handle documented skills (need to import actual implementation)
        if "content" in skill:
            # For pls-office-docs, import office_skill module
            if skill_name == "pls-office-docs":
                return self._execute_office_skill(**kwargs)

        raise NotImplementedError(f"Skill execution not implemented for: {skill_name}")

    def _execute_office_skill(self, **kwargs) -> Any:
        """Execute Office skill - wrapper around office_skill.py."""
        # Import the office skill module
        from office_skill import OfficeSkill

        skill = OfficeSkill()

        # Map kwargs to skill methods
        action = kwargs.get("action", "")

        if "create_word" in action or "create_word_document" in action:
            return skill.create_word_document(
                title=kwargs.get("title", "Document"),
                content=kwargs.get("content", ""),
                filename=kwargs.get("filename")
            )

        elif "create_pdf" in action or "create_pdf_document" in action:
            # PDF 创建需要先生成 Word，再转换
            word_filepath = kwargs.get("word_filepath", "")
            if word_filepath and Path(word_filepath).exists():
                return skill.create_pdf_from_word(
                    word_filepath=word_filepath,
                    output_filename=kwargs.get("filename")
                )
            else:
                # 如果没有 Word 文件，先创建 Word 再转 PDF
                word_doc = skill.create_word_document(
                    title=kwargs.get("title", "Document"),
                    content=kwargs.get("content", ""),
                    filename=kwargs.get("temp_word_file", "temp.docx")
                )
                return skill.create_pdf_from_word(
                    word_filepath=word_doc,
                    output_filename=kwargs.get("filename")
                )

        elif "read_word" in action or "read_word_document" in action:
            return skill.read_word_document(kwargs.get("filepath", ""))

        elif "create_excel" in action or "create_excel_sheet" in action:
            return skill.create_excel_sheet(
                data=kwargs.get("data", []),
                headers=kwargs.get("headers"),
                filename=kwargs.get("filename")
            )

        elif "read_excel" in action or "read_excel_sheet" in action:
            return skill.read_excel_sheet(
                filepath=kwargs.get("filepath", ""),
                sheet_name=kwargs.get("sheet_name")
            )

        elif "create_ppt" in action or "create_ppt_presentation" in action:
            return skill.create_ppt_presentation(
                slides=kwargs.get("slides", []),
                filename=kwargs.get("filename")
            )

        elif "read_pdf" in action:
            return skill.read_pdf(kwargs.get("filepath", ""))

        elif "merge_pdf" in action or "merge_pdfs" in action:
            return skill.merge_pdfs(
                pdf_files=kwargs.get("pdf_files", []),
                output_filename=kwargs.get("output_filename")
            )

        raise ValueError(f"Unknown Office skill action: {action}")


class SkillExecutor:
    """
    Skill Executor - parses LLM responses and executes skills

    This class integrates with phoenix_core_gateway.py to handle
    tool calls in the format:
    - <tool_name>skill_name</tool_name><args>...</args>
    - <invoke name="skill_name">...</invoke>
    """

    def __init__(self, skill_loader: SkillLoader):
        self.skill_loader = skill_loader
        self.bot_name = skill_loader.bot_name

    def parse_and_execute(self, response: str) -> Optional[str]:
        """
        Parse LLM response and execute skill if found.

        Returns the skill execution result, or None if no skill was called.
        """
        # Pattern 1: <tool_name>skill_name</tool_name><args>...</args>
        tool_match = re.search(r'<tool_name>([\w-]+)</tool_name>.*?<args>(.*?)</args>', response, re.DOTALL)
        if tool_match:
            skill_name = tool_match.group(1)
            args_text = tool_match.group(2)
            return self._execute_skill_by_name(skill_name, args_text)

        # Pattern 2: <invoke name="skill_name">...</invoke>
        invoke_match = re.search(r'<invoke[^>]*name="([\w-]+)"[^>]*>(.*?)</invoke>', response, re.DOTALL)
        if invoke_match:
            skill_name = invoke_match.group(1)
            body = invoke_match.group(2)
            return self._execute_skill_by_name(skill_name, body)

        return None

    def _execute_skill_by_name(self, skill_name: str, args_text: str) -> Optional[str]:
        """Execute a skill by name, parsing arguments from text."""
        # Normalize skill name
        skill_name = skill_name.strip()

        # Map TOOLS.md tool names to skill names
        tool_to_skill_map = {
            "create_word_doc": "pls-office-docs",
            "create_excel_sheet": "pls-office-docs",
            "create_ppt": "pls-office-docs",
            "create_pdf": "pls-office-docs",
            "read_pdf": "pls-office-docs",
        }

        actual_skill = tool_to_skill_map.get(skill_name, skill_name)

        if not self.skill_loader.has_skill(actual_skill):
            logger.warning(f"[{self.bot_name}] Skill not found: {actual_skill} (requested as {skill_name})")
            return None

        # Parse arguments
        kwargs = self._parse_args(skill_name, args_text)

        try:
            result = self.skill_loader.execute_skill(actual_skill, **kwargs)
            return f"✅ 技能已执行：{skill_name}\n结果：{result}"
        except Exception as e:
            logger.error(f"[{self.bot_name}] Skill execution failed: {e}")
            return f"❌ 技能执行失败：{e}"

    def _parse_args(self, skill_name: str, args_text: str) -> Dict[str, Any]:
        """Parse arguments from tool call text."""
        kwargs = {}
        args_text = args_text.strip()

        # Parse key: value pairs (handles multi-line content)
        current_key = None
        current_value = []

        for line in args_text.split("\n"):
            line = line.strip()
            if not line:
                continue

            # Check if this is a new key: value pair
            if ":" in line and not line.startswith(" ") and not line.startswith("\t"):
                # Save previous key-value if exists
                if current_key:
                    kwargs[current_key] = "\n".join(current_value).strip()

                # Parse new key-value
                key, value = line.split(":", 1)
                current_key = key.strip()
                current_value = [value.strip()]
            else:
                # Continuation of previous value
                if current_key:
                    current_value.append(line)

        # Save last key-value
        if current_key:
            kwargs[current_key] = "\n".join(current_value).strip()

        # Handle special cases - map tool names to skill actions
        if skill_name == "create_word_doc":
            kwargs["action"] = "create_word_document"
        elif skill_name == "create_excel_sheet":
            kwargs["action"] = "create_excel_sheet"
            # Parse headers as list
            if "headers" in kwargs:
                kwargs["headers"] = [h.strip() for h in kwargs["headers"].split(",")]
            # Parse data as list of lists
            if "data" in kwargs:
                data_rows = kwargs["data"].split(";")
                kwargs["data"] = [[cell.strip() for cell in row.split(",")] for row in data_rows]
        elif skill_name == "create_ppt":
            kwargs["action"] = "create_ppt_presentation"
            # Parse slides: "title1|content1; title2|content2"
            if "slides" in kwargs:
                slides_data = []
                for slide_text in kwargs["slides"].split(";"):
                    if "|" in slide_text:
                        title, content = slide_text.split("|", 1)
                        slides_data.append({"title": title.strip(), "content": content.strip()})
                kwargs["slides"] = slides_data

        return kwargs


# Convenience function for gateway integration
def get_skill_loader(bot_name: str) -> SkillLoader:
    """Get a skill loader for a specific bot."""
    return SkillLoader(bot_name)


if __name__ == "__main__":
    # Test skill loader
    logging.basicConfig(level=logging.DEBUG)

    loader = SkillLoader("场控")
    print(f"Loaded {len(loader.skills)} skills")

    for skill_name, skill_info in loader.skills.items():
        print(f"  - {skill_name} ({skill_info.get('source', 'unknown')})")

    # Test skill execution
    if loader.has_skill("pls-office-docs"):
        result = loader.execute_skill(
            "pls-office-docs",
            action="create_word_document",
            title="测试文档",
            content="这是测试内容",
            filename="test_skill_loader.docx"
        )
        print(f"Office skill result: {result}")

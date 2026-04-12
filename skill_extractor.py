#!/usr/bin/env python3
"""
Automatic Skill Extraction - Convert Evaluated Tasks to Skills

This module automatically extracts skills from tasks that have been
evaluated as worth preserving. It converts task steps into reusable
skill format and writes them to SKILL.md.

Key Features:
1. Auto-extraction from evaluated tasks
2. Skill format standardization
3. AI-powered skill refinement
4. Duplicate detection and merging

Usage:
    extractor = SkillExtractor(memory_manager)

    # After task evaluation says "preserve"
    if evaluation.worth_preserving:
        extractor.extract_skill(evaluation)
"""

import json
import logging
import os
import urllib.request
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Coding Plan API config
CODING_PLAN_CONFIG = {
    "base_url": "https://coding.dashscope.aliyuncs.com/v1",
    "api_key": os.environ.get("CODING_PLAN_API_KEY"),  # 从环境变量读取
    "model": "qwen3-coder-next",
    "max_tokens": 2000,
    "temperature": 0.2
}


class SkillExtractor:
    """
    Extracts skills from evaluated tasks.

    Process:
    1. Receive evaluated task (marked as worth preserving)
    2. Optionally refine with AI
    3. Format as skill entry
    4. Write to SKILL.md
    """

    def __init__(self, memory_manager=None):
        self._memory_manager = memory_manager
        self._api_config = CODING_PLAN_CONFIG
        self._extraction_count = 0
        self._extraction_history = []

    def extract_skill(self, evaluation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract a skill from an evaluated task.

        Args:
            evaluation: Task evaluation result (with worth_preserving=True)

        Returns:
            Extraction result with skill content and status
        """
        if not evaluation.get('worth_preserving'):
            return {
                "success": False,
                "error": "Task not worth preserving",
                "evaluation": evaluation
            }

        task_type = evaluation.get('task_type', 'unknown')
        steps = evaluation.get('steps_taken', [])
        reasoning = evaluation.get('reasoning', '')

        # Generate skill content
        skill = self._generate_skill_content(task_type, steps, reasoning)

        # Optionally refine with AI
        refined_skill = self._refine_with_ai(skill)
        if refined_skill:
            skill = refined_skill

        # Check for duplicates
        if self._is_duplicate(skill):
            return {
                "success": False,
                "error": "Duplicate skill",
                "existing": skill
            }

        # Write to SKILL.md
        result = self._write_skill(skill)

        if result.get('success'):
            self._extraction_count += 1
            self._extraction_history.append({
                "task_type": task_type,
                "skill_name": skill.get('name', 'Unknown'),
                "extracted_at": datetime.now().isoformat()
            })
            logger.info(f"Skill extracted: {skill.get('name')}")

        return {
            "success": result.get('success', False),
            "skill": skill,
            "result": result
        }

    def _generate_skill_content(
        self,
        task_type: str,
        steps: List[str],
        reasoning: str
    ) -> Dict[str, Any]:
        """
        Generate skill content from task evaluation.

        Args:
            task_type: Type of task
            steps: Steps taken to complete task
            reasoning: Evaluation reasoning

        Returns:
            Skill dictionary
        """
        # Generate name from task type
        name = self._generate_skill_name(task_type)

        # Generate description
        description = self._generate_description(task_type, steps)

        # Extract triggers from task type
        triggers = self._generate_triggers(task_type)

        # Format steps
        formatted_steps = self._format_steps(steps)

        # Generate examples
        examples = self._generate_examples(task_type, steps)

        return {
            "name": name,
            "description": description,
            "triggers": triggers,
            "steps": formatted_steps,
            "examples": examples,
            "source": "auto_extracted",
            "task_type": task_type
        }

    def _generate_skill_name(self, task_type: str) -> str:
        """Generate a skill name from task type."""
        # Convert snake_case to Title Case
        name = task_type.replace('_', ' ').title()

        # Add "Skill" suffix if not present
        if 'Skill' not in name and 'Procedure' not in name:
            name += " Procedure"

        return name

    def _generate_description(
        self,
        task_type: str,
        steps: List[str]
    ) -> str:
        """Generate a one-sentence description."""
        # Map common task types to descriptions
        descriptions = {
            "memory_configuration": "Configures memory system for new sessions",
            "memory_config": "Configures memory system settings",
            "changkong_setup": "Sets up Changkong field control bot for live monitoring",
            "changkong_config": "Configures Changkong bot parameters",
            "bot_configuration": "Configures bot settings and parameters",
            "api_integration": "Integrates with external API services",
            "debugging": "Systematic debugging and troubleshooting process",
            "database_migration": "Migrates database with minimal downtime",
            "server_setup": "Sets up and configures server environment",
        }

        task_lower = task_type.lower()
        for key, desc in descriptions.items():
            if key in task_lower:
                return desc

        # Generic description
        return f"Handles {task_type.replace('_', ' ')} tasks"

    def _generate_triggers(self, task_type: str) -> str:
        """Generate trigger conditions from task type."""
        triggers = {
            "memory": "User asks about memory, configuration, or session setup",
            "changkong": "User mentions Changkong, field control, or live monitoring",
            "bot": "User asks about bot setup or configuration",
            "api": "User needs API integration or external service connection",
            "debug": "User encounters errors or needs troubleshooting",
            "database": "User needs database operations or migration",
            "server": "User needs server setup or deployment",
        }

        for key, trigger in triggers.items():
            if key in task_type.lower():
                return trigger

        return f"When user requests {task_type.replace('_', ' ')}"

    def _format_steps(self, steps: List[str]) -> str:
        """Format steps as a numbered procedure."""
        if not steps:
            return "Follow standard procedure for this task type"

        # Clean and number steps
        cleaned = []
        for i, step in enumerate(steps, 1):
            step = step.strip()
            # Remove leading numbers if present
            step = re.sub(r'^\d+[\.\)]\s*', '', step)
            # Capitalize first letter
            step = step[0].upper() + step[1:] if step else step
            cleaned.append(f"{i}. {step}")

        return ". ".join(cleaned)

    def _generate_examples(
        self,
        task_type: str,
        steps: List[str]
    ) -> str:
        """Generate example use cases."""
        examples = {
            "memory": "Setting up memory for new agent sessions; Troubleshooting memory issues",
            "changkong": "Deploying field control bot; Configuring live data monitoring",
            "bot": "Setting up new bot instances; Reconfiguring existing bots",
            "api": "Integrating with third-party services; Setting up webhooks",
            "debug": "Diagnosing connection issues; Fixing configuration errors",
            "database": "Migrating to new schema; Backing up and restoring data",
            "server": "Deploying to production; Setting up development environment",
        }

        for key, example in examples.items():
            if key in task_type.lower():
                return example

        return f"Standard {task_type.replace('_', ' ')} scenarios"

    def _refine_with_ai(self, skill: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Use AI to refine skill content.

        Args:
            skill: Raw skill dictionary

        Returns:
            Refined skill or None if AI fails
        """
        prompt = f"""Refine this skill for clarity and reusability. Output JSON only.

Skill:
{json.dumps(skill, indent=2)}

Improve:
1. Make description concise (1 sentence)
2. Make triggers clear and actionable
3. Format steps as clear numbered procedure
4. Make examples specific

Return refined skill JSON."""

        request_data = {
            "model": self._api_config["model"],
            "messages": [
                {"role": "system", "content": "Output valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            "temperature": self._api_config["temperature"],
            "max_tokens": self._api_config["max_tokens"],
            "response_format": {"type": "json_object"}
        }

        url = f"{self._api_config['base_url']}/chat/completions"

        req = urllib.request.Request(
            url,
            data=json.dumps(request_data).encode('utf-8'),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_config['api_key']}"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                content = result["choices"][0]["message"]["content"]

                # Parse JSON response
                content = content.strip()
                if content.startswith('```'):
                    content = content.split('```')[1]
                    if content.startswith('json'):
                        content = content[4:]
                content = content.strip()

                refined = json.loads(content)

                # Merge with original
                skill['description'] = refined.get('description', skill['description'])
                skill['triggers'] = refined.get('triggers', skill['triggers'])
                skill['steps'] = refined.get('steps', skill['steps'])
                skill['examples'] = refined.get('examples', skill['examples'])

                logger.info(f"AI refinement complete for {skill['name']}")
                return skill

        except Exception as e:
            logger.warning(f"AI refinement failed: {e}, using raw skill")
            return None

    def _is_duplicate(self, skill: Dict[str, Any]) -> bool:
        """
        Check if this skill already exists.

        Args:
            skill: Skill dictionary

        Returns:
            True if duplicate exists
        """
        if not self._memory_manager:
            return False

        # Get existing skills
        result = self._memory_manager._skill_store.read()
        existing = result.get('entries', [])

        # Check for similar names
        skill_name = skill.get('name', '').lower()
        for entry in existing:
            if skill_name in entry.lower():
                return True

        return False

    def _write_skill(self, skill: Dict[str, Any]) -> Dict[str, Any]:
        """
        Write skill to SKILL.md via MemoryManager.

        Args:
            skill: Skill dictionary

        Returns:
            Write result
        """
        if not self._memory_manager:
            return {"success": False, "error": "No memory manager"}

        # Format for storage
        skill_content = f"""[SKILL] {skill['name']}
Description: {skill['description']}
Triggers: {skill['triggers']}
Steps: {skill['steps']}
Examples: {skill['examples']}"""

        # Write via manager
        result = self._memory_manager.add_skill(skill_content)

        return {
            "success": result,
            "skill_content": skill_content
        }

    def get_status(self) -> Dict[str, Any]:
        """Get extractor status."""
        return {
            "extractions_total": self._extraction_count,
            "extractions_history": self._extraction_history[-10:],  # Last 10
        }

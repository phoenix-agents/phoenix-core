#!/usr/bin/env python3
"""
Background Review Agent - Phoenix Core-style Learning Review

This module implements a background agent that:
1. Spawns when learning threshold is exceeded
2. Analyzes conversation for skill creation opportunities
3. Creates or updates skills in SKILL.md
4. Runs asynchronously to avoid blocking main conversation

Usage:
    from background_review import BackgroundReviewAgent

    agent = BackgroundReviewAgent(memory_manager)
    agent.spawn_review(user_content, assistant_content, conversation_buffer)
"""

import json
import logging
import os
import threading
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Coding Plan API config (same as automatic_learner)
CODING_PLAN_CONFIG = {
    "base_url": "https://coding.dashscope.aliyuncs.com/v1",
    "api_key": os.environ.get("DASHSCOPE_API_KEY"),
    "model": "qwen3-coder-next",
    "max_tokens": 2000,
    "temperature": 0.2
}


class BackgroundReviewAgent:
    """
    Background agent for reviewing conversations and creating skills.

    Features:
    1. Non-blocking background execution
    2. AI-powered skill extraction
    3. Automatic skill creation/update
    4. Logging and error handling
    """

    def __init__(self, memory_manager=None):
        self._memory_manager = memory_manager
        self._api_config = CODING_PLAN_CONFIG
        self._is_processing = False
        self._review_queue = []

    def spawn_review(self, user_content: str, assistant_content: str,
                     conversation_buffer: List[Dict] = None):
        """
        Spawn a background review task.

        Args:
            user_content: The user's message that triggered the review
            assistant_content: The assistant's response
            conversation_buffer: Full conversation history (optional)
        """
        if self._is_processing:
            # Queue for later
            self._review_queue.append({
                "user_content": user_content,
                "assistant_content": assistant_content,
                "conversation_buffer": conversation_buffer,
                "timestamp": datetime.now().isoformat()
            })
            logger.info(f"Review queued (processing in progress), queue size: {len(self._review_queue)}")
            return

        # Spawn background thread
        thread = threading.Thread(
            target=self._run_review,
            args=(user_content, assistant_content, conversation_buffer)
        )
        thread.daemon = True
        thread.start()
        logger.info("Background review spawned")

    def _run_review(self, user_content: str, assistant_content: str,
                    conversation_buffer: List[Dict] = None):
        """
        Run the review process in background.

        Args:
            user_content: User's message
            assistant_content: Assistant's response
            conversation_buffer: Full conversation history
        """
        self._is_processing = True

        try:
            # Format conversation for analysis
            if conversation_buffer:
                conversation_text = self._format_conversation(conversation_buffer)
            else:
                conversation_text = f"User: {user_content}\n\nAssistant: {assistant_content}"

            # Call AI for skill extraction
            skills = self._extract_skills(conversation_text)

            if skills:
                # Write skills to SKILL.md
                for skill in skills:
                    self._write_skill(skill)

                logger.info(f"Background review complete: {len(skills)} skills created/updated")
            else:
                logger.info("Background review complete: No skills extracted")

        except Exception as e:
            logger.error(f"Background review failed: {e}")
        finally:
            self._is_processing = False

            # Process queued reviews
            if self._review_queue:
                next_review = self._review_queue.pop(0)
                self._run_review(
                    next_review["user_content"],
                    next_review["assistant_content"],
                    next_review.get("conversation_buffer")
                )

    def _format_conversation(self, buffer: List[Dict]) -> str:
        """Format conversation buffer as text for AI analysis."""
        lines = []
        for msg in buffer[-10:]:  # Last 10 messages
            role = "User" if msg["role"] == "user" else "Assistant"
            content = msg["content"][:500]  # Truncate
            lines.append(f"{role}: {content}")
        return "\n\n".join(lines)

    def _extract_skills(self, conversation: str) -> List[Dict[str, Any]]:
        """
        Extract skills from conversation using AI.

        Args:
            conversation: Formatted conversation text

        Returns:
            List of skill dictionaries
        """
        prompt = f"""You are a skill extraction specialist. Analyze this conversation and extract reusable skills.

A skill is a reusable pattern, workflow, or procedure that can be applied to similar situations in the future.

Conversation:
{conversation[:2000]}

Extract skills in this JSON format:
{{
  "skills": [
    {{
      "name": "ShortSkillName",
      "description": "What this skill does in 1 sentence",
      "triggers": "When to apply this skill",
      "steps": "Step 1. Step 2. Step 3.",
      "examples": "Example use cases"
    }}
  ]
}}

Only extract skills if you see clear reusable patterns. Return empty array if none found."""

        logger.info("Calling AI for skill extraction...")

        request_data = {
            "model": self._api_config["model"],
            "messages": [
                {"role": "system", "content": "Output valid JSON only. No explanations."},
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
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode('utf-8'))
                content = result["choices"][0]["message"]["content"]
                logger.info(f"Skill extraction success, tokens: {result.get('usage', {})}")

                # Clean and parse JSON
                content = content.strip()
                if content.startswith('```'):
                    content = content.split('```')[1]
                    if content.startswith('json'):
                        content = content[4:]
                content = content.strip()

                # Remove control characters
                import re
                content = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', content)

                # Extract closing brace if truncated
                if '{' in content:
                    last_brace = content.rfind('}')
                    if last_brace > 0:
                        content = content[:last_brace+1]

                try:
                    data = json.loads(content)
                    skills = data.get('skills', [])
                    logger.info(f"Extracted {len(skills)} skills")
                    return skills
                except json.JSONDecodeError as e:
                    logger.error(f"JSON parse failed: {e}")
                    logger.error(f"Content: {content[:200]}")
                    return []

        except urllib.error.HTTPError as e:
            logger.error(f"AI call HTTP error: {e.code}")
            return []
        except Exception as e:
            logger.error(f"AI call failed: {e}")
            return []

    def _write_skill(self, skill: Dict[str, Any]):
        """
        Write a skill to SKILL.md via MemoryManager.

        Args:
            skill: Skill dictionary with name, description, triggers, steps, examples
        """
        if not self._memory_manager:
            logger.warning("No memory manager, skipping skill write")
            return

        # Format skill for storage
        skill_content = f"""[SKILL] {skill.get('name', 'Unnamed Skill')}
Description: {skill.get('description', 'No description')}
Triggers: {skill.get('triggers', 'N/A')}
Steps: {skill.get('steps', 'N/A')}
Examples: {skill.get('examples', 'N/A')}"""

        try:
            self._memory_manager.add_skill(skill_content)
            logger.info(f"Skill written: {skill.get('name', 'Unknown')}")
        except Exception as e:
            logger.error(f"Failed to write skill: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get background review status."""
        return {
            "is_processing": self._is_processing,
            "queue_size": len(self._review_queue),
        }

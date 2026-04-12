#!/usr/bin/env python3
"""
Automatic Learning and Reflection Module

This module automatically analyzes conversations after a threshold
and extracts reusable patterns, insights, and lessons to memory.

Uses Coding Plan (阿里云通义千问) for AI-powered analysis.
"""

import json
import logging
import threading
import os
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


# Coding Plan (阿里云通义千问) 配置
CODING_PLAN_CONFIG = {
    "base_url": "https://coding.dashscope.aliyuncs.com/v1",
    "api_key": os.environ.get("DASHSCOPE_API_KEY"),
    "model": "qwen3-coder-next",  # 使用 Qwen Coder Next，速度快且稳定
    "max_tokens": 1500,
    "temperature": 0.1
}


class AutomaticLearner:
    """
    Automatically analyzes conversations and extracts learnings.

    Features:
    1. Triggers after N tool iterations
    2. Analyzes conversation for patterns
    3. Extracts reusable knowledge
    4. Writes to MEMORY.md automatically
    """

    def __init__(self, memory_manager=None, learning_threshold=10, use_ai=True):
        self._memory_manager = memory_manager
        self._learning_threshold = learning_threshold
        self._iteration_count = 0
        self._conversation_buffer = []
        self._is_processing = False
        self._use_ai = use_ai  # Use AI-powered analysis
        self._api_config = CODING_PLAN_CONFIG
        self._skill_extraction_enabled = True  # Extract skills from conversations

    def record_interaction(self, user_content: str, assistant_content: str,
                          tool_iterations: int = 1):
        """Record an interaction for potential learning."""
        self._iteration_count += tool_iterations
        self._conversation_buffer.append({
            "role": "user",
            "content": user_content,
            "timestamp": datetime.now().isoformat()
        })
        self._conversation_buffer.append({
            "role": "assistant",
            "content": assistant_content,
            "timestamp": datetime.now().isoformat()
        })

        logger.debug(f"Recorded interaction, total iterations: {self._iteration_count}")

        # Check if learning should trigger
        if self._iteration_count >= self._learning_threshold:
            self._trigger_learning_async()

    def _trigger_learning_async(self):
        """Trigger learning in background thread."""
        if self._is_processing:
            logger.debug("Learning already in progress, skipping")
            return

        thread = threading.Thread(target=self._run_learning_loop)
        thread.daemon = True
        thread.start()
        logger.info("Automatic learning triggered in background")

    def _run_learning_loop(self):
        """Run the learning loop analysis."""
        self._is_processing = True

        try:
            if self._use_ai:
                # Try AI-powered analysis first
                analysis = self._analyze_conversations()
            else:
                # Use simple extraction
                analysis = self._simple_extraction()

            if analysis and analysis.get("learnings"):
                # Extract patterns and write to memory
                for learning in analysis["learnings"]:
                    self._write_learning_to_memory(learning)

                logger.info(f"Learning complete: {len(analysis['learnings'])} insights extracted")

            # Extract skills if enabled
            if self._skill_extraction_enabled and analysis and analysis.get("skills"):
                for skill in analysis["skills"]:
                    self._write_skill_to_memory(skill)

                logger.info(f"Skill extraction complete: {len(analysis.get('skills', []))} skills extracted")

            # Reset counters
            self._iteration_count = 0
            self._conversation_buffer = []

        except Exception as e:
            logger.error(f"Learning loop failed: {e}")
            # Fallback to simple extraction
            try:
                analysis = self._simple_extraction()
                if analysis and analysis.get("learnings"):
                    for learning in analysis["learnings"]:
                        self._write_learning_to_memory(learning)
            except Exception as fallback_error:
                logger.error(f"Fallback extraction also failed: {fallback_error}")
        finally:
            self._is_processing = False

    def _analyze_conversations(self) -> Optional[Dict[str, Any]]:
        """
        Analyze conversation buffer for patterns and learnings.
        """
        if not self._conversation_buffer:
            logger.warning("No conversation buffer to analyze")
            return None

        conversation_text = self._format_conversation()

        # Prompt for AI analysis - extracts both learnings and skills
        prompt = f"""You are a learning assistant. Extract learnings AND reusable skills from this conversation.

Required JSON format:
{{
  "learnings": [{{"title": "ShortTitle", "content": "Key insight in 1-2 sentences", "category": "pattern", "tags": ["auto", "learned"]}}],
  "skills": [{{"name": "SkillName", "description": "What this skill does", "triggers": "When to apply", "steps": "How to execute", "examples": "Sample applications"}}]
}}

Conversation:
{conversation_text[:800]}

Extract at least 1 learning. Skills are optional - only extract if you see reusable patterns."""

        logger.info(f"Calling AI for analysis")
        try:
            analysis = self._call_ai_for_analysis(prompt)
            if analysis:
                learnings = analysis.get('learnings', [])
                logger.info(f"AI analysis returned {len(learnings)} learnings")
                logger.info(f"Raw AI response: {analysis}")
                if not learnings:
                    logger.warning(f"No learnings extracted, response: {analysis}")
                    # Fallback to simple extraction
                    return self._simple_extraction()
            return analysis
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return self._simple_extraction()

    def _call_ai_for_analysis(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call Coding Plan (阿里云通义千问) for analysis."""

        # Simplify prompt for faster response
        simplified_prompt = f"""Extract learnings and reusable skills from this conversation. Output JSON only.

Conversation:
{prompt[:1500]}  # Limit conversation length

JSON format:
{{"learnings": [{{"title": "...", "content": "...", "category": "pattern", "tags": ["..."]}}], "skills": [{{"name": "...", "description": "...", "triggers": "...", "steps": "...", "examples": "..."}}]}}
"""

        request_data = {
            "model": self._api_config["model"],
            "messages": [
                {"role": "system", "content": "Output valid JSON only. No explanations."},
                {"role": "user", "content": simplified_prompt}
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
            # Increase timeout to 60 seconds
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode('utf-8'))
                content = result["choices"][0]["message"]["content"]
                logger.info(f"AI analysis success, tokens: {result.get('usage', {})}")

                # Clean content before parsing
                content = content.strip()

                # Remove markdown code blocks if present
                if content.startswith('```'):
                    content = content.split('```')[1]
                    if content.startswith('json'):
                        content = content[4:]
                content = content.strip()

                # Remove control characters
                import re
                content = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', content)

                # Try to extract only the JSON part if response is truncated
                # Find the last valid } or ]
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    # Try to fix truncated JSON
                    if content.endswith(','):
                        content = content[:-1] + ']}'  # Try closing arrays/objects
                    if '{' in content:
                        # Find last complete object
                        last_brace = content.rfind('}')
                        if last_brace > 0:
                            content = content[:last_brace+1]
                    try:
                        return json.loads(content)
                    except:
                        logger.warning(f"Could not parse JSON, using fallback")
                        return None

        except urllib.error.HTTPError as e:
            logger.error(f"AI call HTTP error: {e.code} - {e.read().decode('utf-8')[:200]}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse failed: {e}")
            logger.error(f"Content was: {content[:200] if 'content' in dir() else 'N/A'}")
            return None
        except Exception as e:
            logger.error(f"AI call failed: {e}")
            return None

        request_data = {
            "model": "coding-plan/qwen3.5-plus",
            "messages": [
                {"role": "system", "content": "You are a learning assistant. Extract insights from conversations."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 2000,
            "response_format": {"type": "json_object"}
        }

        req = urllib.request.Request(
            "http://localhost:18789/v1/chat/completions",
            data=json.dumps(request_data).encode('utf-8'),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                content = result["choices"][0]["message"]["content"]
                return json.loads(content)
        except Exception as e:
            logger.error(f"AI call failed: {e}")
            return None

    def _simple_extraction(self) -> Dict[str, Any]:
        """Simple extraction without AI - extracts patterns from conversation."""
        learnings = []
        patterns = []

        # Analyze conversation for patterns
        user_messages = [m["content"] for m in self._conversation_buffer if m["role"] == "user"]
        assistant_messages = [m["content"] for m in self._conversation_buffer if m["role"] == "assistant"]

        # Extract common topics from user messages
        topic_keywords = ["config", "setup", "how to", "start", "memory", "server", "agent"]
        for msg in user_messages:
            msg_lower = msg.lower()
            for keyword in topic_keywords:
                if keyword in msg_lower:
                    patterns.append(f"User asks about {keyword}")
                    break

        # Extract significant assistant responses
        for i, msg in enumerate(assistant_messages):
            if len(msg) > 50:
                # Create a learning from this response
                learnings.append({
                    "title": f"Response Pattern {i + 1}",
                    "content": msg[:300],
                    "category": "pattern",
                    "tags": ["auto-extracted", f"turn-{i+1}"]
                })

        # Add a summary learning
        if user_messages:
            learnings.append({
                "title": "Conversation Summary",
                "content": f"Processed {len(user_messages)} user interactions",
                "category": "summary",
                "tags": ["auto-extracted"]
            })

        return {
            "learnings": learnings[:5],  # Max 5 learnings
            "patterns": patterns,
            "summary": f"Auto-extracted {len(learnings)} learnings from conversation"
        }

    def _format_conversation(self) -> str:
        """Format conversation buffer as text."""
        lines = []
        for msg in self._conversation_buffer:
            role = msg["role"].upper()
            content = msg["content"][:500]  # Truncate long messages
            lines.append(f"{role}: {content}")
        return "\n\n".join(lines)

    def _write_learning_to_memory(self, learning: Dict[str, Any]):
        """Write a learning to MEMORY.md."""
        if not self._memory_manager:
            logger.warning("No memory manager, skipping learning write")
            return

        # Format learning for memory
        memory_content = (
            f"[LEARNING] {learning['title']}\n"
            f"Category: {learning.get('category', 'general')}\n"
            f"{learning['content']}\n"
            f"Tags: {', '.join(learning.get('tags', []))}\n"
        )

        # Add to memory
        try:
            self._memory_manager.add_memory(memory_content, target="memory")
            logger.info(f"Learning written to memory: {learning['title']}")
        except Exception as e:
            logger.error(f"Failed to write learning: {e}")

    def _write_skill_to_memory(self, skill: Dict[str, Any]):
        """Write a skill to SKILL.md."""
        if not self._memory_manager:
            logger.warning("No memory manager, skipping skill write")
            return

        # Format skill for storage
        skill_content = (
            f"[SKILL] {skill.get('name', 'Unnamed Skill')}\n"
            f"Description: {skill.get('description', 'No description')}\n"
            f"Triggers: {skill.get('triggers', 'N/A')}\n"
            f"Steps: {skill.get('steps', 'N/A')}\n"
            f"Examples: {skill.get('examples', 'N/A')}\n"
        )

        # Add to skill store
        try:
            self._memory_manager.add_skill(skill_content)
            logger.info(f"Skill written to SKILL.md: {skill.get('name', 'Unknown')}")
        except Exception as e:
            logger.error(f"Failed to write skill: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get current learning status."""
        return {
            "iteration_count": self._iteration_count,
            "threshold": self._learning_threshold,
            "is_processing": self._is_processing,
            "buffer_size": len(self._conversation_buffer),
            "progress_percent": round(self._iteration_count / self._learning_threshold * 100)
        }

    def reset(self):
        """Reset learner state."""
        self._iteration_count = 0
        self._conversation_buffer = []
        self._is_processing = False


# Global learner instance
LEARNER = None


def get_learner(memory_manager=None) -> AutomaticLearner:
    """Get or create global learner instance."""
    global LEARNER
    if LEARNER is None:
        LEARNER = AutomaticLearner(memory_manager)
    return LEARNER

#!/usr/bin/env python3
"""
Skill Activation System - Context-aware Skill Recommendation

This module automatically recommends and applies skills based on
conversation context. It matches user input against skill triggers
and suggests relevant skills to the agent.

Features:
1. Trigger matching against user input
2. Skill relevance scoring
3. Context-aware recommendations
4. Automatic skill application
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class SkillActivator:
    """
    Activates skills based on conversation context.

    Usage:
        activator = SkillActivator(memory_manager)
        activator.load_skills()

        # On each user message
        recommendations = activator.recommend_skills(user_content)

        # Apply skill context to response
        if recommendations:
            response = apply_skill_to_response(response, recommendations[0])
    """

    def __init__(self, memory_manager=None):
        self._memory_manager = memory_manager
        self._skills = []
        self._skill_cache = []

    def load_skills(self, force_reload: bool = False) -> List[Dict[str, Any]]:
        """
        Load skills from SKILL.md and parse into structured format.

        Args:
            force_reload: Force reload from disk even if cached

        Returns:
            List of parsed skill dictionaries
        """
        if self._skill_cache and not force_reload:
            return self._skill_cache

        if not self._memory_manager:
            logger.warning("No memory manager, cannot load skills")
            return []

        # Read skills from store
        result = self._memory_manager._skill_store.read()
        raw_skills = result.get('entries', [])

        # Parse raw skills into structured format
        self._skills = []
        for raw in raw_skills:
            skill = self._parse_skill(raw)
            if skill:
                self._skills.append(skill)

        self._skill_cache = self._skills.copy()
        logger.info(f"Loaded {len(self._skills)} skills for activation")
        return self._skills

    def _parse_skill(self, raw: str) -> Optional[Dict[str, Any]]:
        """
        Parse a raw skill entry into structured format.

        Args:
            raw: Raw skill entry string

        Returns:
            Parsed skill dictionary or None if parse fails
        """
        lines = raw.strip().split('\n')
        skill = {
            'name': '',
            'description': '',
            'triggers': '',
            'steps': '',
            'examples': '',
            'raw': raw
        }

        for line in lines:
            line = line.strip()
            if line.startswith('[SKILL]'):
                skill['name'] = line[7:].strip()
            elif line.startswith('Description:'):
                skill['description'] = line[12:].strip()
            elif line.startswith('Triggers:'):
                skill['triggers'] = line[9:].strip()
            elif line.startswith('Steps:'):
                skill['steps'] = line[6:].strip()
            elif line.startswith('Examples:'):
                skill['examples'] = line[9:].strip()

        if not skill['name']:
            return None

        # Extract trigger keywords
        skill['trigger_keywords'] = self._extract_trigger_keywords(skill['triggers'])

        return skill

    def _extract_trigger_keywords(self, triggers: str) -> List[str]:
        """
        Extract keywords from trigger text for matching.

        Args:
            triggers: Trigger description text

        Returns:
            List of lowercase keywords
        """
        # Convert to lowercase and split
        text = triggers.lower()

        # Extract meaningful words (skip common words)
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                      'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                      'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                      'can', 'need', 'to', 'of', 'in', 'for', 'on', 'with', 'at',
                      'by', 'from', 'as', 'into', 'through', 'during', 'before',
                      'after', 'above', 'below', 'between', 'under', 'again',
                      'further', 'then', 'once', 'here', 'there', 'when', 'where',
                      'why', 'how', 'all', 'each', 'few', 'more', 'most', 'other',
                      'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same',
                      'so', 'than', 'too', 'very', 'just', 'and', 'but', 'if', 'or',
                      'because', 'until', 'while', 'about', 'against', 'this',
                      'that', 'these', 'those', 'what', 'which', 'who', 'whom'}

        # Split on common delimiters
        words = re.split(r'[\s,;.\-()]+', text)

        # Filter stop words and short words
        keywords = [w for w in words if w and len(w) > 2 and w not in stop_words]

        return list(set(keywords))

    def recommend_skills(self, user_content: str, threshold: float = 0.3) -> List[Tuple[Dict[str, Any], float]]:
        """
        Recommend skills based on user input.

        Args:
            user_content: The user's message
            threshold: Minimum relevance score (0.0 - 1.0)

        Returns:
            List of (skill, score) tuples sorted by score descending
        """
        if not self._skills:
            self.load_skills()

        if not self._skills:
            return []

        user_input = user_content.lower()
        recommendations = []

        for skill in self._skills:
            score = self._calculate_relevance(user_input, skill)
            if score >= threshold:
                recommendations.append((skill, score))

        # Sort by score descending
        recommendations.sort(key=lambda x: x[1], reverse=True)

        if recommendations:
            logger.info(f"Recommended {len(recommendations)} skills for: {user_content[:50]}...")

        return recommendations

    def _calculate_relevance(self, user_input: str, skill: Dict[str, Any]) -> float:
        """
        Calculate relevance score between user input and skill.

        Args:
            user_input: User's message (lowercase)
            skill: Parsed skill dictionary

        Returns:
            Relevance score (0.0 - 1.0)
        """
        score = 0.0
        max_score = 0.0

        # Match against trigger keywords (highest weight)
        trigger_keywords = skill.get('trigger_keywords', [])
        if trigger_keywords:
            max_score += 1.0
            for keyword in trigger_keywords:
                if keyword in user_input:
                    score += 0.3

        # Match against skill name
        skill_name = skill.get('name', '').lower()
        if skill_name:
            max_score += 0.5
            name_words = skill_name.split()
            for word in name_words:
                if len(word) > 3 and word in user_input:
                    score += 0.2

        # Match against description
        description = skill.get('description', '').lower()
        if description:
            max_score += 0.3
            desc_words = description.split()
            for word in desc_words:
                if len(word) > 4 and word in user_input:
                    score += 0.1

        # Match against examples
        examples = skill.get('examples', '').lower()
        if examples:
            max_score += 0.2
            example_words = examples.split()
            for word in example_words:
                if len(word) > 4 and word in user_input:
                    score += 0.05

        # Normalize score
        if max_score > 0:
            return min(1.0, score / max_score)
        return 0.0

    def get_active_skill(self, user_content: str, threshold: float = 0.5) -> Optional[Dict[str, Any]]:
        """
        Get the most relevant active skill for user input.

        Args:
            user_content: User's message
            threshold: Minimum score to consider "active"

        Returns:
            Best matching skill or None
        """
        recommendations = self.recommend_skills(user_content, threshold=0.0)

        if recommendations and recommendations[0][1] >= threshold:
            return recommendations[0][0]

        return None

    def format_skill_context(self, skill: Dict[str, Any]) -> str:
        """
        Format skill as context for system prompt injection.

        Args:
            skill: Parsed skill dictionary

        Returns:
            Formatted skill context string
        """
        return f"""
[Active Skill: {skill['name']}]
Description: {skill['description']}
Triggers: {skill['triggers']}
Steps to follow:
{self._format_steps(skill['steps'])}
Example: {skill['examples']}
"""

    def _format_steps(self, steps: str) -> str:
        """Format steps as numbered list."""
        if not steps:
            return "  N/A"

        # Check if already numbered
        if re.match(r'^\d+[.\)]', steps.strip()):
            return f"  {steps}"

        # Split and number
        step_list = re.split(r'[.\d]+\s*|:\s*', steps)
        step_list = [s.strip() for s in step_list if s.strip()]

        if len(step_list) == 1:
            return f"  {steps}"

        return '\n'.join(f"  {i+1}. {step}" for i, step in enumerate(step_list[:5]))

    def get_status(self) -> Dict[str, Any]:
        """Get activator status."""
        return {
            "skills_loaded": len(self._skills),
            "cache_valid": bool(self._skill_cache),
        }

    def clear_cache(self):
        """Clear skill cache to force reload."""
        self._skill_cache = []
        self._skills = []

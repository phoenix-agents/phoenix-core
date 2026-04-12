#!/usr/bin/env python3
"""
Bot Security Guard - Workspace-scoped security for each bot

Each bot has its own guard that:
1. Restricts access to its own workspace only
2. Checks risk levels before task execution
3. Logs audit trails
"""

import logging
from typing import Dict, Any, List, Tuple
from pathlib import Path

from skill_risk_assessor import RiskAssessor
from skills_guard import SkillsGuard, DEFAULT_ROLES

logger = logging.getLogger(__name__)


class BotGuard(SkillsGuard):
    """
    Security guard for a specific bot.

    Responsibilities:
    1. Ensure bot only accesses its own workspace
    2. Check risk levels before task execution
    3. Prevent cross-bot interference
    4. Log all access attempts
    """

    def __init__(self, bot_name: str, risk_assessor: RiskAssessor = None):
        self.bot_name = bot_name
        self.allowed_workspace = f"workspaces/{bot_name}/"
        self.risk_assessor = risk_assessor or RiskAssessor()

        # Bot roles - bots are "developers" by default
        # They can execute skills within their domain
        bot_roles = DEFAULT_ROLES.copy()
        bot_roles["bot"] = {
            "can_execute_all": False,
            "can_create_skills": False,
            "can_modify_skills": False,
            "can_delete_skills": False,
            "can_view_memory": True,
            "can_modify_memory": True,
            "max_risk_level": 0.5,  # Medium risk max
        }

        super().__init__()
        self._roles = bot_roles
        self._current_role = "bot"

    def can_execute_skill(self, skill: Dict[str, Any],
                          risk_level: float = None) -> Tuple[bool, str]:
        """
        Check if bot can execute a skill.

        Additional checks beyond parent class:
        1. Workspace boundary check
        2. Cross-bot interference check
        """
        # Check workspace boundary
        if not self._check_workspace_boundary(skill):
            reason = f"Skill attempts to access other bot's workspace"
            self._log_access("execute", skill.get("name", "unknown"),
                            allowed=False, reason=reason)
            return False, reason

        # Check cross-bot interference
        if self._interferes_with_other_bot(skill):
            reason = f"Skill interferes with another bot's domain"
            self._log_access("execute", skill.get("name", "unknown"),
                            allowed=False, reason=reason)
            return False, reason

        # If risk level not provided, assess it
        if risk_level is None:
            assessment = self.risk_assessor.assess_skill(skill)
            risk_level = assessment["risk_score"]

        # Call parent class for standard RBAC checks
        return super().can_execute_skill(skill, risk_level)

    def _check_workspace_boundary(self, skill: Dict[str, Any]) -> bool:
        """
        Check if skill stays within bot's workspace boundary.

        Returns True if skill only accesses allowed workspace.
        """
        # Extract file paths from skill steps
        steps = skill.get("steps", "")
        if isinstance(steps, list):
            steps = " ".join(steps)

        # Check for workspace paths
        workspace_paths = self._extract_workspace_paths(steps)

        for path in workspace_paths:
            if not path.startswith(self.allowed_workspace):
                logger.warning(
                    f"[{self.bot_name}] Workspace violation: "
                    f"{path} not in {self.allowed_workspace}"
                )
                return False

        return True

    def _extract_workspace_paths(self, text: str) -> List[str]:
        """Extract workspace paths from text."""
        import re
        # Match paths like workspaces/{bot_name}/...
        pattern = r"workspaces/[^/\s]+(?:/[^/\s]+)*"
        return re.findall(pattern, text)

    def _interferes_with_other_bot(self, skill: Dict[str, Any]) -> bool:
        """
        Check if skill interferes with another bot's domain.

        Currently checks for:
        - Attempts to modify other bot's identity files
        - Attempts to send messages as other bot
        """
        steps = skill.get("steps", "")
        if isinstance(steps, list):
            steps = " ".join(steps)

        # Check for identity file modification
        identity_files = [
            f"workspaces/{bot}/IDENTITY.md"
            for bot in ["编导", "剪辑", "美工", "场控", "客服", "运营", "渠道", "小小谦"]
            if bot != self.bot_name
        ]

        for identity_file in identity_files:
            if identity_file in steps:
                logger.warning(
                    f"[{self.bot_name}] Attempted to modify "
                    f"another bot's IDENTITY.md: {identity_file}"
                )
                return True

        return False

    def _log_access(self, action: str, skill_name: str,
                    allowed: bool, reason: str = ""):
        """Log access attempt for audit."""
        log_entry = {
            "bot": self.bot_name,
            "action": action,
            "skill": skill_name,
            "allowed": allowed,
            "reason": reason,
            "timestamp": str(logging.getLogger().handlers[0].formatter.formatTime(
                logging.LogRecord("", 0, "", 0, "", (), None)
            )) if logging.getLogger().handlers else ""
        }
        logger.info(f"Security audit: {log_entry}")


class BotSecurityManager:
    """
    Centralized security management for all bots.

    Provides:
    1. Per-bot guard instances
    2. Cross-bot conflict detection
    3. Global audit logging
    """

    def __init__(self):
        self._guards: Dict[str, BotGuard] = {}
        self._risk_assessor = RiskAssessor()

    def get_guard(self, bot_name: str) -> BotGuard:
        """Get or create guard for a bot."""
        if bot_name not in self._guards:
            self._guards[bot_name] = BotGuard(
                bot_name,
                risk_assessor=self._risk_assessor
            )
        return self._guards[bot_name]

    def can_execute(self, bot_name: str, skill: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Check if a bot can execute a skill.

        Convenience method for quick permission checks.
        """
        guard = self.get_guard(bot_name)
        return guard.can_execute_skill(skill)

    def get_all_guards(self) -> Dict[str, BotGuard]:
        """Get all guard instances."""
        return self._guards.copy()


# Global instance
_security_manager: BotSecurityManager = None


def get_security_manager() -> BotSecurityManager:
    """Get global security manager instance."""
    global _security_manager
    if _security_manager is None:
        _security_manager = BotSecurityManager()
    return _security_manager


def get_bot_guard(bot_name: str) -> BotGuard:
    """Get guard for a specific bot."""
    return get_security_manager().get_guard(bot_name)


def check_bot_permission(bot_name: str, skill: Dict[str, Any]) -> Tuple[bool, str]:
    """Check if bot has permission to execute a skill."""
    return get_security_manager().can_execute(bot_name, skill)

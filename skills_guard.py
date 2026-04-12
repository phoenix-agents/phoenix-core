#!/usr/bin/env python3
"""
Skills Guard - Security module for skill access control

This module provides RBAC-based permission checking for skill operations,
ensuring users can only execute skills they're authorized for.

Key Features:
1. Role-based access control (RBAC)
2. Skill permission levels
3. Sensitive operation blocking
4. Audit logging

Usage:
    guard = SkillsGuard()

    # Check if user can execute a skill
    if guard.can_execute(user_role, skill):
        executor.execute(skill)
    else:
        print("Access denied")
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Default role permissions
DEFAULT_ROLES = {
    "admin": {
        "can_execute_all": True,
        "can_create_skills": True,
        "can_modify_skills": True,
        "can_delete_skills": True,
        "can_view_memory": True,
        "can_modify_memory": True,
        "max_risk_level": 1.0,  # Can execute any risk level
    },
    "developer": {
        "can_execute_all": False,
        "can_create_skills": True,
        "can_modify_skills": False,
        "can_delete_skills": False,
        "can_view_memory": True,
        "can_modify_memory": False,
        "max_risk_level": 0.6,  # Can execute up to medium risk
    },
    "viewer": {
        "can_execute_all": False,
        "can_create_skills": False,
        "can_modify_skills": False,
        "can_delete_skills": False,
        "can_view_memory": True,
        "can_modify_memory": False,
        "max_risk_level": 0.3,  # Low risk only
    }
}

# Blocked action patterns (never allowed)
BLOCKED_ACTIONS = [
    "sudo rm -rf /",
    "rm -rf ~",
    "drop database",
    "delete all",
    "format c:",
    ":(){ :|:& };:",  # Fork bomb
]

# Sensitive patterns requiring confirmation
SENSITIVE_PATTERNS = [
    "rm -rf",
    "delete",
    "drop",
    "truncate",
    "destroy",
    "terminate",
    "shutdown",
    "kill",
]


class SkillsGuard:
    """
    Security guard for skill operations.

    Responsibilities:
    1. Check user permissions before skill execution
    2. Block malicious or dangerous operations
    3. Log all access attempts for audit
    """

    def __init__(self, config_path: str = None):
        self._roles = DEFAULT_ROLES.copy()
        self._current_role: str = "developer"
        self._audit_log: List[Dict[str, Any]] = []
        self._config_path = config_path

        # Load custom roles if config exists
        if config_path and Path(config_path).exists():
            self._load_config()

    def set_current_role(self, role: str):
        """Set the current user's role."""
        if role not in self._roles:
            logger.warning(f"Unknown role '{role}', defaulting to 'developer'")
            role = "developer"
        self._current_role = role
        logger.info(f"Role set to: {role}")

    def get_current_role(self) -> str:
        """Get the current user's role."""
        return self._current_role

    def can_execute_skill(self, skill: Dict[str, Any],
                          risk_level: float = None) -> tuple[bool, str]:
        """
        Check if current user can execute a skill.

        Args:
            skill: Skill definition dictionary
            risk_level: Pre-calculated risk score (0.0-1.0)

        Returns:
            (allowed, reason) tuple
        """
        role_config = self._roles[self._current_role]

        # Check for blocked actions in skill steps (ALWAYS checked, even for admin)
        steps = skill.get("steps", "")
        blocked_action = self._check_blocked_actions(steps)
        if blocked_action:
            reason = f"Skill contains blocked action: {blocked_action}"
            self._log_access("execute", skill.get("name", "unknown"),
                            allowed=False, reason=reason)
            return False, reason

        # Check if role can execute all skills
        if role_config.get("can_execute_all", False):
            return True, "Admin access granted"

        # Check risk level
        if risk_level is not None:
            max_risk = role_config.get("max_risk_level", 0.5)
            if risk_level > max_risk:
                reason = f"Risk level {risk_level:.2f} exceeds {self._current_role} limit ({max_risk:.2f})"
                self._log_access("execute", skill.get("name", "unknown"),
                                allowed=False, reason=reason)
                return False, reason

        self._log_access("execute", skill.get("name", "unknown"),
                        allowed=True, reason="Permission granted")
        return True, "Permission granted"

    def can_modify_memory(self) -> tuple[bool, str]:
        """Check if current user can modify memory."""
        role_config = self._roles[self._current_role]

        if role_config.get("can_modify_memory", False):
            return True, "Permission granted"

        reason = f"Role '{self._current_role}' cannot modify memory"
        self._log_access("modify_memory", "memory",
                        allowed=False, reason=reason)
        return False, reason

    def can_create_skill(self) -> tuple[bool, str]:
        """Check if current user can create skills."""
        role_config = self._roles[self._current_role]

        if role_config.get("can_create_skills", False):
            return True, "Permission granted"

        reason = f"Role '{self._current_role}' cannot create skills"
        self._log_access("create_skill", "skill",
                        allowed=False, reason=reason)
        return False, reason

    def can_delete_skill(self) -> tuple[bool, str]:
        """Check if current user can delete skills."""
        role_config = self._roles[self._current_role]

        if role_config.get("can_delete_skills", False):
            return True, "Permission granted"

        reason = f"Role '{self._current_role}' cannot delete skills"
        self._log_access("delete_skill", "skill",
                        allowed=False, reason=reason)
        return False, reason

    def check_content_safety(self, content: str) -> tuple[bool, str]:
        """
        Check if content is safe to store in memory.

        Args:
            content: Content to validate

        Returns:
            (safe, reason) tuple
        """
        content_lower = content.lower()

        # Check for blocked patterns
        for pattern in BLOCKED_ACTIONS:
            if pattern.lower() in content_lower:
                return False, f"Blocked pattern detected: {pattern}"

        # Check for prompt injection attempts
        injection_patterns = [
            "ignore previous",
            "system prompt",
            "you are now",
            "new instructions",
            "override",
        ]

        for pattern in injection_patterns:
            if pattern.lower() in content_lower:
                return False, f"Potential injection detected: {pattern}"

        return True, "Content is safe"

    def requires_confirmation(self, skill: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Check if skill execution requires user confirmation.

        Args:
            skill: Skill definition dictionary

        Returns:
            (needs_confirmation, reasons) tuple
        """
        reasons = []
        steps = skill.get("steps", "")
        steps_lower = steps.lower()

        for pattern in SENSITIVE_PATTERNS:
            if pattern.lower() in steps_lower:
                reasons.append(f"Contains sensitive action: {pattern}")

        needs_confirmation = len(reasons) > 0
        return needs_confirmation, reasons

    def _check_blocked_actions(self, steps: str) -> Optional[str]:
        """Check for blocked actions in skill steps."""
        steps_lower = steps.lower()

        for pattern in BLOCKED_ACTIONS:
            if pattern.lower() in steps_lower:
                return pattern

        return None

    def _log_access(self, action: str, target: str,
                    allowed: bool, reason: str = ""):
        """Log access attempt for audit."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "role": self._current_role,
            "action": action,
            "target": target,
            "allowed": allowed,
            "reason": reason
        }
        self._audit_log.append(entry)

        log_level = logging.INFO if allowed else logging.WARNING
        logger.log(log_level,
                  f"Access {action} on {target}: {'ALLOWED' if allowed else 'DENIED'} - {reason}")

    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent audit log entries."""
        return self._audit_log[-limit:]

    def clear_audit_log(self):
        """Clear the audit log."""
        self._audit_log.clear()
        logger.info("Audit log cleared")

    def _load_config(self):
        """Load custom role configuration."""
        try:
            with open(self._config_path, 'r') as f:
                config = json.load(f)

            if 'roles' in config:
                self._roles.update(config['roles'])
                logger.info(f"Loaded {len(config['roles'])} custom roles")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")

    def add_custom_role(self, name: str, permissions: Dict[str, Any]):
        """
        Add or update a custom role.

        Args:
            name: Role name
            permissions: Permission dictionary
        """
        self._roles[name] = permissions
        logger.info(f"Role '{name}' added/updated")

    def get_role_permissions(self, role: str = None) -> Dict[str, Any]:
        """Get permissions for a role."""
        role = role or self._current_role
        return self._roles.get(role, {})

    def get_status(self) -> Dict[str, Any]:
        """Get guard status summary."""
        return {
            "current_role": self._current_role,
            "available_roles": list(self._roles.keys()),
            "audit_log_entries": len(self._audit_log),
            "permissions": self._roles[self._current_role]
        }


# Singleton instance for easy access
_guard_instance: Optional[SkillsGuard] = None


def get_guard(config_path: str = None) -> SkillsGuard:
    """Get or create SkillsGuard singleton."""
    global _guard_instance
    if _guard_instance is None:
        _guard_instance = SkillsGuard(config_path=config_path)
    return _guard_instance


def check_skill_execution(skill: Dict[str, Any],
                          risk_level: float = None) -> tuple[bool, str]:
    """
    Quick permission check using default guard.

    Args:
        skill: Skill definition
        risk_level: Pre-calculated risk score

    Returns:
        (allowed, reason) tuple
    """
    guard = get_guard()
    return guard.can_execute_skill(skill, risk_level=risk_level)

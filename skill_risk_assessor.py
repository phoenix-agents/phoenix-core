#!/usr/bin/env python3
"""
Risk Assessment Module for Skill Execution Sandbox

Analyzes skill steps to determine:
1. Risk level (low/medium/high)
2. Side effects
3. Reversibility
4. Dependencies
5. Security vulnerabilities (integrated with SecurityAuditor)
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from security_auditor import SecurityAuditor

logger = logging.getLogger(__name__)


class RiskAssessor:
    """
    Assesses risk level of skill execution.

    Risk Categories:
    - LOW: Read-only operations, no side effects
    - MEDIUM: Creates/modifies data, reversible
    - HIGH: Destructive operations, external calls, irreversible
    """

    # Risk weights for different actions
    ACTION_RISK = {
        "check": 0.1,      # Read-only
        "verify": 0.1,     # Read-only
        "read": 0.1,       # Read-only
        "list": 0.1,       # Read-only
        "get": 0.1,        # Read-only
        "initialize": 0.3, # Creates instance
        "configure": 0.4,  # Modifies config
        "setup": 0.4,      # Setup operations
        "load": 0.2,       # Loads data
        "create": 0.5,     # Creates resource
        "start": 0.4,      # Starts service
        "stop": 0.5,       # Stops service
        "restart": 0.6,    # Restarts service
        "send": 0.5,       # External communication
        "fetch": 0.3,      # External data
        "inject": 0.4,     # Modifies context
        "delete": 0.8,     # Destructive
        "remove": 0.7,     # Destructive
        "drop": 0.9,       # Highly destructive
        "execute": 0.6,    # Executes code
        "run": 0.5,        # Runs process
    }

    # High-risk keywords
    HIGH_RISK_KEYWORDS = [
        "delete", "drop", "destroy", "remove", "kill", "terminate",
        "format", "wipe", "purge", "truncate", "overwrite"
    ]

    # External dependency keywords
    EXTERNAL_KEYWORDS = [
        "api", "webhook", "http", "request", "external", "remote",
        "network", "socket", "port", "database", "db", "s3", "cloud"
    ]

    # Irreversible operations
    IRREVERSIBLE_KEYWORDS = [
        "delete", "drop", "destroy", "wipe", "purge", "format",
        "overwrite", "truncate"
    ]

    def assess_skill(self, skill: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess risk level of a skill.

        Args:
            skill: Skill dictionary

        Returns:
            Risk assessment result
        """
        steps = skill.get('steps', [])
        description = skill.get('description', '')

        # Parse steps if string
        if isinstance(steps, str):
            step_list = self._parse_steps(steps)
        else:
            step_list = steps

        # Analyze each step
        step_assessments = []
        total_risk = 0.0
        side_effects = []
        dependencies = []
        irreversible = False

        for step_text in step_list:
            assessment = self._assess_step(step_text)
            step_assessments.append(assessment)

            total_risk += assessment['risk_score']
            side_effects.extend(assessment.get('side_effects', []))
            dependencies.extend(assessment.get('dependencies', []))

            if assessment.get('irreversible'):
                irreversible = True

        # Calculate overall risk level
        avg_risk = total_risk / len(step_list) if step_list else 0
        risk_level = self._calculate_risk_level(avg_risk, irreversible, len(dependencies))

        return {
            "risk_level": risk_level,
            "risk_score": round(avg_risk, 2),
            "total_steps": len(step_list),
            "step_assessments": step_assessments,
            "side_effects": list(set(side_effects)),
            "dependencies": list(set(dependencies)),
            "irreversible": irreversible,
            "safe_for_sandbox": risk_level in ["low", "medium"],
            "warnings": self._generate_warnings(risk_level, irreversible, dependencies)
        }

    def _assess_step(self, step_text: str) -> Dict[str, Any]:
        """Assess risk of a single step."""
        step_lower = step_text.lower()

        # Find action verb
        action = self._extract_action(step_text)
        base_risk = self.ACTION_RISK.get(action, 0.3)

        # Adjust for high-risk keywords
        for keyword in self.HIGH_RISK_KEYWORDS:
            if keyword in step_lower:
                base_risk = max(base_risk, 0.8)

        # Identify side effects
        side_effects = []
        if action in ['create', 'initialize', 'setup']:
            side_effects.append("Creates new resources")
        if action in ['configure', 'modify', 'update']:
            side_effects.append("Modifies configuration")
        if action in ['delete', 'remove', 'drop']:
            side_effects.append("Deletes data/resources")
        if action in ['start', 'stop', 'restart']:
            side_effects.append("Affects service state")
        if action in ['send', 'webhook', 'notify']:
            side_effects.append("External communication")

        # Identify dependencies
        dependencies = []
        for keyword in self.EXTERNAL_KEYWORDS:
            if keyword in step_lower:
                if 'database' in step_lower or 'db' in step_lower:
                    dependencies.append("Database")
                if 'api' in step_lower or 'webhook' in step_lower:
                    dependencies.append("External API")
                if 'port' in step_lower or 'socket' in step_lower:
                    dependencies.append("Network")
                if 'file' in step_lower or 'disk' in step_lower:
                    dependencies.append("File system")

        # Check reversibility
        irreversible = any(kw in step_lower for kw in self.IRREVERSIBLE_KEYWORDS)

        return {
            "step_text": step_text,
            "action": action,
            "risk_score": base_risk,
            "side_effects": side_effects,
            "dependencies": dependencies,
            "irreversible": irreversible
        }

    def _extract_action(self, step_text: str) -> str:
        """Extract action verb from step text."""
        words = step_text.split()
        if words:
            # Clean first word
            action = words[0].lower()
            action = action.rstrip('.:;,)!]')
            return action
        return "unknown"

    def _parse_steps(self, steps_str: str) -> List[str]:
        """Parse steps string into list."""
        import re
        # Split on numbered patterns
        step_list = re.split(r'\d+[\.\)]\s*', steps_str)
        return [s.strip() for s in step_list if s.strip()]

    def _calculate_risk_level(self, avg_risk: float, irreversible: bool,
                              dependency_count: int) -> str:
        """Calculate overall risk level."""
        # Adjust for irreversibility
        if irreversible:
            return "high"

        # Adjust for many dependencies
        if dependency_count >= 3:
            return "high"

        # Based on average risk
        if avg_risk < 0.3:
            return "low"
        elif avg_risk < 0.6:
            return "medium"
        else:
            return "high"

    def _generate_warnings(self, risk_level: str, irreversible: bool,
                          dependencies: List[str]) -> List[str]:
        """Generate warning messages."""
        warnings = []

        if risk_level == "high":
            warnings.append("High risk operation - review before executing")

        if irreversible:
            warnings.append("Contains irreversible operations")

        if "External API" in dependencies:
            warnings.append("Depends on external API availability")

        if "Database" in dependencies:
            warnings.append("Database operations - ensure backup exists")

        if "Network" in dependencies:
            warnings.append("Network operations - may fail due to connectivity")

        return warnings

    def audit_skill_security(self, skill_path: str) -> Dict[str, Any]:
        """
        Perform security audit using SecurityAuditor.

        Args:
            skill_path: Path to skill file or directory

        Returns:
            Security audit result integrated with risk assessment
        """
        try:
            auditor = SecurityAuditor()
            security_report = auditor.audit_skill(skill_path)

            # Integrate security findings into risk assessment
            security_findings = security_report.get("findings", [])
            security_risk = security_report.get("risk_score", 0)
            verdict = security_report.get("verdict", "PASS")

            # Convert security verdict to risk level
            if verdict == "FAIL":
                security_risk_level = "critical"
            elif verdict == "REVIEW_NEEDED":
                security_risk_level = "high"
            else:
                security_risk_level = "low"

            return {
                "security_audit": True,
                "verdict": verdict,
                "risk_score": security_risk,
                "risk_level": security_risk_level,
                "total_findings": security_report.get("total_findings", 0),
                "findings_by_severity": security_report.get("findings_by_severity", {}),
                "findings": security_findings[:10],  # Limit to first 10 for brevity
                "safe_to_install": security_report.get("safe_to_install", False),
                "recommendations": self._generate_security_recommendations(security_findings),
            }

        except Exception as e:
            logger.error(f"Security audit failed: {e}")
            return {
                "security_audit": True,
                "verdict": "ERROR",
                "error": str(e),
                "safe_to_install": False,
            }

    def _generate_security_recommendations(self, findings: List[Dict]) -> List[str]:
        """Generate security recommendations based on findings."""
        recommendations = []

        # Group by severity
        critical = [f for f in findings if f.get("severity") == "critical"]
        high = [f for f in findings if f.get("severity") == "high"]

        if critical:
            recommendations.append("🛑 CRITICAL: Do not install this skill. Contains dangerous security vulnerabilities.")
            for f in critical[:3]:
                recommendations.append(f"  - {f.get('title', 'Unknown issue')}: {f.get('remediation', 'Fix required')}")

        if high:
            recommendations.append("⚠️ HIGH RISK: Manual security review required before installation.")
            for f in high[:3]:
                recommendations.append(f"  - {f.get('title', 'Unknown issue')}: {f.get('remediation', 'Fix required')}")

        if not critical and not high:
            recommendations.append("✅ Skill passed security audit. Safe to install.")

        return recommendations

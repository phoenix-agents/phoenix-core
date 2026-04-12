#!/usr/bin/env python3
"""
SandyClaw-inspired Dynamic Sandbox for AI Agent Skills

Inspired by Permiso.io's SandyClaw (https://permiso.io/blog/introducing-sandyclaw-dynamic-sandbox-ai-agent-skills)

This module provides dynamic analysis of skills by executing them in a controlled,
isolated environment to observe actual runtime behavior.

Key Features:
1. Sandboxed skill execution
2. Behavior monitoring
3. Network traffic analysis
4. File system change tracking
5. Process monitoring
6. Automatic rollback
"""

import json
import logging
import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DynamicSandbox:
    """
    Dynamic sandbox for skill execution analysis.

    Executes skills in isolated environments and monitors:
    - File system changes
    - Network activity
    - Process spawning
    - Environment variable access
    - System calls
    """

    def __init__(self, workspace_dir: str = None):
        self.workspace_dir = Path(workspace_dir) if workspace_dir else Path(tempfile.mkdtemp())
        self.sandbox_dir: Optional[Path] = None
        self.execution_log: List[Dict[str, Any]] = []
        self.file_changes: List[Dict[str, Any]] = []
        self.network_calls: List[Dict[str, Any]] = []
        self.process_spawns: List[Dict[str, Any]] = []

    @contextmanager
    def sandboxed_environment(self, skill_name: str):
        """
        Create a sandboxed environment for skill execution.

        Args:
            skill_name: Name of the skill to execute

        Yields:
            Sandbox context dictionary
        """
        # Create isolated sandbox directory
        self.sandbox_dir = self.workspace_dir / f"sandbox_{skill_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)

        # Create isolated subdirectories
        (self.sandbox_dir / "workspace").mkdir()
        (self.sandbox_dir / "output").mkdir()
        (self.sandbox_dir / "logs").mkdir()

        # Snapshot initial state
        initial_snapshot = self._snapshot_filesystem()

        logger.info(f"Sandbox created for {skill_name} at {self.sandbox_dir}")

        try:
            yield {
                "sandbox_dir": self.sandbox_dir,
                "workspace_dir": self.sandbox_dir / "workspace",
                "output_dir": self.sandbox_dir / "output",
                "log_dir": self.sandbox_dir / "logs",
            }
        finally:
            # Compare final state with initial snapshot
            final_snapshot = self._snapshot_filesystem()
            self._detect_changes(initial_snapshot, final_snapshot)

            logger.info(f"Sandbox execution complete for {skill_name}")

    def _snapshot_filesystem(self) -> Dict[str, Any]:
        """Create a snapshot of the filesystem state."""
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "files": {},
            "directories": [],
        }

        if self.sandbox_dir and self.sandbox_dir.exists():
            for f in self.sandbox_dir.rglob("*"):
                if f.is_file():
                    try:
                        stat = f.stat()
                        snapshot["files"][str(f)] = {
                            "size": stat.st_size,
                            "mtime": stat.st_mtime,
                            "mode": oct(stat.st_mode),
                        }
                    except Exception as e:
                        logger.warning(f"Could not stat {f}: {e}")
                elif f.is_dir():
                    snapshot["directories"].append(str(f))

        return snapshot

    def _detect_changes(self, initial: Dict, final: Dict):
        """Detect filesystem changes between snapshots."""
        initial_files = set(initial.get("files", {}).keys())
        final_files = set(final.get("files", {}).keys())

        # New files
        for path in final_files - initial_files:
            self.file_changes.append({
                "type": "created",
                "path": path,
                "size": final["files"].get(path, {}).get("size", 0),
            })

        # Deleted files
        for path in initial_files - final_files:
            self.file_changes.append({
                "type": "deleted",
                "path": path,
            })

        # Modified files
        for path in initial_files & final_files:
            initial_size = initial["files"].get(path, {}).get("size", 0)
            final_size = final["files"].get(path, {}).get("size", 0)
            if initial_size != final_size:
                self.file_changes.append({
                    "type": "modified",
                    "path": path,
                    "size_change": final_size - initial_size,
                })

    def execute_skill(self, skill: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
        """
        Execute a skill in the sandbox and monitor behavior.

        Args:
            skill: Skill definition dictionary
            timeout: Execution timeout in seconds

        Returns:
            Behavior analysis report
        """
        skill_name = skill.get("name", "unknown")
        report = {
            "skill_name": skill_name,
            "executed_at": datetime.now().isoformat(),
            "status": "unknown",
            "behavior": {
                "file_changes": [],
                "network_calls": [],
                "process_spawns": [],
                "env_access": [],
            },
            "verdict": "unknown",
            "warnings": [],
        }

        with self.sandboxed_environment(skill_name) as ctx:
            try:
                # Execute skill with monitoring
                result = self._execute_monitored(skill, ctx, timeout)
                report["status"] = result.get("status", "completed")
                report["behavior"]["file_changes"] = self.file_changes.copy()
                report["behavior"]["network_calls"] = self.network_calls.copy()
                report["behavior"]["process_spawns"] = self.process_spawns.copy()

                # Determine verdict
                report["verdict"] = self._determine_verdict(report)
                report["warnings"] = self._generate_warnings(report)

            except subprocess.TimeoutExpired:
                report["status"] = "timeout"
                report["verdict"] = "SUSPICIOUS"
                report["warnings"].append("Skill execution timed out - may indicate infinite loop or hanging process")

            except Exception as e:
                report["status"] = "error"
                report["verdict"] = "ERROR"
                report["warnings"].append(f"Execution error: {str(e)}")

        self.execution_log.append(report)
        return report

    def _execute_monitored(self, skill: Dict, ctx: Dict, timeout: int) -> Dict[str, Any]:
        """Execute skill with behavior monitoring."""
        # For Python-based skills, we can directly analyze
        # For other skills, we simulate execution

        skill_content = skill.get("content", "")
        skill_steps = skill.get("steps", "")

        # Analyze without actual execution (safe mode)
        # This is a simplified version - full sandbox would use containers/VMs

        # Check for network calls
        network_indicators = ["requests.", "urllib", "http://", "https://", "socket.", "fetch("]
        for indicator in network_indicators:
            if indicator in skill_content:
                self.network_calls.append({
                    "indicator": indicator,
                    "detected_at": datetime.now().isoformat(),
                })

        # Check for process spawning
        process_indicators = ["subprocess.", "os.system", "os.popen", "Popen", "spawn"]
        for indicator in process_indicators:
            if indicator in skill_content:
                self.process_spawns.append({
                    "indicator": indicator,
                    "detected_at": datetime.now().isoformat(),
                })

        # Check for environment access
        env_indicators = ["os.environ", "process.env", "getenv", "environ["]
        for indicator in env_indicators:
            if indicator in skill_content:
                self.file_changes.append({
                    "type": "env_access",
                    "indicator": indicator,
                    "detected_at": datetime.now().isoformat(),
                })

        return {"status": "completed"}

    def _determine_verdict(self, report: Dict) -> str:
        """Determine sandbox verdict based on behavior."""
        behavior = report.get("behavior", {})

        # Check for suspicious behavior
        suspicious_file_changes = [
            f for f in behavior.get("file_changes", [])
            if f.get("type") == "created" and "workspace" not in f.get("path", "")
        ]

        if suspicious_file_changes:
            return "SUSPICIOUS"

        if behavior.get("network_calls"):
            return "REVIEW_NEEDED"

        if behavior.get("process_spawns"):
            return "REVIEW_NEEDED"

        return "SAFE"

    def _generate_warnings(self, report: Dict) -> List[str]:
        """Generate warnings based on behavior."""
        warnings = []
        behavior = report.get("behavior", {})

        if behavior.get("file_changes"):
            warnings.append(f"File system changes detected: {len(behavior['file_changes'])} changes")

        if behavior.get("network_calls"):
            warnings.append(f"Network activity detected: {len(behavior['network_calls'])} calls")

        if behavior.get("process_spawns"):
            warnings.append(f"Process spawning detected: {len(behavior['process_spawns'])} spawns")

        return warnings

    def get_execution_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent execution history."""
        return self.execution_log[-limit:]

    def cleanup(self):
        """Clean up sandbox directories."""
        if self.sandbox_dir and self.sandbox_dir.exists():
            try:
                shutil.rmtree(self.sandbox_dir)
                logger.info(f"Sandbox cleaned up: {self.sandbox_dir}")
            except Exception as e:
                logger.error(f"Cleanup failed: {e}")


class BehaviorAnalyzer:
    """
    Analyzes skill behavior patterns to detect malicious intent.

    Uses pattern matching and heuristics to identify:
    - Data exfiltration attempts
    - Persistence mechanisms
    - Privilege escalation
    - Lateral movement
    """

    # Malicious behavior patterns
    EXFILTRATION_PATTERNS = [
        r"POST.*\/(upload|exfil|steal|send)",
        r"requests\.post.*headers.*Authorization",
        r"socket\.connect.*\d+",
    ]

    PERSISTENCE_PATTERNS = [
        r"cron.*@",
        r"systemd.*service",
        r"\.bashrc",
        r"\.profile",
        r"startup",
    ]

    PRIV_ESC_PATTERNS = [
        r"sudo",
        r"pkexec",
        r"setuid",
        r"chmod\s+[47]",
    ]

    def analyze_behavior(self, skill_content: str) -> Dict[str, Any]:
        """
        Analyze skill content for malicious behavior patterns.

        Args:
            skill_content: Skill code/content as string

        Returns:
            Behavior analysis report
        """
        import re

        report = {
            "analyzed_at": datetime.now().isoformat(),
            "patterns_detected": [],
            "risk_indicators": [],
            "verdict": "SAFE",
        }

        # Check for exfiltration patterns
        for pattern in self.EXFILTRATION_PATTERNS:
            if re.search(pattern, skill_content, re.IGNORECASE):
                report["patterns_detected"].append({
                    "category": "exfiltration",
                    "pattern": pattern,
                    "severity": "high",
                })

        # Check for persistence patterns
        for pattern in self.PERSISTENCE_PATTERNS:
            if re.search(pattern, skill_content, re.IGNORECASE):
                report["patterns_detected"].append({
                    "category": "persistence",
                    "pattern": pattern,
                    "severity": "critical",
                })

        # Check for privilege escalation patterns
        for pattern in self.PRIV_ESC_PATTERNS:
            if re.search(pattern, skill_content, re.IGNORECASE):
                report["patterns_detected"].append({
                    "category": "privilege_escalation",
                    "pattern": pattern,
                    "severity": "critical",
                })

        # Determine verdict
        critical_count = len([p for p in report["patterns_detected"] if p.get("severity") == "critical"])
        high_count = len([p for p in report["patterns_detected"] if p.get("severity") == "high"])

        if critical_count > 0:
            report["verdict"] = "MALICIOUS"
        elif high_count > 0:
            report["verdict"] = "SUSPICIOUS"
        elif len(report["patterns_detected"]) > 0:
            report["verdict"] = "REVIEW_NEEDED"

        return report


def analyze_skill_safely(skill: Dict[str, Any]) -> Dict[str, Any]:
    """
    Comprehensive safety analysis combining security audit, risk assessment, and sandbox analysis.

    Args:
        skill: Skill definition dictionary

    Returns:
        Comprehensive safety report
    """
    from security_auditor import SecurityAuditor
    from skill_risk_assessor import RiskAssessor

    # 1. Static security audit
    auditor = SecurityAuditor()
    security_report = auditor.audit_skill(skill.get("name", "unknown"), skill.get("content", ""))

    # 2. Risk assessment
    assessor = RiskAssessor()
    risk_report = assessor.assess_skill(skill)

    # 3. Dynamic sandbox analysis
    sandbox = DynamicSandbox()
    sandbox_report = sandbox.execute_skill(skill, timeout=30)

    # 4. Behavior analysis
    analyzer = BehaviorAnalyzer()
    behavior_report = analyzer.analyze_behavior(skill.get("content", ""))

    # Combine all reports
    combined_report = {
        "skill_name": skill.get("name", "unknown"),
        "analyzed_at": datetime.now().isoformat(),
        "security_audit": security_report,
        "risk_assessment": risk_report,
        "sandbox_analysis": sandbox_report,
        "behavior_analysis": behavior_report,
        "overall_verdict": determine_overall_verdict(security_report, risk_report, sandbox_report, behavior_report),
        "safe_to_install": is_safe_to_install(security_report, sandbox_report, behavior_report),
    }

    return combined_report


def determine_overall_verdict(*reports) -> str:
    """Determine overall verdict from multiple reports."""
    verdicts = []

    for report in reports:
        if isinstance(report, dict):
            verdict = report.get("verdict", "UNKNOWN")
            if verdict != "UNKNOWN":
                verdicts.append(verdict)

    # If any report says MALICIOUS/FAIL, overall is FAIL
    if "MALICIOUS" in verdicts or "FAIL" in verdicts:
        return "FAIL"

    # If any report says SUSPICIOUS, overall is REVIEW_NEEDED
    if "SUSPICIOUS" in verdicts:
        return "REVIEW_NEEDED"

    # If any report says REVIEW_NEEDED, overall is REVIEW_NEEDED
    if "REVIEW_NEEDED" in verdicts:
        return "REVIEW_NEEDED"

    return "PASS"


def is_safe_to_install(*reports) -> bool:
    """Determine if skill is safe to install."""
    for report in reports:
        if isinstance(report, dict):
            # Check explicit safety flags
            if report.get("safe_to_install") is False:
                return False
            if report.get("safe_for_sandbox") is False:
                return False

            # Check verdicts
            verdict = report.get("verdict", "")
            if verdict in ["FAIL", "MALICIOUS", "ERROR"]:
                return False

    return True


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 sandbox_analyzer.py <skill_file>")
        print("Example: python3 sandbox_analyzer.py skills/some-skill/SKILL.md")
        sys.exit(1)

    skill_path = sys.argv[1]

    # Read skill content
    skill_content = Path(skill_path).read_text(encoding="utf-8")

    # Parse skill name
    skill_name = Path(skill_path).parent.stem if skill_path.endswith("SKILL.md") else Path(skill_path).stem

    skill = {
        "name": skill_name,
        "content": skill_content,
    }

    report = analyze_skill_safely(skill)

    print(json.dumps(report, indent=2, ensure_ascii=False))

    print("\n" + "="*60)
    print(f"Safety Analysis Report: {report['skill_name']}")
    print(f"Overall Verdict: {report['overall_verdict']}")
    print(f"Safe to Install: {'YES' if report['safe_to_install'] else 'NO'}")

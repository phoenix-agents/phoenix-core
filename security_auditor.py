#!/usr/bin/env python3
"""
Security Auditor - Automated Security Scanning for Phoenix Core Skills

Based on official Security-Audit Skill from Orac-G
https://github.com/Orac-G/security-audit-skill

Detects:
- Credential exfiltration
- Code obfuscation
- Malicious network activity
- Dangerous file operations
- System file modification
- Backdoor persistence
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SecurityAuditor:
    """
    Automated security scanner for Phoenix Core/NanoClaw skills.

    Produces detailed security reports with risk scores and remediation guidance.
    """

    # Detection patterns organized by severity
    CRITICAL_PATTERNS = {
        "credential_exfiltration": [
            r"(api[_-]?key|apikey)\s*[=:]\s*[\"'][^\"']+[\"']",
            r"(secret|token|password|passwd)\s*[=:]\s*[\"'][^\"']+[\"']",
            r"process\.env\.(?:API_KEY|SECRET|TOKEN|PASSWORD)",
            r"fetch\([^)]*headers[^)]*(?:Authorization|api[-_]?key)",
            r"axios\.post\([^)]*(?:api[_-]?key|secret|token)",
        ],
        "code_obfuscation": [
            r"\beval\s*\(",
            r"\bFunction\s*\(",
            r"Buffer\.from\s*\([^)]*\)\.toString\(",
            r"atob\s*\(",
            r"new\s+Function\s*\(",
            r"vm\.runInNewContext",
            r"vm\.runInThisContext",
        ],
        "process_injection": [
            r"exec\s*\([^)]*\+[^)]*\)",
            r"spawn\s*\([^)]*\+[^)]*\)",
            r"\$\(.*\$\{.*\}\)",
            r"`[^`]*\$\{[^}]+\}[^`]*`",
        ],
        "system_file_modification": [
            r"(?:\/etc\/|\/bin\/|\/usr\/|\/sbin\/|\/var\/)",
            r"\/etc\/passwd",
            r"\/etc\/shadow",
            r"\.ssh\/authorized_keys",
        ],
        "directory_traversal": [
            r"\.\.\/",
            r"\.\.\\",
            r"process\.cwd\(\)\s*\+\s*req\.",
            r"path\.join\s*\(\s*__dirname\s*,\s*\.\.",
        ],
        "backdoor_persistence": [
            r"cron\s*\-y\s+.*echo",
            r"systemd-run",
            r"\.systemd\/",
            r"/etc/rc\.local",
            r"crontab\s+\-e",
            r"startup",
            r"boot",
        ],
    }

    HIGH_PATTERNS = {
        "undocumented_network": [
            r"fetch\s*\(",
            r"axios\.(?:get|post|put|delete)\s*\(",
            r"https?:\/\/[^\s\"')]+",
            r"XMLHttpRequest",
        ],
        "dynamic_urls": [
            r"fetch\s*\([^)]*\+[^)]*\)",
            r"axios\.get\s*\([^)]*\+[^)]*\)",
            r"url\s*=\s*`?[^\`]*\$\{[^\}]+\}[^\`]*`?",
        ],
        "environment_enumeration": [
            r"Object\.keys\s*\(\s*process\.env\s*\)",
            r"for\s*\([^)]*in\s*process\.env",
            r"JSON\.stringify\s*\(\s*process\.env",
        ],
        "shell_execution": [
            r"child_process\.exec",
            r"execSync",
            r"spawnSync",
            r"\/bin\/sh",
            r"\/bin\/bash",
            r"shell:\s*true",
        ],
        "dynamic_imports": [
            r"import\s*\(\s*[^\"']+\s*\)",
            r"require\s*\(\s*[^\"']+\s*\)",
            r"import\s*\([^)]*\+[^)]*\)",
        ],
        "steganography": [
            r"\/\*\s*[A-Za-z0-9+\/=]{50,}\s*\*\/",
            r"\/\/\s*[A-Za-z0-9+\/=]{50,}",
            r"fromCharCode",
        ],
    }

    MEDIUM_PATTERNS = {
        "sensitive_file_access": [
            r"\.(?:env|secret|token|password|key)",
            r"credentials\.json",
            r"\.aws\/credentials",
            r"\.git\/config",
        ],
        "workspace_escape": [
            r"workspace\/\.\.",
            r"\.\.\/\.\.",
            r"chdir\s*\(\s*\"\.",
        ],
        "file_deletion": [
            r"fs\.unlink",
            r"fs\.rm",
            r"fs\.rmdir",
            r"shutil\.rmtree",
            r"os\.remove",
        ],
        "permission_modification": [
            r"chmod\s*\(",
            r"chown\s*\(",
            r"fs\.chmod",
            r"fs\.chown",
        ],
        "prototype_pollution": [
            r"Object\.prototype\.",
            r"__proto__\s*=",
            r"constructor\.prototype",
        ],
    }

    LOW_PATTERNS = {
        "unencrypted_http": [
            r"http:\/\/(?!localhost|127\.0\.0\.1)",
        ],
        "console_logging_secrets": [
            r"console\.log\s*\([^)]*(?:key|secret|token|password)",
            r"log\.info\s*\([^)]*(?:api|secret)",
        ],
        "runtime_dependency_install": [
            r"npm\s+install",
            r"pip\s+install",
            r"yarn\s+add",
            r"git\s+clone",
        ],
        "background_processes": [
            r"setInterval\s*\(",
            r"setTimeout\s*\(\s*\w+\s*,\s*[0-9]{5,}",
        ],
    }

    def __init__(self):
        self.findings: List[Dict[str, Any]] = []
        self.risk_score = 0

    def audit_skill(self, skill_path: str, skill_content: str = None) -> Dict[str, Any]:
        """
        Perform a complete security audit on a skill.

        Args:
            skill_path: Path to skill file or directory
            skill_content: Optional content string (if scanning file directly)

        Returns:
            Security audit report dictionary
        """
        self.findings = []
        self.risk_score = 0

        # Determine what we're auditing
        skill_name = Path(skill_path).stem if skill_path else "unknown"

        # Get content to scan
        content_to_scan = skill_content
        if content_to_scan is None and Path(skill_path).exists():
            if Path(skill_path).is_file():
                content_to_scan = Path(skill_path).read_text(encoding="utf-8")
            elif Path(skill_path).is_dir():
                # Scan all files in directory
                content_to_scan = self._scan_directory(Path(skill_path))

        if not content_to_scan:
            return self._build_report(skill_name, "ERROR", "No content to scan")

        # Run all detection checks
        self._scan_critical(content_to_scan)
        self._scan_high(content_to_scan)
        self._scan_medium(content_to_scan)
        self._scan_low(content_to_scan)

        # Calculate risk score
        self._calculate_risk_score()

        # Determine verdict
        verdict = self._determine_verdict()

        logger.info(f"Security audit complete for {skill_name}: {verdict} (risk: {self.risk_score})")

        return self._build_report(skill_name, verdict, findings=self.findings)

    def _scan_directory(self, dir_path: Path) -> str:
        """Scan all files in a directory and return combined content."""
        contents = []
        for ext in ["*.md", "*.py", "*.js", "*.ts", "*.json", "*.yaml", "*.yml"]:
            for f in dir_path.glob(ext):
                try:
                    content = f.read_text(encoding="utf-8")
                    contents.append(f"=== FILE: {f} ===\n{content}")
                except Exception as e:
                    logger.warning(f"Could not read {f}: {e}")
        return "\n".join(contents)

    def _scan_critical(self, content: str):
        """Scan for critical severity issues."""
        for category, patterns in self.CRITICAL_PATTERNS.items():
            for pattern in patterns:
                self._scan_pattern(content, pattern, "critical", category)

    def _scan_high(self, content: str):
        """Scan for high severity issues."""
        for category, patterns in self.HIGH_PATTERNS.items():
            for pattern in patterns:
                self._scan_pattern(content, pattern, "high", category)

    def _scan_medium(self, content: str):
        """Scan for medium severity issues."""
        for category, patterns in self.MEDIUM_PATTERNS.items():
            for pattern in patterns:
                self._scan_pattern(content, pattern, "medium", category)

    def _scan_low(self, content: str):
        """Scan for low severity issues."""
        for category, patterns in self.LOW_PATTERNS.items():
            for pattern in patterns:
                self._scan_pattern(content, pattern, "low", category)

    def _scan_pattern(self, content: str, pattern: str, severity: str, category: str):
        """Scan content for a single pattern and record findings."""
        try:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                line_start = content[:match.start()].count('\n') + 1
                line_end = content[:match.end()].count('\n') + 1

                # Extract context (the matched line)
                lines = content.split('\n')
                code_excerpt = lines[line_start - 1] if line_start <= len(lines) else ""

                self.findings.append({
                    "severity": severity,
                    "category": category,
                    "title": f"Detected {category.replace('_', ' ')}",
                    "line_start": line_start,
                    "line_end": line_end,
                    "code": code_excerpt.strip()[:200],
                    "description": self._get_description(category, severity),
                    "attack_scenario": self._get_attack_scenario(category),
                    "remediation": self._get_remediation(category),
                })
        except re.error as e:
            logger.warning(f"Regex error for pattern {pattern}: {e}")

    def _get_description(self, category: str, severity: str) -> str:
        """Get human-readable description for a finding."""
        descriptions = {
            "credential_exfiltration": "Code appears to extract and potentially transmit sensitive credentials",
            "code_obfuscation": "Code uses obfuscation techniques that hide its true intent",
            "process_injection": "Potential command injection via shell execution",
            "system_file_modification": "Attempts to modify protected system files",
            "directory_traversal": "Potential directory traversal attack",
            "backdoor_persistence": "Code may establish persistent backdoor access",
            "undocumented_network": "Network activity to potentially undocumented endpoints",
            "dynamic_urls": "URLs constructed dynamically, may redirect to malicious sites",
            "environment_enumeration": "Enumeration of environment variables, may leak secrets",
            "shell_execution": "Direct shell command execution detected",
            "dynamic_imports": "Dynamic module imports may load malicious code",
            "steganography": "Data hidden within code comments or strings",
            "sensitive_file_access": "Access to sensitive configuration files",
            "workspace_escape": "Potential escape from workspace boundaries",
            "file_deletion": "File deletion operations detected",
            "permission_modification": "File permission changes detected",
            "prototype_pollution": "Prototype pollution may affect all objects",
            "unencrypted_http": "Unencrypted HTTP communication",
            "console_logging_secrets": "Potential logging of sensitive information",
            "runtime_dependency_install": "Runtime dependency installation may introduce vulnerabilities",
            "background_processes": "Background process execution detected",
        }
        return descriptions.get(category, f"Potentially dangerous {category} operation ({severity} severity)")

    def _get_attack_scenario(self, category: str) -> str:
        """Describe the potential attack scenario."""
        scenarios = {
            "credential_exfiltration": "Attacker could steal API keys, tokens, or passwords and use them for unauthorized access",
            "code_obfuscation": "Hidden malicious payload executes when skill runs, bypassing security review",
            "process_injection": "Arbitrary commands executed with user's privileges",
            "system_file_modification": "System compromise through modification of critical files",
            "directory_traversal": "Access to files outside intended scope, potentially reading secrets",
            "backdoor_persistence": "Persistent access established that survives skill removal",
            "undocumented_network": "Data exfiltration to attacker-controlled server",
            "dynamic_urls": "User redirected to phishing or malware distribution sites",
            "environment_enumeration": "Secrets leaked through environment variable exposure",
            "shell_execution": "Arbitrary code execution through shell commands",
            "dynamic_imports": "Malicious code loaded from remote source at runtime",
            "steganography": "Hidden payload extracted and executed",
            "sensitive_file_access": "Sensitive credentials stolen from configuration files",
            "workspace_escape": "Access to files outside skill's authorized directory",
            "file_deletion": "Data loss through file deletion",
            "permission_modification": "Security boundaries bypassed through permission changes",
            "prototype_pollution": "Global object pollution affects entire application",
            "unencrypted_http": "Sensitive data transmitted in plaintext",
            "console_logging_secrets": "Secrets exposed in logs accessible to unauthorized parties",
            "runtime_dependency_install": "Malicious package installed at runtime",
            "background_processes": "Hidden process continues running after skill completes",
        }
        return scenarios.get(category, "Potential security compromise")

    def _get_remediation(self, category: str) -> str:
        """Provide remediation guidance."""
        remediations = {
            "credential_exfiltration": "Remove credential handling code. Use environment variables managed externally. Never transmit credentials to external servers.",
            "code_obfuscation": "Remove all obfuscation. Code must be human-readable and auditable.",
            "process_injection": "Use parameterized commands. Never interpolate user input into shell commands.",
            "system_file_modification": "Remove system file access. Skills should only modify workspace files.",
            "directory_traversal": "Validate and sanitize file paths. Use path.resolve() and verify within bounds.",
            "backdoor_persistence": "Remove persistence mechanisms. Skills should not survive removal.",
            "undocumented_network": "Document all external endpoints. Use allowlist for network destinations.",
            "dynamic_urls": "Use static URLs. If dynamic, validate against allowlist.",
            "environment_enumeration": "Only access specific required environment variables.",
            "shell_execution": "Use native APIs instead of shell commands. If shell is required, use strict input validation.",
            "dynamic_imports": "Use static imports only. All dependencies must be declared.",
            "steganography": "Remove hidden data. All data must be explicit and documented.",
            "sensitive_file_access": "Do not access sensitive files. Use provided credential management.",
            "workspace_escape": "Confine all file operations to workspace directory.",
            "file_deletion": "Avoid file deletion. If required, require explicit user confirmation.",
            "permission_modification": "Do not modify file permissions.",
            "prototype_pollution": "Do not modify Object.prototype or similar.",
            "unencrypted_http": "Use HTTPS for all external communication.",
            "console_logging_secrets": "Remove sensitive data from logs. Use logging filters.",
            "runtime_dependency_install": "Declare all dependencies statically. Install during setup, not runtime.",
            "background_processes": "Remove background processes. Skills should complete synchronously.",
        }
        return remediations.get(category, "Review and fix the identified issue")

    def _calculate_risk_score(self):
        """Calculate overall risk score based on findings."""
        score = 0
        for finding in self.findings:
            severity = finding.get("severity", "low")
            if severity == "critical":
                score += 40
            elif severity == "high":
                score += 15
            elif severity == "medium":
                score += 5
            else:  # low
                score += 1
        self.risk_score = min(100, score)

    def _determine_verdict(self) -> str:
        """Determine audit verdict based on findings."""
        has_critical = any(f["severity"] == "critical" for f in self.findings)
        has_high = any(f["severity"] == "high" for f in self.findings)

        if has_critical:
            return "FAIL"
        elif has_high:
            return "REVIEW_NEEDED"
        else:
            return "PASS"

    def _build_report(self, skill_name: str, verdict: str, findings: List = None) -> Dict[str, Any]:
        """Build the final audit report."""
        return {
            "skill": skill_name,
            "audited": datetime.now().isoformat(),
            "verdict": verdict,
            "risk_score": self.risk_score,
            "total_findings": len(self.findings),
            "findings_by_severity": {
                "critical": len([f for f in self.findings if f["severity"] == "critical"]),
                "high": len([f for f in self.findings if f["severity"] == "high"]),
                "medium": len([f for f in self.findings if f["severity"] == "medium"]),
                "low": len([f for f in self.findings if f["severity"] == "low"]),
            },
            "findings": self.findings,
            "safe_to_install": verdict == "PASS",
        }


def audit_skill_file(skill_path: str) -> Dict[str, Any]:
    """
    Convenience function to audit a skill file.

    Args:
        skill_path: Path to skill file or directory

    Returns:
        Audit report dictionary
    """
    auditor = SecurityAuditor()
    return auditor.audit_skill(skill_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 security_auditor.py <skill_file_or_directory>")
        print("Example: python3 security_auditor.py skills/some-skill/")
        sys.exit(1)

    skill_path = sys.argv[1]
    report = audit_skill_file(skill_path)

    print(json.dumps(report, indent=2, ensure_ascii=False))

    # Print summary
    print("\n" + "="*60)
    print(f"Security Audit Report: {report['skill']}")
    print(f"Verdict: {report['verdict']}")
    print(f"Risk Score: {report['risk_score']}/100")
    print(f"Total Findings: {report['total_findings']}")
    print(f"  Critical: {report['findings_by_severity']['critical']}")
    print(f"  High: {report['findings_by_severity']['high']}")
    print(f"  Medium: {report['findings_by_severity']['medium']}")
    print(f"  Low: {report['findings_by_severity']['low']}")
    print(f"Safe to install: {'YES' if report['safe_to_install'] else 'NO'}")

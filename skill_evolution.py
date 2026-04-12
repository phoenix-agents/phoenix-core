#!/usr/bin/env python3
"""
Skill Evolution - Versioned Skill Evolution

Supports:
1. Versioned skills (v1 → v2 → v3)
2. Preserve history (never overwrite)
3. Deprecate old versions (mark as deprecated)
4. Track evolution lineage

Usage:
    evolution = SkillEvolution(memory_manager)
    result = evolution.evolve_skill("memory_config", reason="Low success rate")
"""

import json
import logging
import os
import urllib.request
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# AI config for evolution analysis
EVOLUTION_CONFIG = {
    "base_url": "https://coding.dashscope.aliyuncs.com/v1",
    "api_key": os.environ.get("DASHSCOPE_API_KEY"),
    "model": "qwen3-coder-next",
    "max_tokens": 2000,
    "temperature": 0.2
}


class SkillVersion:
    """Represents a single version of a skill."""

    def __init__(self, version_data: Dict[str, Any]):
        self.version = version_data.get('version', 'v1')
        self.name = version_data.get('name', '')
        self.description = version_data.get('description', '')
        self.triggers = version_data.get('triggers', '')
        self.steps = version_data.get('steps', '')
        self.examples = version_data.get('examples', '')
        self.created_at = version_data.get('created_at', '')
        self.deprecated = version_data.get('deprecated', False)
        self.deprecated_reason = version_data.get('deprecated_reason', '')
        self.deprecated_at = version_data.get('deprecated_at', '')
        self.success_rate = version_data.get('success_rate', 0.0)
        self.execution_count = version_data.get('execution_count', 0)
        self.parent_version = version_data.get('parent_version', None)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'version': self.version,
            'name': self.name,
            'description': self.description,
            'triggers': self.triggers,
            'steps': self.steps,
            'examples': self.examples,
            'created_at': self.created_at,
            'deprecated': self.deprecated,
            'deprecated_reason': self.deprecated_reason,
            'deprecated_at': self.deprecated_at,
            'success_rate': self.success_rate,
            'execution_count': self.execution_count,
            'parent_version': self.parent_version
        }


class SkillEvolution:
    """
    Manages versioned skill evolution.

    Features:
    1. Create new versions (v1 → v2 → v3)
    2. Preserve all versions (never overwrite)
    3. Track lineage (parent → child)
    4. Deprecate old versions
    5. Analyze evolution history
    """

    def __init__(self, memory_manager=None):
        self._memory_manager = memory_manager
        self._evolution_dir = Path(__file__).parent / "skill_evolution"
        self._evolution_dir.mkdir(parents=True, exist_ok=True)
        self._api_config = EVOLUTION_CONFIG

        # Evolution tracking
        self._evolution_history = []

    def get_skill_versions(self, skill_name: str) -> List[SkillVersion]:
        """Get all versions of a skill."""
        skill_file = self._get_skill_file(skill_name)

        if not skill_file.exists():
            return []

        with open(skill_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        versions = []
        for v_data in data.get('versions', []):
            versions.append(SkillVersion(v_data))

        return versions

    def get_latest_version(self, skill_name: str) -> Optional[SkillVersion]:
        """Get the latest (non-deprecated) version of a skill."""
        versions = self.get_skill_versions(skill_name)

        if not versions:
            return None

        # Return latest non-deprecated version
        for version in reversed(versions):
            if not version.deprecated:
                return version

        # All deprecated, return the latest anyway
        return versions[-1] if versions else None

    def evolve_skill(
        self,
        skill_name: str,
        reason: str = "Performance improvement",
        execution_data: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evolve a skill to a new version.

        Args:
            skill_name: Name of the skill to evolve
            reason: Reason for evolution
            execution_data: Historical execution data for analysis

        Returns:
            Evolution result with new version info
        """
        logger.info(f"Starting evolution for {skill_name}: {reason}")

        # Get current version
        current_version = self.get_latest_version(skill_name)

        if not current_version:
            return {
                'success': False,
                'error': f'Skill {skill_name} not found'
            }

        # Analyze and create new version
        new_version_data = self._analyze_and_evolve(
            current_version,
            reason,
            execution_data
        )

        if not new_version_data:
            return {
                'success': False,
                'error': 'Failed to create new version'
            }

        # Get all versions and add new one
        versions = self.get_skill_versions(skill_name)

        # Mark current version as deprecated
        if current_version:
            current_version.deprecated = True
            current_version.deprecated_reason = reason
            current_version.deprecated_at = datetime.now().isoformat()

        # Create new version
        new_version = SkillVersion({
            **new_version_data,
            'version': self._increment_version(current_version.version),
            'created_at': datetime.now().isoformat(),
            'parent_version': current_version.version
        })

        # Save all versions
        self._save_skill_versions(skill_name, versions + [new_version])

        # Record evolution
        evolution_record = {
            'timestamp': datetime.now().isoformat(),
            'skill_name': skill_name,
            'reason': reason,
            'from_version': current_version.version if current_version else 'v0',
            'to_version': new_version.version,
            'old_success_rate': current_version.success_rate if current_version else 0,
            'new_success_rate': new_version.success_rate if new_version else 0
        }
        self._evolution_history.append(evolution_record)
        self._write_evolution_log(evolution_record)

        logger.info(f"Evolved {skill_name}: {current_version.version} → {new_version.version}")

        return {
            'success': True,
            'skill_name': skill_name,
            'old_version': current_version.version if current_version else None,
            'new_version': new_version.version,
            'evolution_record': evolution_record
        }

    def _analyze_and_evolve(
        self,
        current_version: SkillVersion,
        reason: str,
        execution_data: List[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Use AI to analyze and create improved version."""

        # Prepare analysis prompt
        execution_summary = ""
        if execution_data:
            successes = sum(1 for e in execution_data if e.get('success', False))
            total = len(execution_data)
            execution_summary = f"Recent executions: {successes}/{total} successful\n"

            # Add failure patterns
            failures = [e for e in execution_data if not e.get('success', False)]
            if failures:
                execution_summary += f"Common failure patterns:\n"
                for f in failures[:5]:
                    execution_summary += f"- {f.get('error', 'Unknown error')}\n"

        prompt = f"""Analyze this skill and suggest improvements based on execution data.

Current Skill (version {current_version.version}):
- Name: {current_version.name}
- Description: {current_version.description}
- Triggers: {current_version.triggers}
- Steps: {current_version.steps}
- Examples: {current_version.examples}
- Success Rate: {current_version.success_rate:.0%}
- Execution Count: {current_version.execution_count}

Evolution Reason: {reason}

{execution_summary}

Suggest improvements to:
1. Make description clearer
2. Make triggers more actionable
3. Improve steps for better success rate
4. Add better examples

Return JSON with improved skill (only the fields that changed):
{{
  "name": "...",
  "description": "...",
  "triggers": "...",
  "steps": "...",
  "examples": "...",
  "success_rate": 0.0,
  "execution_count": 0
}}
"""

        # Call AI
        try:
            improved = self._call_ai(prompt)
            if improved:
                # Merge with current version
                return {
                    'name': improved.get('name', current_version.name),
                    'description': improved.get('description', current_version.description),
                    'triggers': improved.get('triggers', current_version.triggers),
                    'steps': improved.get('steps', current_version.steps),
                    'examples': improved.get('examples', current_version.examples),
                    'success_rate': improved.get('success_rate', current_version.success_rate),
                    'execution_count': current_version.execution_count
                }
        except Exception as e:
            logger.error(f"AI evolution analysis failed: {e}")

        # Fallback: minor improvement
        return {
            'name': current_version.name,
            'description': current_version.description,
            'triggers': current_version.triggers,
            'steps': current_version.steps,
            'examples': current_version.examples,
            'success_rate': current_version.success_rate,
            'execution_count': current_version.execution_count
        }

    def _call_ai(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call AI for analysis."""
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

                # Parse JSON
                content = content.strip()
                if content.startswith('```'):
                    content = content.split('```')[1]
                    if content.startswith('json'):
                        content = content[4:]
                content = content.strip()

                return json.loads(content)
        except Exception as e:
            logger.error(f"AI call failed: {e}")
            return None

    def _get_skill_file(self, skill_name: str) -> Path:
        """Get path to skill evolution file."""
        safe_name = skill_name.replace('/', '_').replace(' ', '_')
        return self._evolution_dir / f"{safe_name}.json"

    def _save_skill_versions(self, skill_name: str, versions: List[SkillVersion]):
        """Save all versions of a skill."""
        skill_file = self._get_skill_file(skill_name)

        data = {
            'skill_name': skill_name,
            'versions': [v.to_dict() for v in versions],
            'total_versions': len(versions),
            'latest_version': versions[-1].version if versions else None
        }

        with open(skill_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _increment_version(self, version: str) -> str:
        """Increment version number (v1 → v2)."""
        if version.startswith('v'):
            try:
                num = int(version[1:])
                return f'v{num + 1}'
            except ValueError:
                pass
        return 'v1'

    def _write_evolution_log(self, record: Dict[str, Any]):
        """Write evolution log entry."""
        log_file = self._evolution_dir / 'evolution_log.md'

        entry = f"""## {record['timestamp']}

- **Skill**: {record['skill_name']}
- **Version**: {record['from_version']} → {record['to_version']}
- **Reason**: {record['reason']}
- **Success Rate**: {record['old_success_rate']:.0%} → {record['new_success_rate']:.0%}

---
"""

        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(entry)

    def get_evolution_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get evolution history."""
        return self._evolution_history[-limit:]

    def get_evolution_stats(self) -> Dict[str, Any]:
        """Get evolution statistics."""
        total_evolutions = len(self._evolution_history)
        skills_evolved = len(set(e['skill_name'] for e in self._evolution_history))

        avg_improvement = 0
        if self._evolution_history:
            improvements = [
                e['new_success_rate'] - e['old_success_rate']
                for e in self._evolution_history
                if e.get('new_success_rate') and e.get('old_success_rate')
            ]
            avg_improvement = sum(improvements) / len(improvements) if improvements else 0

        return {
            'total_evolutions': total_evolutions,
            'skills_evolved': skills_evolved,
            'avg_success_rate_improvement': avg_improvement
        }

    def get_skill_lineage(self, skill_name: str) -> Dict[str, Any]:
        """
        Get complete version lineage of a skill.

        Args:
            skill_name: Name of the skill

        Returns:
            Lineage info including version tree and evolution path
        """
        versions = self.get_skill_versions(skill_name)

        if not versions:
            return {
                'success': False,
                'error': f'Skill {skill_name} not found',
                'lineage': None
            }

        # Build lineage structure
        lineage = {
            'skill_name': skill_name,
            'total_versions': len(versions),
            'versions': [],
            'evolution_path': [],
            'current_version': None,
            'root_version': None
        }

        # Find root and current versions
        root_version = versions[0].version if versions else None
        current_version = None
        for v in reversed(versions):
            if not v.deprecated:
                current_version = v.version
                break

        if not current_version and versions:
            current_version = versions[-1].version

        lineage['root_version'] = root_version
        lineage['current_version'] = current_version

        # Build version list with lineage info
        for v in versions:
            version_info = {
                'version': v.version,
                'created_at': v.created_at,
                'deprecated': v.deprecated,
                'deprecated_reason': v.deprecated_reason,
                'parent_version': v.parent_version,
                'success_rate': v.success_rate
            }
            lineage['versions'].append(version_info)

        # Build evolution path (v1 -> v2 -> v3 ...)
        evolution_path = [v.version for v in versions]
        lineage['evolution_path'] = evolution_path

        # Build version tree (parent-child relationships)
        version_tree = {}
        for v in versions:
            parent = v.parent_version
            if parent:
                if parent not in version_tree:
                    version_tree[parent] = []
                version_tree[parent].append(v.version)

        lineage['version_tree'] = version_tree

        return {
            'success': True,
            'lineage': lineage
        }

    def rollback_skill(
        self,
        skill_name: str,
        target_version: str,
        reason: str = "Manual rollback"
    ) -> Dict[str, Any]:
        """
        Rollback a skill to a specific historical version.

        Args:
            skill_name: Name of the skill to rollback
            target_version: Version to rollback to (e.g., 'v2')
            reason: Reason for rollback

        Returns:
            Rollback result with audit info
        """
        logger.info(f"Starting rollback for {skill_name} to {target_version}: {reason}")

        versions = self.get_skill_versions(skill_name)

        if not versions:
            return {
                'success': False,
                'error': f'Skill {skill_name} not found'
            }

        # Find target version
        target = None
        for v in versions:
            if v.version == target_version:
                target = v
                break

        if not target:
            available_versions = [v.version for v in versions]
            return {
                'success': False,
                'error': f'Version {target_version} not found',
                'available_versions': available_versions
            }

        # Get current version
        current_version = self.get_latest_version(skill_name)

        if current_version and current_version.version == target_version:
            return {
                'success': False,
                'error': f'Already at version {target_version}'
            }

        # Create rollback version (new version based on target)
        rollback_version_num = self._increment_version(versions[-1].version)

        rollback_version = SkillVersion({
            'version': rollback_version_num,
            'name': target.name,
            'description': target.description,
            'triggers': target.triggers,
            'steps': target.steps,
            'examples': target.examples,
            'created_at': datetime.now().isoformat(),
            'parent_version': current_version.version if current_version else None,
            'rollback_from': target_version,
            'rollback_reason': reason,
            'is_rollback': True,
            'success_rate': 0.0,
            'execution_count': 0
        })

        # Mark current version as deprecated if exists
        if current_version:
            current_version.deprecated = True
            current_version.deprecated_reason = f"Rolled back: {reason}"
            current_version.deprecated_at = datetime.now().isoformat()

        # Save all versions including rollback
        all_versions = versions + [rollback_version]
        self._save_skill_versions(skill_name, all_versions)

        # Record audit log
        audit_record = {
            'timestamp': datetime.now().isoformat(),
            'action': 'rollback',
            'skill_name': skill_name,
            'from_version': current_version.version if current_version else None,
            'to_version': rollback_version_num,
            'restored_from_version': target_version,
            'reason': reason,
            'operator': 'system'
        }
        self._write_audit_log(audit_record)

        # Also write to evolution log
        evolution_record = {
            'timestamp': audit_record['timestamp'],
            'skill_name': skill_name,
            'reason': f"ROLLBACK: {reason}",
            'from_version': current_version.version if current_version else 'v0',
            'to_version': rollback_version_num,
            'old_success_rate': current_version.success_rate if current_version else 0,
            'new_success_rate': 0
        }
        self._evolution_history.append(evolution_record)
        self._write_evolution_log(evolution_record)

        logger.info(f"Rolled back {skill_name}: {current_version.version if current_version else 'none'} → {rollback_version_num}")

        return {
            'success': True,
            'skill_name': skill_name,
            'previous_version': current_version.version if current_version else None,
            'new_version': rollback_version_num,
            'restored_from': target_version,
            'reason': reason,
            'audit_record': audit_record
        }

    def get_version_diff(
        self,
        skill_name: str,
        version1: str,
        version2: str
    ) -> Dict[str, Any]:
        """
        Compare two versions of a skill and show differences.

        Args:
            skill_name: Name of the skill
            version1: First version (e.g., 'v1')
            version2: Second version (e.g., 'v2')

        Returns:
            Diff report showing what changed between versions
        """
        versions = self.get_skill_versions(skill_name)

        if not versions:
            return {
                'success': False,
                'error': f'Skill {skill_name} not found'
            }

        # Find both versions
        v1 = None
        v2 = None
        for v in versions:
            if v.version == version1:
                v1 = v
            if v.version == version2:
                v2 = v

        if not v1:
            available = [v.version for v in versions]
            return {
                'success': False,
                'error': f'Version {version1} not found',
                'available_versions': available
            }

        if not v2:
            available = [v.version for v in versions]
            return {
                'success': False,
                'error': f'Version {version2} not found',
                'available_versions': available
            }

        # Compare fields
        diff = {
            'skill_name': skill_name,
            'version1': version1,
            'version2': version2,
            'changed_fields': [],
            'unchanged_fields': [],
            'details': {}
        }

        fields_to_compare = [
            ('name', 'Name'),
            ('description', 'Description'),
            ('triggers', 'Triggers'),
            ('steps', 'Steps'),
            ('examples', 'Examples')
        ]

        for field, label in fields_to_compare:
            val1 = getattr(v1, field, '')
            val2 = getattr(v2, field, '')

            if val1 != val2:
                diff['changed_fields'].append(label)
                diff['details'][field] = {
                    f'{version1}': val1,
                    f'{version2}': val2,
                    'change_type': 'modified'
                }
            else:
                diff['unchanged_fields'].append(label)

        # Compare metadata
        if v1.success_rate != v2.success_rate:
            diff['details']['success_rate'] = {
                f'{version1}': v1.success_rate,
                f'{version2}': v2.success_rate
            }

        if v1.execution_count != v2.execution_count:
            diff['details']['execution_count'] = {
                f'{version1}': v1.execution_count,
                f'{version2}': v2.execution_count
            }

        # Add timestamp info
        diff['version1_created'] = v1.created_at
        diff['version2_created'] = v2.created_at

        # Summary
        diff['summary'] = {
            'total_changes': len(diff['changed_fields']),
            'fields_modified': diff['changed_fields']
        }

        return {
            'success': True,
            'diff': diff
        }

    def _write_audit_log(self, record: Dict[str, Any]):
        """Write audit log entry for rollback and other operations."""
        audit_file = self._evolution_dir / 'audit_log.jsonl'

        with open(audit_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')


# Global instance
_default_evolution: Optional[SkillEvolution] = None


def get_skill_evolution(memory_manager=None) -> SkillEvolution:
    """Get or create SkillEvolution instance."""
    global _default_evolution
    if _default_evolution is None:
        _default_evolution = SkillEvolution(memory_manager)
    return _default_evolution


def evolve_skill(
    skill_name: str,
    reason: str = "Performance improvement",
    execution_data: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Convenience function to evolve a skill."""
    evolution = get_skill_evolution()
    return evolution.evolve_skill(skill_name, reason, execution_data)


def get_skill_lineage(skill_name: str) -> Dict[str, Any]:
    """Convenience function to get skill lineage."""
    evolution = get_skill_evolution()
    return evolution.get_skill_lineage(skill_name)


def rollback_skill(
    skill_name: str,
    target_version: str,
    reason: str = "Manual rollback"
) -> Dict[str, Any]:
    """Convenience function to rollback a skill."""
    evolution = get_skill_evolution()
    return evolution.rollback_skill(skill_name, target_version, reason)


def get_version_diff(
    skill_name: str,
    version1: str,
    version2: str
) -> Dict[str, Any]:
    """Convenience function to compare two versions."""
    evolution = get_skill_evolution()
    return evolution.get_version_diff(skill_name, version1, version2)

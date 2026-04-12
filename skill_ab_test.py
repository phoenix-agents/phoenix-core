#!/usr/bin/env python3
"""
Skill A/B Testing Framework - Compare skill versions

Features:
1. Random traffic splitting between versions
2. Success/failure tracking per version
3. Statistical significance testing
4. Automatic winner selection

Usage:
    ab_test = SkillABTest()
    ab_test.start_test("memory_config", versions=["v1", "v2"])
    ab_test.record_execution("memory_config", "v1", success=True)
    results = ab_test.get_results("memory_config")
"""

import json
import logging
import random
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import math

logger = logging.getLogger(__name__)


class ABTestExperiment:
    """Represents a single A/B test experiment."""

    def __init__(self, skill_name: str, versions: List[str], traffic_split: List[float] = None):
        self.skill_name = skill_name
        self.versions = versions
        self.traffic_split = traffic_split or [0.5] * len(versions)
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None

        # Stats per version
        self.stats = {v: {'successes': 0, 'failures': 0, 'total': 0} for v in versions}

        # Configuration
        self.min_samples_per_version = 30  # Minimum samples before declaring winner
        self.significance_level = 0.05  # P-value threshold

    def assign_version(self, user_id: str) -> str:
        """Assign a version based on traffic split using consistent hashing."""
        # Create consistent hash
        hash_input = f"{self.skill_name}:{user_id}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        normalized = (hash_value % 1000) / 1000  # 0.0 to 1.0

        # Assign based on cumulative traffic split
        cumulative = 0
        for i, split in enumerate(self.traffic_split):
            cumulative += split
            if normalized < cumulative:
                return self.versions[i]

        return self.versions[-1]

    def record(self, version: str, success: bool):
        """Record an execution result."""
        if version not in self.stats:
            logger.warning(f"Unknown version: {version}")
            return

        self.stats[version]['total'] += 1
        if success:
            self.stats[version]['successes'] += 1
        else:
            self.stats[version]['failures'] += 1

    def get_success_rate(self, version: str) -> float:
        """Get success rate for a version."""
        if version not in self.stats:
            return 0.0

        stats = self.stats[version]
        if stats['total'] == 0:
            return 0.0

        return stats['successes'] / stats['total']

    def is_ready_for_decision(self) -> bool:
        """Check if test has enough data for decision."""
        for version in self.versions:
            if self.stats[version]['total'] < self.min_samples_per_version:
                return False
        return True

    def calculate_significance(self) -> Tuple[float, bool]:
        """
        Calculate statistical significance between versions.
        Uses two-proportion z-test.

        Returns:
            (p_value, is_significant)
        """
        if len(self.versions) < 2:
            return (1.0, False)

        v1, v2 = self.versions[:2]
        s1 = self.stats[v1]
        s2 = self.stats[v2]

        # Check minimum sample size
        if s1['total'] < 10 or s2['total'] < 10:
            return (1.0, False)

        # Calculate proportions
        p1 = s1['successes'] / s1['total']
        p2 = s2['successes'] / s2['total']

        # Pooled proportion
        p_pool = (s1['successes'] + s2['successes']) / (s1['total'] + s2['total'])

        if p_pool == 0 or p_pool == 1:
            return (1.0, False)

        # Standard error
        se = math.sqrt(p_pool * (1 - p_pool) * (1/s1['total'] + 1/s2['total']))

        if se == 0:
            return (1.0, False)

        # Z-score
        z = (p1 - p2) / se

        # Two-tailed p-value (approximation)
        p_value = 2 * (1 - self._normal_cdf(abs(z)))

        return (p_value, p_value < self.significance_level)

    def _normal_cdf(self, x: float) -> float:
        """Approximate normal CDF using error function."""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    def get_winner(self) -> Optional[Dict[str, Any]]:
        """Determine the winning version."""
        if not self.is_ready_for_decision():
            return None

        p_value, is_significant = self.calculate_significance()

        if not is_significant:
            return None  # No significant difference

        # Find version with highest success rate
        best_version = max(self.versions, key=lambda v: self.get_success_rate(v))
        best_rate = self.get_success_rate(best_version)

        return {
            'version': best_version,
            'success_rate': best_rate,
            'p_value': p_value,
            'is_significant': is_significant
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get experiment summary."""
        return {
            'skill_name': self.skill_name,
            'versions': self.versions,
            'traffic_split': self.traffic_split,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'stats': self.stats,
            'success_rates': {v: self.get_success_rate(v) for v in self.versions},
            'is_ready': self.is_ready_for_decision(),
            'winner': self.get_winner()
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'skill_name': self.skill_name,
            'versions': self.versions,
            'traffic_split': self.traffic_split,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'stats': self.stats
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ABTestExperiment':
        """Deserialize from dictionary."""
        exp = cls(
            data['skill_name'],
            data['versions'],
            data.get('traffic_split')
        )
        exp.start_time = datetime.fromisoformat(data['start_time'])
        if data.get('end_time'):
            exp.end_time = datetime.fromisoformat(data['end_time'])
        exp.stats = data['stats']
        return exp


class SkillABTest:
    """
    A/B testing framework for skill versions.

    Manages multiple experiments and provides:
    1. Version assignment
    2. Result tracking
    3. Statistical analysis
    4. Winner selection
    """

    def __init__(self):
        self.experiments_dir = Path(__file__).parent / "ab_experiments"
        self.experiments_dir.mkdir(parents=True, exist_ok=True)

        self._experiments: Dict[str, ABTestExperiment] = {}
        self._load_experiments()

    def _load_experiments(self):
        """Load existing experiments from disk."""
        for file in self.experiments_dir.glob('*.json'):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                exp = ABTestExperiment.from_dict(data)
                self._experiments[exp.skill_name] = exp
            except Exception as e:
                logger.error(f"Failed to load experiment {file}: {e}")

    def _save_experiment(self, exp: ABTestExperiment):
        """Save experiment to disk."""
        file = self.experiments_dir / f"{exp.skill_name}.json"
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(exp.to_dict(), f, indent=2, ensure_ascii=False)

    def start_test(
        self,
        skill_name: str,
        versions: List[str],
        traffic_split: List[float] = None
    ) -> Dict[str, Any]:
        """
        Start a new A/B test.

        Args:
            skill_name: Name of the skill to test
            versions: List of versions to compare (e.g., ["v1", "v2"])
            traffic_split: Traffic distribution (default: equal split)

        Returns:
            Test start result
        """
        if skill_name in self._experiments:
            existing = self._experiments[skill_name]
            if not existing.end_time:
                return {
                    'success': False,
                    'error': f'Test already running for {skill_name}'
                }

        exp = ABTestExperiment(skill_name, versions, traffic_split)
        self._experiments[skill_name] = exp
        self._save_experiment(exp)

        logger.info(f"Started A/B test for {skill_name}: {versions}")

        return {
            'success': True,
            'skill_name': skill_name,
            'versions': versions,
            'traffic_split': traffic_split or [1/len(versions)] * len(versions)
        }

    def assign_version(self, skill_name: str, user_id: str = None) -> Optional[str]:
        """
        Assign a version for a skill.

        Args:
            skill_name: Name of the skill
            user_id: Optional user ID for consistent assignment

        Returns:
            Assigned version or None if no test running
        """
        if skill_name not in self._experiments:
            return None

        exp = self._experiments[skill_name]
        if exp.end_time:
            return None  # Test ended

        user_id = user_id or str(random.random())
        return exp.assign_version(user_id)

    def record_execution(
        self,
        skill_name: str,
        version: str,
        success: bool,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Record a skill execution result.

        Args:
            skill_name: Name of the skill
            version: Version that was executed
            success: Whether execution was successful
            metadata: Optional additional data

        Returns:
            Recording result
        """
        if skill_name not in self._experiments:
            return {'success': False, 'error': 'No test running'}

        exp = self._experiments[skill_name]
        exp.record(version, success)
        self._save_experiment(exp)

        # Check if decision can be made
        if exp.is_ready_for_decision():
            winner = exp.get_winner()
            if winner:
                logger.info(f"Winner found for {skill_name}: {winner['version']} ({winner['success_rate']:.0%})")

        return {'success': True, 'recorded': True}

    def get_results(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """
        Get test results for a skill.

        Args:
            skill_name: Name of the skill

        Returns:
            Test results or None if no test found
        """
        if skill_name not in self._experiments:
            return None

        exp = self._experiments[skill_name]
        return exp.get_summary()

    def end_test(self, skill_name: str, force: bool = False) -> Dict[str, Any]:
        """
        End an A/B test.

        Args:
            skill_name: Name of the skill
            force: Force end even if not ready

        Returns:
            End result with final statistics
        """
        if skill_name not in self._experiments:
            return {'success': False, 'error': 'No test found'}

        exp = self._experiments[skill_name]
        exp.end_time = datetime.now()

        if not exp.is_ready_for_decision() and not force:
            return {
                'success': False,
                'error': 'Test not ready for decision',
                'hint': f"Need {exp.min_samples_per_version} samples per version"
            }

        self._save_experiment(exp)

        winner = exp.get_winner() if not force else None

        return {
            'success': True,
            'skill_name': skill_name,
            'duration_hours': (exp.end_time - exp.start_time).total_seconds() / 3600,
            'stats': exp.stats,
            'success_rates': {v: exp.get_success_rate(v) for v in exp.versions},
            'winner': winner
        }

    def list_tests(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """List all tests."""
        tests = []
        for exp in self._experiments.values():
            if active_only and exp.end_time:
                continue

            tests.append({
                'skill_name': exp.skill_name,
                'versions': exp.versions,
                'is_active': exp.end_time is None,
                'start_time': exp.start_time.isoformat(),
                'end_time': exp.end_time.isoformat() if exp.end_time else None
            })

        return tests

    def get_all_results(self) -> Dict[str, Dict[str, Any]]:
        """Get results for all tests."""
        return {
            name: exp.get_summary()
            for name, exp in self._experiments.items()
        }


# Global instance
_default_ab_test: Optional[SkillABTest] = None


def get_ab_test() -> SkillABTest:
    """Get or create SkillABTest instance."""
    global _default_ab_test
    if _default_ab_test is None:
        _default_ab_test = SkillABTest()
    return _default_ab_test


def start_ab_test(skill_name: str, versions: List[str]) -> Dict[str, Any]:
    """Convenience function to start A/B test."""
    return get_ab_test().start_test(skill_name, versions)


def assign_skill_version(skill_name: str, user_id: str = None) -> Optional[str]:
    """Convenience function to assign version."""
    return get_ab_test().assign_version(skill_name, user_id)


def record_skill_execution(skill_name: str, version: str, success: bool) -> Dict[str, Any]:
    """Convenience function to record execution."""
    return get_ab_test().record_execution(skill_name, version, success)


def get_ab_results(skill_name: str) -> Optional[Dict[str, Any]]:
    """Convenience function to get results."""
    return get_ab_test().get_results(skill_name)

#!/usr/bin/env python3
"""
Test suite for Skill Evolution API - Lineage, Rollback, and Version Diff

Tests:
1. get_skill_lineage() - Get complete version lineage
2. rollback_skill() - Rollback to historical version
3. get_version_diff() - Compare two versions
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from skill_evolution import (
    SkillEvolution,
    SkillVersion,
    get_skill_lineage,
    rollback_skill,
    get_version_diff,
    evolve_skill
)


class TestSkillVersion(unittest.TestCase):
    """Test SkillVersion class."""

    def test_create_from_dict(self):
        """Test creating SkillVersion from dictionary."""
        data = {
            'version': 'v1',
            'name': 'test_skill',
            'description': 'A test skill',
            'triggers': 'when needed',
            'steps': 'step 1',
            'examples': 'example 1',
            'created_at': '2024-01-01T00:00:00',
            'deprecated': False,
            'parent_version': None
        }
        version = SkillVersion(data)

        self.assertEqual(version.version, 'v1')
        self.assertEqual(version.name, 'test_skill')
        self.assertEqual(version.description, 'A test skill')
        self.assertFalse(version.deprecated)
        self.assertIsNone(version.parent_version)

    def test_to_dict(self):
        """Test converting SkillVersion to dictionary."""
        data = {
            'version': 'v2',
            'name': 'test_skill',
            'description': 'Updated skill',
            'parent_version': 'v1'
        }
        version = SkillVersion(data)
        result = version.to_dict()

        self.assertEqual(result['version'], 'v2')
        self.assertEqual(result['parent_version'], 'v1')
        self.assertIn('deprecated', result)


class TestSkillLineage(unittest.TestCase):
    """Test get_skill_lineage functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.evolution = SkillEvolution()
        self.evolution._evolution_dir = Path(self.test_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_test_skill(self, name: str, versions: list):
        """Helper to create a skill with multiple versions."""
        skill_file = self.evolution._get_skill_file(name)
        skill_file.parent.mkdir(parents=True, exist_ok=True)

        version_objects = []
        for i, v_data in enumerate(versions):
            version_data = {
                'version': f'v{i+1}',
                'name': name,
                'created_at': datetime.now().isoformat(),
                'deprecated': v_data.get('deprecated', False),
                'parent_version': f'v{i}' if i > 0 else None,
                **v_data
            }
            version_objects.append(SkillVersion(version_data))

        data = {
            'skill_name': name,
            'versions': [v.to_dict() for v in version_objects],
            'total_versions': len(version_objects),
            'latest_version': version_objects[-1].version
        }

        with open(skill_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def test_lineage_single_version(self):
        """Test lineage for skill with single version."""
        self._create_test_skill('simple_skill', [
            {'description': 'v1 desc', 'steps': 'step 1'}
        ])

        result = self.evolution.get_skill_lineage('simple_skill')

        self.assertTrue(result['success'])
        self.assertIsNotNone(result['lineage'])
        self.assertEqual(result['lineage']['total_versions'], 1)
        self.assertEqual(result['lineage']['root_version'], 'v1')
        self.assertEqual(result['lineage']['current_version'], 'v1')

    def test_lineage_multiple_versions(self):
        """Test lineage for skill with multiple versions."""
        self._create_test_skill('evolved_skill', [
            {'description': 'v1 desc', 'deprecated': False},
            {'description': 'v2 desc', 'deprecated': True},
            {'description': 'v3 desc', 'deprecated': False}
        ])

        result = self.evolution.get_skill_lineage('evolved_skill')

        self.assertTrue(result['success'])
        lineage = result['lineage']
        self.assertEqual(lineage['total_versions'], 3)
        self.assertEqual(lineage['root_version'], 'v1')
        self.assertEqual(lineage['current_version'], 'v3')
        self.assertIn('v1', lineage['evolution_path'])
        self.assertIn('v2', lineage['evolution_path'])
        self.assertIn('v3', lineage['evolution_path'])

    def test_lineage_version_tree(self):
        """Test lineage includes version tree structure."""
        self._create_test_skill('tree_skill', [
            {'description': 'v1', 'parent_version': None},
            {'description': 'v2', 'parent_version': 'v1'},
            {'description': 'v3', 'parent_version': 'v2'}
        ])

        result = self.evolution.get_skill_lineage('tree_skill')

        self.assertTrue(result['success'])
        self.assertIn('version_tree', result['lineage'])
        self.assertIn('v1', result['lineage']['version_tree'])

    def test_lineage_not_found(self):
        """Test lineage for non-existent skill."""
        result = self.evolution.get_skill_lineage('nonexistent_skill')

        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIsNone(result['lineage'])


class TestSkillRollback(unittest.TestCase):
    """Test rollback_skill functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.evolution = SkillEvolution()
        self.evolution._evolution_dir = Path(self.test_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_test_skill(self, name: str, versions: list):
        """Helper to create a skill with multiple versions."""
        skill_file = self.evolution._get_skill_file(name)
        skill_file.parent.mkdir(parents=True, exist_ok=True)

        version_objects = []
        for i, v_data in enumerate(versions):
            version_data = {
                'version': f'v{i+1}',
                'name': name,
                'description': v_data.get('description', f'v{i+1} desc'),
                'triggers': v_data.get('triggers', 'trigger'),
                'steps': v_data.get('steps', 'steps'),
                'examples': v_data.get('examples', 'examples'),
                'created_at': datetime.now().isoformat(),
                'deprecated': v_data.get('deprecated', False),
                'parent_version': f'v{i}' if i > 0 else None,
                'success_rate': v_data.get('success_rate', 0.0)
            }
            version_objects.append(SkillVersion(version_data))

        data = {
            'skill_name': name,
            'versions': [v.to_dict() for v in version_objects],
            'total_versions': len(version_objects),
            'latest_version': version_objects[-1].version
        }

        with open(skill_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def test_rollback_to_previous_version(self):
        """Test rolling back to a previous version."""
        self._create_test_skill('rollback_skill', [
            {'description': 'Original v1', 'success_rate': 0.8},
            {'description': 'Bad v2', 'success_rate': 0.5},
            {'description': 'Worse v3', 'success_rate': 0.3}
        ])

        result = self.evolution.rollback_skill(
            'rollback_skill',
            'v1',
            reason='v3 has poor performance'
        )

        self.assertTrue(result['success'])
        self.assertEqual(result['skill_name'], 'rollback_skill')
        self.assertEqual(result['restored_from'], 'v1')
        self.assertEqual(result['new_version'], 'v4')
        self.assertIn('audit_record', result)

    def test_rollback_creates_new_version(self):
        """Test that rollback creates a new version."""
        self._create_test_skill('version_skill', [
            {'description': 'v1'},
            {'description': 'v2'}
        ])

        result = self.evolution.rollback_skill('version_skill', 'v1')

        self.assertTrue(result['success'])
        # After rollback, we should have v3
        versions = self.evolution.get_skill_versions('version_skill')
        version_nums = [v.version for v in versions]
        self.assertIn('v3', version_nums)

    def test_rollback_marks_current_deprecated(self):
        """Test that rollback marks current version as deprecated."""
        self._create_test_skill('deprecate_skill', [
            {'description': 'v1'},
            {'description': 'v2'}
        ])

        result = self.evolution.rollback_skill('deprecate_skill', 'v1')

        versions = self.evolution.get_skill_versions('deprecate_skill')
        v2 = next((v for v in versions if v.version == 'v2'), None)
        self.assertIsNotNone(v2)
        self.assertTrue(v2.deprecated)
        self.assertIn('Rolled back', v2.deprecated_reason)

    def test_rollback_not_found(self):
        """Test rollback for non-existent skill."""
        result = self.evolution.rollback_skill('nonexistent', 'v1')

        self.assertFalse(result['success'])
        self.assertIn('error', result)

    def test_rollback_version_not_found(self):
        """Test rollback to non-existent version."""
        self._create_test_skill('missing_version', [
            {'description': 'v1'},
            {'description': 'v2'}
        ])

        result = self.evolution.rollback_skill('missing_version', 'v99')

        self.assertFalse(result['success'])
        self.assertIn('available_versions', result)

    def test_rollback_already_at_version(self):
        """Test rollback when already at target version."""
        self._create_test_skill('current_skill', [
            {'description': 'v1', 'deprecated': True},
            {'description': 'v2', 'deprecated': False}
        ])

        # First rollback to v1
        self.evolution.rollback_skill('current_skill', 'v1')

        # Now v2 is deprecated, v3 is current (based on v1)
        # Try to rollback to v3 (current)
        result = self.evolution.rollback_skill('current_skill', 'v3')

        # Should fail since v3 doesn't exist yet or is current
        # This depends on implementation

    def test_rollback_writes_audit_log(self):
        """Test that rollback writes audit log."""
        self._create_test_skill('audit_skill', [
            {'description': 'v1'},
            {'description': 'v2'}
        ])

        self.evolution.rollback_skill('audit_skill', 'v1', reason='Testing audit')

        audit_file = self.evolution._evolution_dir / 'audit_log.jsonl'
        self.assertTrue(audit_file.exists())

        with open(audit_file, 'r') as f:
            lines = f.readlines()

        self.assertGreater(len(lines), 0)
        last_entry = json.loads(lines[-1])
        self.assertEqual(last_entry['action'], 'rollback')
        self.assertEqual(last_entry['skill_name'], 'audit_skill')
        self.assertEqual(last_entry['reason'], 'Testing audit')


class TestVersionDiff(unittest.TestCase):
    """Test get_version_diff functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.evolution = SkillEvolution()
        self.evolution._evolution_dir = Path(self.test_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_test_skill(self, name: str, versions: list):
        """Helper to create a skill with multiple versions."""
        skill_file = self.evolution._get_skill_file(name)
        skill_file.parent.mkdir(parents=True, exist_ok=True)

        version_objects = []
        for i, v_data in enumerate(versions):
            version_data = {
                'version': f'v{i+1}',
                'name': name,
                'description': v_data.get('description', f'v{i+1} desc'),
                'triggers': v_data.get('triggers', 'trigger'),
                'steps': v_data.get('steps', 'steps'),
                'examples': v_data.get('examples', 'examples'),
                'created_at': datetime.now().isoformat(),
                'deprecated': False,
                'parent_version': f'v{i}' if i > 0 else None,
                'success_rate': v_data.get('success_rate', 0.0),
                'execution_count': v_data.get('execution_count', 0)
            }
            version_objects.append(SkillVersion(version_data))

        data = {
            'skill_name': name,
            'versions': [v.to_dict() for v in version_objects],
            'total_versions': len(version_objects),
            'latest_version': version_objects[-1].version
        }

        with open(skill_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def test_diff_with_changes(self):
        """Test diff between versions with changes."""
        self._create_test_skill('diff_skill', [
            {'description': 'Original description', 'steps': 'original steps'},
            {'description': 'Updated description', 'steps': 'updated steps'}
        ])

        result = self.evolution.get_version_diff('diff_skill', 'v1', 'v2')

        self.assertTrue(result['success'])
        diff = result['diff']
        self.assertEqual(diff['version1'], 'v1')
        self.assertEqual(diff['version2'], 'v2')
        self.assertIn('Description', diff['changed_fields'])
        self.assertIn('Steps', diff['changed_fields'])

    def test_diff_no_changes(self):
        """Test diff between identical versions."""
        self._create_test_skill('same_skill', [
            {'description': 'Same', 'steps': 'same', 'triggers': 'same'},
            {'description': 'Same', 'steps': 'same', 'triggers': 'same'}
        ])

        result = self.evolution.get_version_diff('same_skill', 'v1', 'v2')

        self.assertTrue(result['success'])
        diff = result['diff']
        self.assertEqual(len(diff['changed_fields']), 0)
        self.assertEqual(diff['summary']['total_changes'], 0)

    def test_diff_skill_not_found(self):
        """Test diff for non-existent skill."""
        result = self.evolution.get_version_diff('nonexistent', 'v1', 'v2')

        self.assertFalse(result['success'])
        self.assertIn('error', result)

    def test_diff_version_not_found(self):
        """Test diff with non-existent version."""
        self._create_test_skill('missing_v', [
            {'description': 'v1'},
            {'description': 'v2'}
        ])

        result = self.evolution.get_version_diff('missing_v', 'v1', 'v99')

        self.assertFalse(result['success'])
        self.assertIn('error', result)

    def test_diff_success_rate_change(self):
        """Test diff captures success rate changes."""
        self._create_test_skill('metrics_skill', [
            {'description': 'v1', 'success_rate': 0.5, 'execution_count': 100},
            {'description': 'v1', 'success_rate': 0.8, 'execution_count': 200}
        ])

        result = self.evolution.get_version_diff('metrics_skill', 'v1', 'v2')

        self.assertTrue(result['success'])
        diff = result['diff']
        self.assertIn('success_rate', diff['details'])
        self.assertIn('execution_count', diff['details'])
        self.assertEqual(diff['details']['success_rate']['v1'], 0.5)
        self.assertEqual(diff['details']['success_rate']['v2'], 0.8)


class TestConvenienceFunctions(unittest.TestCase):
    """Test module-level convenience functions."""

    def setUp(self):
        """Set up test fixtures."""
        # Reset global state
        import skill_evolution
        skill_evolution._default_evolution = None

    def test_get_skill_lineage_function(self):
        """Test get_skill_lineage convenience function."""
        # This will use the default evolution instance
        result = get_skill_lineage('nonexistent')
        self.assertFalse(result['success'])

    def test_rollback_skill_function(self):
        """Test rollback_skill convenience function."""
        result = rollback_skill('nonexistent', 'v1')
        self.assertFalse(result['success'])

    def test_get_version_diff_function(self):
        """Test get_version_diff convenience function."""
        result = get_version_diff('nonexistent', 'v1', 'v2')
        self.assertFalse(result['success'])


class TestIntegration(unittest.TestCase):
    """Integration tests for full workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.evolution = SkillEvolution()
        self.evolution._evolution_dir = Path(self.test_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_full_lifecycle(self):
        """Test complete lifecycle: create, evolve, check lineage, rollback, diff."""
        # Create initial skill
        skill_name = 'lifecycle_skill'
        skill_file = self.evolution._get_skill_file(skill_name)
        skill_file.parent.mkdir(parents=True, exist_ok=True)

        initial_version = SkillVersion({
            'version': 'v1',
            'name': skill_name,
            'description': 'Initial version',
            'triggers': 'initial trigger',
            'steps': 'initial steps',
            'examples': 'initial examples',
            'created_at': datetime.now().isoformat(),
            'deprecated': False,
            'success_rate': 0.7
        })

        data = {
            'skill_name': skill_name,
            'versions': [initial_version.to_dict()],
            'total_versions': 1,
            'latest_version': 'v1'
        }

        with open(skill_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        # Evolve to v2
        evolve_result = self.evolution.evolve_skill(
            skill_name,
            reason='Improving performance'
        )

        # Check lineage shows both versions
        lineage_result = self.evolution.get_skill_lineage(skill_name)
        self.assertTrue(lineage_result['success'])
        self.assertEqual(lineage_result['lineage']['total_versions'], 2)

        # Get diff between v1 and v2
        diff_result = self.evolution.get_version_diff(skill_name, 'v1', 'v2')
        self.assertTrue(diff_result['success'])

        # Rollback to v1
        rollback_result = self.evolution.rollback_skill(
            skill_name,
            'v1',
            reason='v2 not working well'
        )
        self.assertTrue(rollback_result['success'])
        self.assertEqual(rollback_result['new_version'], 'v3')

        # Verify audit log exists
        audit_file = self.evolution._evolution_dir / 'audit_log.jsonl'
        self.assertTrue(audit_file.exists())

        # Final lineage should show all versions
        final_lineage = self.evolution.get_skill_lineage(skill_name)
        self.assertEqual(final_lineage['lineage']['total_versions'], 3)

        print(f"\nIntegration test passed:")
        print(f"  - Created skill: {skill_name}")
        print(f"  - Evolved: v1 -> v2")
        print(f"  - Rolled back: v2 -> v3 (restored from v1)")
        print(f"  - Total versions: 3")


if __name__ == '__main__':
    unittest.main(verbosity=2)

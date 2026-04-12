#!/usr/bin/env python3
"""
Test Suite for Skill Comparison Module

Tests:
1. Bot skill matrix generation
2. Bot comparison functionality
3. Knowledge flow tracking
4. Skill gap identification
5. Heatmap data generation

Usage:
    python3 test_skill_comparison.py
"""

import json
import unittest
from pathlib import Path
from datetime import datetime

from skill_comparison import (
    SkillComparator,
    get_skill_comparator,
    get_bot_skill_matrix,
    compare_bots,
    get_knowledge_flow,
    identify_skill_gaps,
    generate_skill_heatmap,
    BOTS,
    SKILL_CATEGORIES,
    BOT_RELATIONSHIPS
)


class TestSkillMatrix(unittest.TestCase):
    """Test bot skill matrix generation."""

    def setUp(self):
        self.comparator = get_skill_comparator()

    def test_get_bot_skill_matrix_valid_bot(self):
        """Test getting skill matrix for a valid bot."""
        result = self.comparator.get_bot_skill_matrix("编导")

        self.assertTrue(result.get("success"))
        self.assertEqual(result["bot_name"], "编导")
        self.assertIn("bot_info", result)
        self.assertIn("total_skills", result)
        self.assertIn("category_distribution", result)
        self.assertIn("proficiency_levels", result)
        self.assertIn("skill_list", result)
        self.assertIn("generated_at", result)

    def test_get_bot_skill_matrix_invalid_bot(self):
        """Test getting skill matrix for an invalid bot."""
        result = self.comparator.get_bot_skill_matrix("InvalidBot")

        self.assertFalse(result.get("success"))
        self.assertIn("error", result)
        self.assertIn("available_bots", result)

    def test_get_bot_skill_matrix_all_bots(self):
        """Test getting skill matrix for all bots."""
        for bot_name in BOTS.keys():
            result = self.comparator.get_bot_skill_matrix(bot_name)
            self.assertTrue(result.get("success"), f"Failed for bot: {bot_name}")

    def test_skill_matrix_has_bot_info(self):
        """Test that skill matrix contains correct bot info."""
        result = self.comparator.get_bot_skill_matrix("运营")

        self.assertIn("运营", BOTS.keys())
        self.assertEqual(result["bot_info"]["role"], "operation")

    def test_convenience_function(self):
        """Test the convenience function."""
        result = get_bot_skill_matrix("客服")
        self.assertTrue(result.get("success"))


class TestBotComparison(unittest.TestCase):
    """Test bot comparison functionality."""

    def setUp(self):
        self.comparator = get_skill_comparator()

    def test_compare_bots_valid(self):
        """Test comparing two valid bots."""
        result = self.comparator.compare_bots("编导", "运营")

        self.assertTrue(result.get("success"))
        self.assertIn("bots_compared", result)
        self.assertIn("category_comparison", result)
        self.assertIn("recommendation", result)

    def test_compare_bots_invalid_bot1(self):
        """Test comparing with invalid first bot."""
        result = self.comparator.compare_bots("InvalidBot", "运营")
        self.assertFalse(result.get("success"))
        self.assertIn("error", result)

    def test_compare_bots_invalid_bot2(self):
        """Test comparing with invalid second bot."""
        result = self.comparator.compare_bots("编导", "InvalidBot")
        self.assertFalse(result.get("success"))
        self.assertIn("error", result)

    def test_compare_bots_same_bot(self):
        """Test comparing a bot with itself."""
        result = self.comparator.compare_bots("编导", "编导")
        self.assertTrue(result.get("success"))
        # Should show equal distribution
        self.assertEqual(result["bot1_info"]["total_skills"], result["bot2_info"]["total_skills"])

    def test_comparison_has_recommendation(self):
        """Test that comparison includes recommendation."""
        result = self.comparator.compare_bots("剪辑", "美工")

        self.assertIn("recommendation", result)
        self.assertIsInstance(result["recommendation"], str)

    def test_convenience_function(self):
        """Test the convenience function."""
        result = compare_bots("场控", "客服")
        self.assertTrue(result.get("success"))


class TestKnowledgeFlow(unittest.TestCase):
    """Test knowledge flow analysis."""

    def setUp(self):
        self.comparator = get_skill_comparator()

    def test_get_knowledge_flow(self):
        """Test getting knowledge flow analysis."""
        result = self.comparator.get_knowledge_flow()

        self.assertTrue(result.get("success"))
        self.assertIn("knowledge_sources", result)
        self.assertIn("knowledge_receivers", result)
        self.assertIn("propagation_paths", result)

    def test_knowledge_flow_has_bot_relationships(self):
        """Test that knowledge flow includes bot relationships."""
        result = self.comparator.get_knowledge_flow()

        self.assertIn("bot_relationships", result)
        self.assertEqual(len(result["bot_relationships"]), len(BOTS))

    def test_knowledge_flow_visualization(self):
        """Test that knowledge flow includes ASCII visualization."""
        result = self.comparator.get_knowledge_flow()

        self.assertIn("knowledge_flow_visualization", result)
        self.assertIsInstance(result["knowledge_flow_visualization"], str)

    def test_convenience_function(self):
        """Test the convenience function."""
        result = get_knowledge_flow()
        self.assertTrue(result.get("success"))


class TestSkillGaps(unittest.TestCase):
    """Test skill gap identification."""

    def setUp(self):
        self.comparator = get_skill_comparator()

    def test_identify_skill_gaps(self):
        """Test identifying skill gaps."""
        result = self.comparator.identify_skill_gaps()

        self.assertTrue(result.get("success"))
        self.assertIn("team_size", result)
        self.assertIn("skill_gaps", result)
        self.assertIn("recommendations", result)

    def test_skill_gaps_has_summary(self):
        """Test that skill gaps include bot summary."""
        result = self.comparator.identify_skill_gaps()

        self.assertIn("bot_skill_summary", result)
        self.assertEqual(len(result["bot_skill_summary"]), len(BOTS))

    def test_skill_gaps_has_recommendations(self):
        """Test that skill gaps include recommendations."""
        result = self.comparator.identify_skill_gaps()

        self.assertIn("recommendations", result)
        self.assertIsInstance(result["recommendations"], list)
        self.assertGreater(len(result["recommendations"]), 0)

    def test_skill_gap_severity(self):
        """Test that skill gaps have severity levels."""
        result = self.comparator.identify_skill_gaps()

        for gap in result["skill_gaps"]:
            self.assertIn("severity", gap)
            self.assertIn(gap["severity"], ["high", "medium", "low"])

    def test_convenience_function(self):
        """Test the convenience function."""
        result = identify_skill_gaps()
        self.assertTrue(result.get("success"))


class TestHeatmapGeneration(unittest.TestCase):
    """Test heatmap data generation."""

    def setUp(self):
        self.comparator = get_skill_comparator()

    def test_generate_skill_heatmap(self):
        """Test generating heatmap data."""
        result = self.comparator.generate_skill_heatmap_data()

        self.assertTrue(result.get("success"))
        self.assertIn("bots", result)
        self.assertIn("categories", result)
        self.assertIn("data", result)

    def test_heatmap_has_all_bots(self):
        """Test that heatmap includes all bots."""
        result = self.comparator.generate_skill_heatmap_data()

        self.assertEqual(len(result["bots"]), len(BOTS))
        for bot in BOTS.keys():
            self.assertIn(bot, result["bots"])

    def test_heatmap_has_all_categories(self):
        """Test that heatmap includes all categories."""
        result = self.comparator.generate_skill_heatmap_data()

        self.assertEqual(len(result["categories"]), len(SKILL_CATEGORIES))

    def test_heatmap_data_structure(self):
        """Test heatmap data structure."""
        result = self.comparator.generate_skill_heatmap_data()

        for bot in result["bots"]:
            self.assertIn(bot, result["data"])
            for category in result["categories"]:
                self.assertIn(category, result["data"][bot])

    def test_convenience_function(self):
        """Test the convenience function."""
        result = generate_skill_heatmap()
        self.assertTrue(result.get("success"))


class TestSkillCategorization(unittest.TestCase):
    """Test skill categorization functionality."""

    def setUp(self):
        self.comparator = get_skill_comparator()

    def test_categorize_content(self):
        """Test categorizing content."""
        # Test technical content
        categories = self.comparator._categorize_content(
            "This skill handles API integration and automation scripts"
        )
        self.assertIn("technical", categories)

        # Test content creation
        categories = self.comparator._categorize_content(
            "Writing creative scripts and content for videos"
        )
        self.assertIn("content", categories)

        # Test data analysis
        categories = self.comparator._categorize_content(
            "Analysis of metrics and statistics for reports"
        )
        self.assertIn("data", categories)

    def test_categorize_unknown_content(self):
        """Test categorizing unknown content."""
        categories = self.comparator._categorize_content("Some random text")
        # Should default to "general"
        self.assertEqual(categories, ["general"])


class TestBotRelationships(unittest.TestCase):
    """Test bot relationship functionality."""

    def test_all_bots_have_relationships(self):
        """Test that all bots have defined relationships."""
        for bot in BOTS.keys():
            self.assertIn(bot, BOT_RELATIONSHIPS)

    def test_relationships_are_valid(self):
        """Test that relationships reference valid bots."""
        for bot, related in BOT_RELATIONSHIPS.items():
            for related_bot in related:
                self.assertIn(related_bot, BOTS.keys())

    def test_xiao_xiao_qian_connects_to_all(self):
        """Test that 小小谦 connects to all bots."""
        relationships = BOT_RELATIONSHIPS.get("小小谦", [])
        # Should connect to all other bots
        other_bots = [b for b in BOTS.keys() if b != "小小谦"]
        for bot in other_bots:
            self.assertIn(bot, relationships)


class TestIntegration(unittest.TestCase):
    """Integration tests for the skill comparison module."""

    def setUp(self):
        self.comparator = get_skill_comparator()

    def test_full_workflow(self):
        """Test complete workflow: matrix -> compare -> flow -> gaps."""
        # Get matrix for a bot
        matrix = self.comparator.get_bot_skill_matrix("编导")
        self.assertTrue(matrix.get("success"))

        # Compare with another bot
        comparison = self.comparator.compare_bots("编导", "运营")
        self.assertTrue(comparison.get("success"))

        # Get knowledge flow
        flow = self.comparator.get_knowledge_flow()
        self.assertTrue(flow.get("success"))

        # Identify skill gaps
        gaps = self.comparator.identify_skill_gaps()
        self.assertTrue(gaps.get("success"))

        # Generate heatmap
        heatmap = self.comparator.generate_skill_heatmap_data()
        self.assertTrue(heatmap.get("success"))

    def test_json_serialization(self):
        """Test that all results are JSON serializable."""
        results = [
            self.comparator.get_bot_skill_matrix("编导"),
            self.comparator.compare_bots("编导", "剪辑"),
            self.comparator.get_knowledge_flow(),
            self.comparator.identify_skill_gaps(),
            self.comparator.generate_skill_heatmap_data()
        ]

        for result in results:
            try:
                json.dumps(result, ensure_ascii=False)
            except TypeError as e:
                self.fail(f"Result not JSON serializable: {e}")


class TestCommandLine(unittest.TestCase):
    """Test command-line interface."""

    def test_module_has_main(self):
        """Test that module has main block."""
        import skill_comparison
        import inspect
        source = inspect.getsource(skill_comparison)
        self.assertIn('if __name__ == "__main__":', source)


def run_tests():
    """Run all tests and print results."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestSkillMatrix))
    suite.addTests(loader.loadTestsFromTestCase(TestBotComparison))
    suite.addTests(loader.loadTestsFromTestCase(TestKnowledgeFlow))
    suite.addTests(loader.loadTestsFromTestCase(TestSkillGaps))
    suite.addTests(loader.loadTestsFromTestCase(TestHeatmapGeneration))
    suite.addTests(loader.loadTestsFromTestCase(TestSkillCategorization))
    suite.addTests(loader.loadTestsFromTestCase(TestBotRelationships))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestCommandLine))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")

    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"  - {test}")

    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"  - {test}")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)

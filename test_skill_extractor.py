#!/usr/bin/env python3
"""
Test script for Automatic Skill Extraction

Tests:
1. Skill extraction from evaluated task
2. AI-powered skill refinement
3. Duplicate detection
4. Integration with MemoryManager
5. End-to-end workflow
"""

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from skill_extractor import SkillExtractor
from task_evaluation import TaskEvaluator, TaskOutcome
from memory_manager import MemoryManager


def test_skill_extractor():
    print("=" * 60)
    print("Testing SkillExtractor")
    print("=" * 60)

    # Create manager and extractor
    manager = MemoryManager()
    manager.load(session_id="skill-extraction-test")

    extractor = SkillExtractor(memory_manager=manager)
    evaluator = TaskEvaluator()

    # Test 1: Extract skill from high-quality evaluation
    print("\n[Test 1] Extracting skill from high-quality task...")

    evaluation = evaluator.evaluate_task(
        task_type="memory_configuration",
        steps_taken=[
            "Check if memory server is running on port 8765",
            "Initialize MemoryManager with session_id",
            "Call load() to load MEMORY.md and USER.md",
            "Inject memory context into system prompt",
            "Verify memory entries are accessible"
        ],
        outcome=TaskOutcome.SUCCESS,
        user_satisfaction=0.9,
        retries=0
    )

    print(f"Task: {evaluation.task_type}")
    print(f"Score: {evaluation.preservation_score:.2f}")
    print(f"Worth preserving: {evaluation.worth_preserving}")

    if evaluation.worth_preserving:
        result = extractor.extract_skill(evaluation.to_dict())
        print(f"Extraction success: {result.get('success')}")
        if result.get('success'):
            skill = result.get('skill', {})
            print(f"Skill name: {skill.get('name', 'Unknown')}")
            print(f"Skill description: {skill.get('description', 'N/A')[:80]}...")

    # Test 2: Try to extract duplicate (should fail)
    print("\n[Test 2] Testing duplicate detection...")
    evaluation2 = evaluator.evaluate_task(
        task_type="memory_configuration",  # Same task type
        steps_taken=[
            "Check memory server",
            "Initialize manager",
            "Load memory"
        ],
        outcome=TaskOutcome.SUCCESS,
        user_satisfaction=0.8,
        retries=0
    )

    if evaluation2.worth_preserving:
        result2 = extractor.extract_skill(evaluation2.to_dict())
        print(f"Duplicate detection: {not result2.get('success', True)}")
        print(f"Error: {result2.get('error', 'None')}")

    # Test 3: Extract different skill
    print("\n[Test 3] Extracting different skill (changkong_setup)...")
    evaluation3 = evaluator.evaluate_task(
        task_type="changkong_setup",
        steps_taken=[
            "Start live-monitor service on port 4321",
            "Configure 5-minute analysis interval",
            "Setup Discord webhook for output",
            "Test data stream connectivity"
        ],
        outcome=TaskOutcome.SUCCESS,
        user_satisfaction=0.85,
        retries=0
    )

    if evaluation3.worth_preserving:
        result3 = extractor.extract_skill(evaluation3.to_dict())
        print(f"Extraction success: {result3.get('success')}")
        if result3.get('success'):
            skill = result3.get('skill', {})
            print(f"Skill name: {skill.get('name', 'Unknown')}")

    # Test 4: Check extractor status
    print("\n[Test 4] Extractor status...")
    status = extractor.get_status()
    print(f"Extractions total: {status.get('extractions_total')}")
    print(f"History: {status.get('extractions_history')}")

    print("\n" + "=" * 60)
    print("SkillExtractor tests complete!")
    print("=" * 60)


def test_memory_manager_auto_extract():
    print("\n" + "=" * 60)
    print("Testing MemoryManager Auto-Extraction")
    print("=" * 60)

    manager = MemoryManager()
    manager.load(session_id="auto-extract-test")

    # Test 1: Auto-extract enabled (default)
    print("\n[Test 1] Auto-extract enabled (default)...")
    print(f"Auto-extract setting: {manager._auto_extract_skills}")

    result = manager.evaluate_task(
        task_type="api_integration",
        steps_taken=[
            "Check API endpoint documentation",
            "Authenticate with API key",
            "Make initial request",
            "Parse JSON response",
            "Handle rate limiting",
            "Implement retry logic"
        ],
        outcome="success",
        user_satisfaction=0.85,
        retries=0
    )

    print(f"Task evaluated: {result['task_type']}")
    print(f"Score: {result['scores']['preservation_score']:.2f}")
    print(f"Worth preserving: {result['worth_preserving']}")
    print(f"Skill extraction: {result.get('skill_extraction', {}).get('success', 'N/A')}")

    # Test 2: Auto-extract disabled
    print("\n[Test 2] Auto-extract disabled...")
    manager.set_auto_extract(False)
    print(f"Auto-extract setting: {manager._auto_extract_skills}")

    result2 = manager.evaluate_task(
        task_type="debugging_workflow",
        steps_taken=[
            "Identify error source",
            "Check application logs",
            "Reproduce the issue",
            "Apply fix",
            "Verify resolution"
        ],
        outcome="success",
        user_satisfaction=0.9,
        retries=0
    )

    print(f"Task evaluated: {result2['task_type']}")
    print(f"Worth preserving: {result2['worth_preserving']}")
    print(f"Skill extraction: {result2.get('skill_extraction', 'Not attempted')}")

    # Test 3: Re-enable and force extract
    print("\n[Test 3] Re-enable and force extract...")
    manager.set_auto_extract(True)

    result3 = manager.evaluate_task(
        task_type="database_backup",
        steps_taken=[
            "Create database snapshot",
            "Compress backup file",
            "Transfer to remote storage",
            "Verify backup integrity",
            "Update backup log"
        ],
        outcome="success",
        user_satisfaction=0.95,
        retries=0,
        auto_extract=True  # Force extract
    )

    print(f"Skill extraction with force: {result3.get('skill_extraction', {}).get('success', 'N/A')}")

    # Test 4: Check final state
    print("\n[Test 4] Final state...")
    skills = manager._skill_store.read()
    print(f"Total skills in SKILL.md: {skills['count']}")

    eval_summary = manager.get_evaluation_summary()
    print(f"Evaluation summary: {eval_summary}")

    extractor_status = manager.get_skill_extractor_status()
    print(f"Extractor status: {extractor_status}")

    print("\n" + "=" * 60)
    print("MemoryManager auto-extraction tests complete!")
    print("=" * 60)


def test_end_to_end_workflow():
    print("\n" + "=" * 60)
    print("End-to-End Workflow Test")
    print("=" * 60)

    manager = MemoryManager()
    manager.load(session_id="e2e-test")

    # Simulate real workflow: task completes → evaluate → auto-extract
    print("\n[Workflow] Task completes...")

    tasks = [
        ("memory_setup", [
            "Initialize MemoryManager",
            "Load memory from disk",
            "Build memory context",
            "Inject into system prompt"
        ], "success", 0.8),
        ("bot_deploy", [
            "Configure bot credentials",
            "Set up webhook endpoints",
            "Deploy to server",
            "Test connectivity",
            "Monitor logs"
        ], "success", 0.9),
        ("simple_query", [
            "Answer user question"
        ], "success", 0.5),  # Too simple, won't be preserved
    ]

    for task_type, steps, outcome, satisfaction in tasks:
        print(f"\n  Evaluating: {task_type}")
        result = manager.evaluate_task(
            task_type=task_type,
            steps_taken=steps,
            outcome=outcome,
            user_satisfaction=satisfaction
        )

        preserve = "PRESERVE" if result['worth_preserving'] else "SKIP"
        extracted = result.get('skill_extraction', {}).get('success', False)
        print(f"    → {preserve}, Extracted: {extracted}")

    # Final summary
    print("\n[Final Summary]")
    summary = manager.get_evaluation_summary()
    print(f"Tasks evaluated: {summary['total']}")
    print(f"Tasks preserved: {summary['preserved']}")
    print(f"Preservation rate: {summary['preservation_rate']:.1%}")

    extractor = manager.get_skill_extractor_status()
    print(f"Skills extracted: {extractor.get('extractions_total')}")

    print("\n" + "=" * 60)
    print("End-to-end workflow test complete!")
    print("=" * 60)


if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    test_skill_extractor()
    test_memory_manager_auto_extract()
    test_end_to_end_workflow()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)

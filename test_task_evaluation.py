#!/usr/bin/env python3
"""
Test script for Task Evaluation System

Tests Phoenix Core-style task evaluation:
1. Reusability assessment
2. Complexity assessment
3. Effectiveness assessment
4. Generality assessment
5. Preservation decision
6. Integration with MemoryManager
"""

import sys
sys.path.insert(0, str(Path(__file__).parent))

from task_evaluation import TaskEvaluator, TaskOutcome, TaskEvaluation
from memory_manager import MemoryManager


def test_task_evaluator():
    print("=" * 60)
    print("Testing TaskEvaluator")
    print("=" * 60)

    evaluator = TaskEvaluator()

    # Test 1: High-quality task (should be preserved)
    print("\n[Test 1] Evaluating high-quality task...")
    eval1 = evaluator.evaluate_task(
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

    print(f"Task: {eval1.task_type}")
    print(f"Scores: reusability={eval1.reusability:.2f}, complexity={eval1.complexity:.2f}")
    print(f"        effectiveness={eval1.effectiveness:.2f}, generality={eval1.generality:.2f}")
    print(f"Preservation score: {eval1.preservation_score:.2f}")
    print(f"Worth preserving: {eval1.worth_preserving}")
    print(f"Reasoning: {eval1.reasoning}")

    # Test 2: Low-quality task (should NOT be preserved)
    print("\n[Test 2] Evaluating low-quality task...")
    eval2 = evaluator.evaluate_task(
        task_type="simple_greeting",
        steps_taken=[
            "Say hello"
        ],
        outcome=TaskOutcome.SUCCESS,
        user_satisfaction=0.5,
        retries=0
    )

    print(f"Task: {eval2.task_type}")
    print(f"Preservation score: {eval2.preservation_score:.2f}")
    print(f"Worth preserving: {eval2.worth_preserving}")
    print(f"Reasoning: {eval2.reasoning}")

    # Test 3: Task with failures (should NOT be preserved)
    print("\n[Test 3] Evaluating failed task...")
    eval3 = evaluator.evaluate_task(
        task_type="complex_migration",
        steps_taken=[
            "Attempt to migrate data",
            "Encounter error, retry",
            "Fail again",
            "Give up"
        ],
        outcome=TaskOutcome.FAILURE,
        user_satisfaction=0.2,
        retries=3
    )

    print(f"Task: {eval3.task_type}")
    print(f"Preservation score: {eval3.preservation_score:.2f}")
    print(f"Worth preserving: {eval3.worth_preserving}")
    print(f"Reasoning: {eval3.reasoning}")

    # Test 4: Partial success with retries
    print("\n[Test 4] Evaluating partial success with retries...")
    eval4 = evaluator.evaluate_task(
        task_type="bot_configuration",
        steps_taken=[
            "Start live-monitor service on port 4321",
            "Configure 5-minute analysis interval",
            "Setup Discord webhook",
            "Test connection - failed, adjust config",
            "Test connection - success"
        ],
        outcome=TaskOutcome.PARTIAL,
        user_satisfaction=0.6,
        retries=1
    )

    print(f"Task: {eval4.task_type}")
    print(f"Preservation score: {eval4.preservation_score:.2f}")
    print(f"Worth preserving: {eval4.worth_preserving}")
    print(f"Reasoning: {eval4.reasoning}")

    # Test 5: Check evaluation summary
    print("\n[Test 5] Evaluation summary...")
    summary = evaluator.get_evaluation_summary()
    print(f"Total evaluations: {summary['total']}")
    print(f"Preserved: {summary['preserved']}")
    print(f"Rejected: {summary['rejected']}")
    print(f"Preservation rate: {summary['preservation_rate']:.1%}")
    print(f"Average score: {summary['average_score']:.2f}")

    print("\n" + "=" * 60)
    print("TaskEvaluator tests complete!")
    print("=" * 60)


def test_memory_manager_integration():
    print("\n" + "=" * 60)
    print("Testing MemoryManager Integration")
    print("=" * 60)

    manager = MemoryManager()
    manager.load(session_id="task-eval-test")

    # Test 1: Check evaluator exists
    print("\n[Test 1] Checking task evaluator...")
    print(f"Has _task_evaluator: {hasattr(manager, '_task_evaluator')}")

    # Test 2: Evaluate via manager
    print("\n[Test 2] Evaluating task via manager...")
    result = manager.evaluate_task(
        task_type="changkong_setup",
        steps_taken=[
            "Start live-monitor service on port 4321",
            "Configure 5-minute analysis interval",
            "Setup Discord output channel",
            "Verify data stream connectivity"
        ],
        outcome="success",
        user_satisfaction=0.85,
        retries=0
    )

    print(f"Task type: {result['task_type']}")
    print(f"Outcome: {result['outcome']}")
    print(f"Scores: {result['scores']}")
    print(f"Worth preserving: {result['worth_preserving']}")
    print(f"Reasoning: {result['reasoning'][:100]}...")

    # Test 3: Get evaluation summary
    print("\n[Test 3] Getting evaluation summary...")
    summary = manager.get_evaluation_summary()
    print(f"Summary: {summary}")

    # Test 4: Multiple evaluations
    print("\n[Test 4] Running multiple evaluations...")

    test_cases = [
        ("simple_query", ["Answer question"], "success", 0.5, 0),
        ("api_integration", [
            "Check API endpoint",
            "Authenticate with API key",
            "Make request",
            "Parse response",
            "Handle errors"
        ], "success", 0.8, 0),
        ("debugging", [
            "Identify error source",
            "Check logs",
            "Fix configuration",
            "Restart service",
            "Verify fix"
        ], "success", 0.9, 0),
    ]

    for task_type, steps, outcome, satisfaction, retries in test_cases:
        result = manager.evaluate_task(task_type, steps, outcome, satisfaction, retries=retries)
        preserve = "PRESERVE" if result['worth_preserving'] else "SKIP"
        print(f"  {task_type}: {preserve} (score={result['scores']['preservation_score']:.2f})")

    # Final summary
    print("\n[Final Summary]")
    summary = manager.get_evaluation_summary()
    print(f"Total: {summary['total']}, Preserved: {summary['preserved']}, Rate: {summary['preservation_rate']:.1%}")

    print("\n" + "=" * 60)
    print("MemoryManager integration tests complete!")
    print("=" * 60)


def test_phoenix_criteria():
    print("\n" + "=" * 60)
    print("Testing Phoenix Core-style Criteria")
    print("=" * 60)

    evaluator = TaskEvaluator()

    # Test cases that demonstrate Phoenix Core criteria
    test_cases = [
        {
            "name": "Reusable + Complex + Effective",
            "task": "database_migration",
            "steps": [
                "Backup existing database",
                "Create migration script",
                "Run migration in test environment",
                "Verify data integrity",
                "Deploy to production",
                "Monitor for issues"
            ],
            "outcome": TaskOutcome.SUCCESS,
            "satisfaction": 0.95,
            "expected": True
        },
        {
            "name": "Too Simple (trivial)",
            "task": "greeting",
            "steps": ["Say hi"],
            "outcome": TaskOutcome.SUCCESS,
            "satisfaction": 0.5,
            "expected": False
        },
        {
            "name": "Not Reusable (one-off)",
            "task": "fix_typo_in_readme",
            "steps": ["Open README.md", "Fix typo", "Save file"],
            "outcome": TaskOutcome.SUCCESS,
            "satisfaction": 0.7,
            "expected": False
        },
        {
            "name": "Failed Task",
            "task": "server_setup",
            "steps": ["Install dependencies", "Configure server", "Start service"],
            "outcome": TaskOutcome.FAILURE,
            "satisfaction": 0.2,
            "expected": False
        },
    ]

    for tc in test_cases:
        print(f"\n[Case: {tc['name']}]")
        result = evaluator.evaluate_task(
            task_type=tc['task'],
            steps_taken=tc['steps'],
            outcome=tc['outcome'],
            user_satisfaction=tc['satisfaction']
        )

        verdict = "PRESERVE" if result.worth_preserving else "SKIP"
        expected = "PRESERVE" if tc['expected'] else "SKIP"
        match = "✓" if result.worth_preserving == tc['expected'] else "✗"

        print(f"  Score: {result.preservation_score:.2f}, Decision: {verdict} (Expected: {expected}) {match}")
        print(f"  Reasoning: {result.reasoning}")

    print("\n" + "=" * 60)
    print("Phoenix Core criteria tests complete!")
    print("=" * 60)


if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    test_task_evaluator()
    test_memory_manager_integration()
    test_phoenix_criteria()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)

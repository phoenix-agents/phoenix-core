#!/usr/bin/env python3
"""
Test script for Skill Optimization (Execution Result Learning)

Tests:
1. Execution result recording
2. Statistics calculation
3. Failure pattern analysis
4. AI-powered skill optimization
5. Integration with MemoryManager
"""

import sys
sys.path.insert(0, str(Path(__file__).parent))

from skill_optimizer import SkillOptimizer
from memory_manager import MemoryManager


def test_execution_recording():
    print("=" * 60)
    print("Testing Execution Result Recording")
    print("=" * 60)

    optimizer = SkillOptimizer()

    # Test 1: Record successful execution
    print("\n[Test 1] Recording successful execution...")
    optimizer.record_execution("Memory Configuration", {
        "success": True,
        "total_steps": 5,
        "success_count": 5,
        "error_count": 0,
        "execution_time": 2.5
    })
    print("Recorded: Success execution")

    # Test 2: Record failed execution
    print("\n[Test 2] Recording failed execution...")
    optimizer.record_execution("Memory Configuration", {
        "success": False,
        "total_steps": 5,
        "success_count": 2,
        "error_count": 1,
        "step_results": [
            {"success": True},
            {"success": True},
            {"success": False, "error": "Connection timeout on port 8765"}
        ]
    })
    print("Recorded: Failed execution")

    # Test 3: Record multiple executions
    print("\n[Test 3] Recording multiple executions...")
    for i in range(10):
        optimizer.record_execution("Changkong Setup", {
            "success": i >= 3,  # First 3 fail, rest succeed
            "total_steps": 4,
            "success_count": 4 if i >= 3 else 1,
            "error_count": 0 if i >= 3 else 1,
            "step_results": [] if i >= 3 else [
                {"success": True},
                {"success": False, "error": "Port 4321 already in use"}
            ]
        })
    print("Recorded: 10 executions (7 success, 3 failures)")

    # Test 4: Get stats
    print("\n[Test 4] Getting skill statistics...")
    stats = optimizer.get_skill_stats("Changkong Setup")
    print(f"Total executions: {stats['total_executions']}")
    print(f"Successes: {stats['successes']}")
    print(f"Failures: {stats['failures']}")
    print(f"Success rate: {stats['success_rate']:.0%}")
    print(f"Needs optimization: {stats['needs_optimization']}")

    print("\n" + "=" * 60)
    print("Execution result recording tests complete!")
    print("=" * 60)


def test_failure_analysis():
    print("\n" + "=" * 60)
    print("Testing Failure Pattern Analysis")
    print("=" * 60)

    optimizer = SkillOptimizer()

    # Record executions with specific failure pattern
    print("\n[Recording executions with pattern...]")
    for i in range(8):
        optimizer.record_execution("API Integration", {
            "success": i >= 5,
            "total_steps": 6,
            "success_count": 2 if i < 5 else 6,
            "error_count": 1 if i < 5 else 0,
            "step_results": [] if i >= 5 else [
                {"success": True},
                {"success": True},
                {"success": False, "error": f"Rate limit exceeded (attempt {i+1})"}
            ]
        })

    # Get stats
    stats = optimizer.get_skill_stats("API Integration")
    print(f"\nSkill: {stats['skill_name']}")
    print(f"Total: {stats['total_executions']}")
    print(f"Success rate: {stats['success_rate']:.0%}")
    print(f"Common failure step: {stats['common_failure_step']}")
    print(f"Common error: {stats['common_error']}")
    print(f"Needs optimization: {stats['needs_optimization']}")

    # Check if should optimize
    should_opt = optimizer.should_optimize("API Integration")
    print(f"\nShould optimize: {should_opt}")

    print("\n" + "=" * 60)
    print("Failure pattern analysis tests complete!")
    print("=" * 60)


def test_optimization_candidates():
    print("\n" + "=" * 60)
    print("Testing Optimization Candidates")
    print("=" * 60)

    optimizer = SkillOptimizer()

    # Record various skills with different success rates
    skills_data = [
        ("Memory Config", 0.9, 10),  # 90% success, 10 executions - good
        ("API Integration", 0.5, 8),  # 50% success, 8 executions - needs work
        ("Database Backup", 0.3, 6),  # 30% success, 6 executions - needs optimize
        ("Bot Deploy", 0.95, 5),      # 95% success - excellent
    ]

    for skill_name, success_rate, total in skills_data:
        successes = int(total * success_rate)
        failures = total - successes

        for i in range(total):
            optimizer.record_execution(skill_name, {
                "success": i < successes,
                "total_steps": 5,
                "success_count": 5 if i < successes else 2,
                "error_count": 0 if i < successes else 1
            })

    # Get candidates
    candidates = optimizer.get_optimization_candidates()
    print(f"\nOptimization candidates: {len(candidates)}")
    for c in candidates:
        print(f"  - {c['skill_name']}: {c['stats']['success_rate']:.0%} success rate")

    print("\n" + "=" * 60)
    print("Optimization candidates tests complete!")
    print("=" * 60)


def test_memory_manager_integration():
    print("\n" + "=" * 60)
    print("Testing MemoryManager Integration")
    print("=" * 60)

    manager = MemoryManager()
    manager.load(session_id="optimizer-test")

    # Test 1: Record execution via manager
    print("\n[Test 1] Recording execution via MemoryManager...")
    manager.record_skill_execution("Memory Setup", {
        "success": True,
        "total_steps": 4,
        "success_count": 4,
        "error_count": 0
    })
    print("Recorded successfully")

    # Test 2: Get stats via manager
    print("\n[Test 2] Getting stats via MemoryManager...")
    stats = manager.get_skill_stats("Memory Setup")
    print(f"Stats: {stats}")

    # Test 3: Multiple executions
    print("\n[Test 3] Recording multiple executions...")
    for i in range(6):
        manager.record_skill_execution("Test Skill", {
            "success": i >= 4,
            "total_steps": 5,
            "success_count": 5 if i >= 4 else 2,
            "error_count": 0 if i >= 4 else 1,
            "step_results": [] if i >= 4 else [
                {"success": True},
                {"success": True},
                {"success": False, "error": "Test error"}
            ]
        })

    # Check if should optimize
    should_opt = manager.should_optimize_skill("Test Skill")
    print(f"Should optimize 'Test Skill': {should_opt}")

    # Get all stats
    all_stats = manager.get_all_execution_stats()
    print(f"\nAll stats: {all_stats}")

    # Get candidates
    candidates = manager.get_optimization_candidates()
    print(f"Optimization candidates: {len(candidates)}")

    print("\n" + "=" * 60)
    print("MemoryManager integration tests complete!")
    print("=" * 60)


def test_ai_optimization():
    print("\n" + "=" * 60)
    print("Testing AI-Powered Optimization")
    print("=" * 60)

    manager = MemoryManager()
    manager.load(session_id="ai-opt-test")

    # Add a test skill first
    manager.add_skill("""[SKILL] Test Optimization Skill
Description: A skill for testing AI optimization
Triggers: When testing optimization
Steps: 1. Do something. 2. Check result. 3. Report status.
Examples: Testing the optimizer""")

    # Record failures with specific pattern
    print("\n[Recording failures for AI optimization...]")
    for i in range(5):
        manager.record_skill_execution("Test Optimization Skill", {
            "success": False,
            "total_steps": 3,
            "success_count": 1,
            "error_count": 1,
            "step_results": [
                {"success": True},
                {"success": False, "error": f"Step 2 failed: missing precondition check (attempt {i+1})"}
            ]
        })

    # Check if should optimize
    should_opt = manager.should_optimize_skill("Test Optimization Skill")
    print(f"Should optimize: {should_opt}")

    if should_opt:
        # Try AI optimization
        print("\n[Running AI optimization...]")
        result = manager.optimize_skill("Test Optimization Skill")
        print(f"Optimization result: {result.get('success')}")

        if result.get('success'):
            print(f"Original: {result['original_skill']['name']}")
            print(f"Optimized: {result['optimized_skill']['name']}")
            print(f"Optimized steps: {result['optimized_skill'].get('steps', 'N/A')[:100]}...")

    print("\n" + "=" * 60)
    print("AI optimization tests complete!")
    print("=" * 60)


if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    test_execution_recording()
    test_failure_analysis()
    test_optimization_candidates()
    test_memory_manager_integration()
    test_ai_optimization()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)

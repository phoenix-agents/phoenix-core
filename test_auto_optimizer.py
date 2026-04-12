#!/usr/bin/env python3
"""
Test script for Automatic Skill Optimization

Tests:
1. AutoOptimizer initialization
2. Candidate detection
3. Auto-optimization logic
4. Background service (simulated)
5. Optimization history tracking
6. MemoryManager integration
"""

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from auto_optimizer import AutoOptimizer, get_auto_optimizer
from memory_manager import MemoryManager
import time


def test_auto_optimizer_init():
    print("=" * 60)
    print("Testing AutoOptimizer Initialization")
    print("=" * 60)

    optimizer = AutoOptimizer()

    print(f"\nDefault settings:")
    print(f"  Auto-optimize enabled: {optimizer._auto_optimize_enabled}")
    print(f"  Auto-optimize threshold: {optimizer._auto_optimize_threshold:.0%}")
    print(f"  Min failures for auto: {optimizer._min_failures_for_auto}")
    print(f"  Scan interval: {optimizer._scan_interval_minutes} minutes")

    status = optimizer.get_status()
    print(f"\nStatus: {status}")

    print("\n" + "=" * 60)
    print("Initialization test complete!")
    print("=" * 60)


def test_candidate_detection():
    print("\n" + "=" * 60)
    print("Testing Candidate Detection")
    print("=" * 60)

    optimizer = AutoOptimizer()

    # Record executions for a skill that should be a candidate
    print("\n[Recording executions for 'Database Sync' skill...]")
    for i in range(10):
        optimizer._optimizer.record_execution("Database Sync", {
            "success": i < 4,  # 4 successes, 6 failures
            "total_steps": 5,
            "success_count": 5 if i < 4 else 2,
            "error_count": 0 if i < 4 else 1,
            "step_results": [] if i < 4 else [
                {"success": True},
                {"success": True},
                {"success": False, "error": f"Connection timeout (attempt {i+1})"}
            ]
        })

    # Record executions for a skill that should NOT be a candidate (good success rate)
    print("[Recording executions for 'Cache Warmup' skill...]")
    for i in range(10):
        optimizer._optimizer.record_execution("Cache Warmup", {
            "success": i < 8,  # 8 successes, 2 failures
            "total_steps": 4,
            "success_count": 4 if i < 8 else 1,
            "error_count": 0 if i < 8 else 1
        })

    # Get candidates
    candidates = optimizer.get_candidates_preview()
    print(f"\nCandidates found: {len(candidates)}")

    for c in candidates:
        should_auto = optimizer._should_auto_optimize(c['stats'])
        print(f"  - {c['skill_name']}: {c['stats']['success_rate']:.0%} success, auto-optimize: {should_auto}")

    print("\n" + "=" * 60)
    print("Candidate detection test complete!")
    print("=" * 60)


def test_auto_optimize_logic():
    print("\n" + "=" * 60)
    print("Testing Auto-Optimize Logic")
    print("=" * 60)

    optimizer = AutoOptimizer()

    # Test threshold checks with full stats dict format
    test_cases = [
        {"success_rate": 0.3, "failures": 5, "total_executions": 8, "expected": True},
        {"success_rate": 0.6, "failures": 4, "total_executions": 10, "expected": False},  # Above threshold
        {"success_rate": 0.4, "failures": 2, "total_executions": 5, "expected": False},   # Not enough failures
        {"success_rate": 0.35, "failures": 6, "total_executions": 4, "expected": False},  # Not enough data
    ]

    print("\n[Testing _should_auto_optimize logic...]")
    for i, case in enumerate(test_cases):
        result = optimizer._should_auto_optimize(case)
        expected = case['expected']
        status = "✓" if result == expected else "✗"
        print(f"  Case {i+1}: success_rate={case['success_rate']:.0%}, "
              f"failures={case['failures']}, total={case['total_executions']}")
        print(f"    Result: {result}, Expected: {expected} {status}")

    print("\n" + "=" * 60)
    print("Auto-optimize logic test complete!")
    print("=" * 60)


def test_scan_and_optimize():
    print("\n" + "=" * 60)
    print("Testing Scan and Optimize")
    print("=" * 60)

    # Use MemoryManager for full integration test
    manager = MemoryManager()
    manager.load(session_id="auto-opt-test")

    # Add a test skill
    manager.add_skill("""[SKILL] Test API Retry
Description: API integration with retry logic
Triggers: When calling external APIs
Steps: 1. Call API. 2. Check response. 3. Retry on failure.
Examples: REST API calls""")

    optimizer = manager._auto_optimizer

    # Record failing executions
    print("\n[Recording failing executions...]")
    for i in range(8):
        manager.record_skill_execution("Test API Retry", {
            "success": i >= 6,  # Only last 2 succeed
            "total_steps": 3,
            "success_count": 3 if i >= 6 else 1,
            "error_count": 0 if i >= 6 else 1,
            "step_results": [] if i >= 6 else [
                {"success": True},
                {"success": False, "error": f"API rate limit (attempt {i+1})"}
            ]
        })

    # Dry run first
    print("\n[Dry run scan...]")
    dry_result = optimizer.scan_and_optimize(dry_run=True)
    print(f"Candidates found: {dry_result['candidates_found']}")
    print(f"Would optimize: {len([c for c in dry_result['optimizations'] if c.get('would_optimize', False)])}")

    # Actual optimization
    print("\n[Running actual optimization...]")
    result = optimizer.scan_and_optimize(dry_run=False)
    print(f"Optimized count: {result['optimized_count']}")
    print(f"Failed count: {result['failed_count']}")

    if result['optimizations']:
        opt = result['optimizations'][0]
        print(f"\nFirst optimization:")
        print(f"  Skill: {opt['skill_name']}")
        print(f"  Original success rate: {opt.get('original_success_rate', 'N/A')}")

    print("\n" + "=" * 60)
    print("Scan and optimize test complete!")
    print("=" * 60)


def test_optimization_history():
    print("\n" + "=" * 60)
    print("Testing Optimization History")
    print("=" * 60)

    optimizer = AutoOptimizer()

    # Simulate some optimization history
    print("\n[Simulating optimization history...]")
    optimizer._optimization_history = [
        {
            "timestamp": "2026-04-09T10:00:00",
            "skill_name": "API Integration v1",
            "optimized_name": "API Integration v2",
            "original_success_rate": 0.45,
            "auto_optimized": True
        },
        {
            "timestamp": "2026-04-09T11:30:00",
            "skill_name": "Database Sync v1",
            "optimized_name": "Database Sync v2",
            "original_success_rate": 0.38,
            "auto_optimized": True
        },
        {
            "timestamp": "2026-04-09T14:00:00",
            "skill_name": "Cache Warmup v1",
            "optimized_name": "Cache Warmup v2",
            "original_success_rate": 0.52,
            "auto_optimized": False
        }
    ]

    # Get history
    history = optimizer.get_optimization_history(limit=10)
    print(f"Total history entries: {len(history)}")

    # Get limited history
    limited = optimizer.get_optimization_history(limit=2)
    print(f"Limited history (limit=2): {len(limited)}")

    # Get status
    status = optimizer.get_status()
    print(f"\nStatus:")
    print(f"  Total optimizations: {status['total_optimizations']}")
    print(f"  Skills tracked: {status['skills_tracked']}")

    print("\n" + "=" * 60)
    print("Optimization history test complete!")
    print("=" * 60)


def test_background_service():
    print("\n" + "=" * 60)
    print("Testing Background Service (Simulated)")
    print("=" * 60)

    manager = MemoryManager()
    manager.load(session_id="background-test")

    optimizer = manager._auto_optimizer

    # Add test skill and record failures
    manager.add_skill("""[SKILL] Background Test Skill
Description: Test skill for background optimization
Triggers: Testing
Steps: 1. Test. 2. Verify. 3. Report.
Examples: Testing""")

    for i in range(6):
        manager.record_skill_execution("Background Test Skill", {
            "success": i >= 4,
            "total_steps": 3,
            "success_count": 3 if i >= 4 else 1,
            "error_count": 0 if i >= 4 else 1
        })

    # Start background service with short interval for testing
    print("\n[Starting background service with 1-minute interval...]")
    optimizer.start_background_service(interval_minutes=1)

    # Check status
    status = optimizer.get_status()
    print(f"Background running: {status['background_running']}")
    print(f"Scan interval: {status['scan_interval_minutes']}min")

    # Let it run briefly
    print("\n[Waiting 2 seconds for background loop...]")
    time.sleep(2)

    # Check if scan happened
    status = optimizer.get_status()
    print(f"Last scan: {status['last_scan']}")

    # Stop service
    print("\n[Stopping background service...]")
    optimizer.stop_background_service(wait=True)

    status = optimizer.get_status()
    print(f"Background running after stop: {status['background_running']}")

    print("\n" + "=" * 60)
    print("Background service test complete!")
    print("=" * 60)


def test_memory_manager_integration():
    print("\n" + "=" * 60)
    print("Testing MemoryManager Integration")
    print("=" * 60)

    manager = MemoryManager()
    manager.load(session_id="integration-test")

    # Test all new methods
    print("\n[Test 1] Start auto-optimization...")
    manager.start_auto_optimization(interval_minutes=60)
    print("Started")

    print("\n[Test 2] Get status...")
    status = manager.get_auto_optimizer_status()
    print(f"Status: {status}")

    print("\n[Test 3] Set threshold...")
    manager.set_auto_optimize_threshold(0.6)
    print("Threshold set to 60%")

    print("\n[Test 4] Get candidates preview...")
    candidates = manager.get_optimization_candidates_preview()
    print(f"Candidates: {len(candidates)}")

    print("\n[Test 5] Dry run scan...")
    result = manager.scan_and_optimize(dry_run=True)
    print(f"Scan result: {result['candidates_found']} candidates")

    print("\n[Test 6] Stop auto-optimization...")
    manager.stop_auto_optimization()
    print("Stopped")

    print("\n" + "=" * 60)
    print("MemoryManager integration test complete!")
    print("=" * 60)


if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    test_auto_optimizer_init()
    test_candidate_detection()
    test_auto_optimize_logic()
    test_scan_and_optimize()
    test_optimization_history()
    test_background_service()
    test_memory_manager_integration()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)

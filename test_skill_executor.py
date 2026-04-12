#!/usr/bin/env python3
"""
Test script for Skill Workflow Executor

Tests:
1. Skill matching from user input
2. Step parsing
3. Step execution
4. Built-in handlers
5. Integration with MemoryManager
6. End-to-end workflow execution
"""

import sys
sys.path.insert(0, str(Path(__file__).parent))

from skill_executor import SkillExecutor
from memory_manager import MemoryManager


def test_skill_executor():
    print("=" * 60)
    print("Testing SkillExecutor")
    print("=" * 60)

    # Create manager and executor
    manager = MemoryManager()
    manager.load(session_id="skill-executor-test")

    executor = SkillExecutor(memory_manager=manager)

    # Test 1: Find matching skill
    print("\n[Test 1] Finding matching skill...")
    skill = executor.find_matching_skill("how do I configure memory?")
    if skill:
        print(f"Found skill: {skill['name']}")
        print(f"Description: {skill['description'][:60]}...")
    else:
        print("No matching skill found")

    # Test 2: Parse steps
    print("\n[Test 2] Parsing skill steps...")
    if skill:
        steps = executor._parse_steps(skill)
        print(f"Parsed {len(steps)} steps:")
        for i, step in enumerate(steps[:3], 1):
            print(f"  {i}. Action: {step['action']}, Target: {step['target']}")

    # Test 3: Execute step handlers
    print("\n[Test 3] Testing built-in handlers...")
    test_steps = [
        {"action": "check", "target": "memory server", "raw": "Check memory server"},
        {"action": "verify", "target": "entries", "raw": "Verify entries"},
        {"action": "initialize", "target": "manager", "raw": "Initialize MemoryManager"},
        {"action": "load", "target": "memory", "raw": "Load memory from disk"},
        {"action": "start", "target": "service", "parameters": {"port": 8765}, "raw": "Start service on port 8765"},
        {"action": "test", "target": "connection", "raw": "Test connection"},
    ]

    for step in test_steps:
        result = executor._execute_step(step, {}, step_number=1)
        status = "✓" if result.get('success') else "✗"
        print(f"  {status} {step['action']}: {result.get('message', 'N/A')[:50]}")

    # Test 4: Execute full skill
    print("\n[Test 4] Executing full skill...")
    if skill:
        result = executor.execute_skill(skill, {})
        print(f"Skill: {result.get('skill_name')}")
        print(f"Success: {result.get('success')}")
        print(f"Steps: {result.get('success_count')}/{result.get('total_steps')} completed")

    # Test 5: Executor status
    print("\n[Test 5] Executor status...")
    status = executor.get_status()
    print(f"Total executions: {status.get('total_executions')}")
    print(f"Handlers registered: {status.get('handlers_registered')}")

    print("\n" + "=" * 60)
    print("SkillExecutor tests complete!")
    print("=" * 60)


def test_memory_manager_integration():
    print("\n" + "=" * 60)
    print("Testing MemoryManager Integration")
    print("=" * 60)

    manager = MemoryManager()
    manager.load(session_id="integration-test")

    # Test 1: Check executor exists
    print("\n[Test 1] Checking skill executor...")
    print(f"Has _skill_executor: {hasattr(manager, '_skill_executor')}")

    # Test 2: Execute skill by user input
    print("\n[Test 2] Execute skill by user input...")
    result = manager.execute_skill(user_input="how to setup memory configuration")
    print(f"Success: {result.get('success')}")
    if result.get('success'):
        print(f"Skill: {result.get('skill_name')}")
        print(f"Steps completed: {result.get('success_count')}/{result.get('total_steps')}")

    # Test 3: Execute skill by name
    print("\n[Test 3] Execute skill by name...")
    result = manager.execute_skill(skill_name="Memory Configuration")
    print(f"Success: {result.get('success')}")
    if result.get('success'):
        print(f"Skill: {result.get('skill_name')}")
        print(f"Steps: {result.get('success_count')}/{result.get('total_steps')}")

    # Test 4: Non-existent skill
    print("\n[Test 4] Non-existent skill...")
    result = manager.execute_skill(skill_name="NonExistent Skill")
    print(f"Error: {result.get('error')}")

    # Test 5: No matching input
    print("\n[Test 5] No matching skill for input...")
    result = manager.execute_skill(user_input="what is the weather")
    print(f"Error: {result.get('error', 'None')}")

    # Test 6: Get executor status
    print("\n[Test 6] Executor status via manager...")
    status = manager.get_skill_executor_status()
    print(f"Status: {status}")

    print("\n" + "=" * 60)
    print("MemoryManager integration tests complete!")
    print("=" * 60)


def test_end_to_end_workflow():
    print("\n" + "=" * 60)
    print("End-to-End Workflow Test")
    print("=" * 60)

    manager = MemoryManager()
    manager.load(session_id="e2e-workflow-test")

    # Test scenarios
    scenarios = [
        ("Memory setup query", "how do I initialize memory for a new session?"),
        ("Changkong setup", "setup Changkong bot for field control"),
        ("API integration", "how to integrate with external API"),
    ]

    for name, user_input in scenarios:
        print(f"\n[Scenario: {name}]")
        print(f"  Input: {user_input}")

        # Find matching skill
        skill = manager._skill_executor.find_matching_skill(user_input)
        if skill:
            print(f"  Matched: {skill['name']}")

            # Execute
            result = manager._skill_executor.execute_skill(skill)
            print(f"  Result: {result.get('success_count')}/{result.get('total_steps')} steps")
        else:
            print(f"  No matching skill found")

    # Execution history
    print("\n[Execution History]")
    history = manager._skill_executor.get_execution_history(limit=5)
    for i, exec_record in enumerate(history[-3:], 1):
        print(f"  {i}. {exec_record.get('skill_name')} - Success: {exec_record.get('success')}")

    print("\n" + "=" * 60)
    print("End-to-end workflow test complete!")
    print("=" * 60)


def test_custom_handler():
    print("\n" + "=" * 60)
    print("Testing Custom Handler Registration")
    print("=" * 60)

    manager = MemoryManager()
    manager.load(session_id="custom-handler-test")

    # Register custom handler
    def handle_deploy(step, context):
        return {
            "success": True,
            "message": f"Deployed to {step.get('target', 'target')}",
            "custom": True
        }

    manager._skill_executor.register_handler("deploy", handle_deploy)
    print("\n[Registered custom 'deploy' handler]")

    # Test custom handler
    step = {"action": "deploy", "target": "production server", "raw": "Deploy to production server"}
    result = manager._skill_executor._execute_step(step, {}, step_number=1)
    print(f"Custom handler result: {result.get('message')}")
    print(f"Custom flag: {result.get('custom')}")

    print("\n" + "=" * 60)
    print("Custom handler test complete!")
    print("=" * 60)


if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    test_skill_executor()
    test_memory_manager_integration()
    test_end_to_end_workflow()
    test_custom_handler()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)

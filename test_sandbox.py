#!/usr/bin/env python3
"""
Test script for Skill Execution Sandbox

Tests:
1. Risk assessment
2. Sandbox execution
3. Step simulation
4. Side effects detection
5. Integration with MemoryManager
"""

import sys
sys.path.insert(0, str(Path(__file__).parent))

from skill_executor import SkillExecutor
from skill_risk_assessor import RiskAssessor
from memory_manager import MemoryManager


def test_risk_assessor():
    print("=" * 60)
    print("Testing RiskAssessor")
    print("=" * 60)

    assessor = RiskAssessor()

    # Test 1: Low risk skill (read-only)
    print("\n[Test 1] Low risk skill (read-only operations)...")
    low_risk_skill = {
        "name": "Memory Status Check",
        "steps": [
            "Check memory server status",
            "Verify loaded skills",
            "List active sessions"
        ]
    }
    result = assessor.assess_skill(low_risk_skill)
    print(f"Risk level: {result['risk_level']}")
    print(f"Risk score: {result['risk_score']}")
    print(f"Safe for sandbox: {result['safe_for_sandbox']}")
    print(f"Side effects: {result['side_effects']}")

    # Test 2: Medium risk skill (configuration)
    print("\n[Test 2] Medium risk skill (configuration)...")
    medium_risk_skill = {
        "name": "Server Configuration",
        "steps": [
            "Configure server port to 8765",
            "Setup database connection",
            "Initialize memory manager",
            "Start service"
        ]
    }
    result = assessor.assess_skill(medium_risk_skill)
    print(f"Risk level: {result['risk_level']}")
    print(f"Risk score: {result['risk_score']}")
    print(f"Safe for sandbox: {result['safe_for_sandbox']}")
    print(f"Dependencies: {result['dependencies']}")

    # Test 3: High risk skill (destructive)
    print("\n[Test 3] High risk skill (destructive operations)...")
    high_risk_skill = {
        "name": "Database Cleanup",
        "steps": [
            "Delete old sessions",
            "Drop temporary tables",
            "Purge expired cache"
        ]
    }
    result = assessor.assess_skill(high_risk_skill)
    print(f"Risk level: {result['risk_level']}")
    print(f"Irreversible: {result['irreversible']}")
    print(f"Warnings: {result['warnings']}")

    print("\n" + "=" * 60)
    print("RiskAssessor tests complete!")
    print("=" * 60)


def test_sandbox_execution():
    print("\n" + "=" * 60)
    print("Testing Sandbox Execution")
    print("=" * 60)

    manager = MemoryManager()
    manager.load(session_id="sandbox-test")

    executor = SkillExecutor(memory_manager=manager)

    # Test 1: Sandbox execution of memory config skill
    print("\n[Test 1] Sandbox: Memory Configuration...")
    skill = executor.find_matching_skill("how to configure memory?")

    if skill:
        print(f"Found skill: {skill['name']}")

        # Execute in sandbox mode
        result = executor.execute_skill(skill, sandbox=True)

        print(f"Sandbox mode: {result.get('sandbox')}")
        print(f"Risk level: {result.get('risk_level')}")
        print(f"Risk score: {result.get('risk_score')}")
        print(f"Safe to execute: {result.get('safe_to_execute')}")
        print(f"Total steps: {result.get('total_steps')}")

        # Show step simulations
        print("\nStep simulations:")
        for sim in result.get('step_simulations', [])[:3]:
            print(f"  {sim['step_number']}. {sim['action']}: {sim['predicted_outcome']}")
            print(f"     Side effects: {sim['has_side_effects']}, Reversible: {sim['reversible']}")

        # Show warnings
        if result.get('warnings'):
            print(f"\nWarnings: {result['warnings']}")
    else:
        print("No matching skill found")

    # Test 2: Compare sandbox vs real execution
    print("\n[Test 2] Compare sandbox vs real execution...")
    skill = executor.find_matching_skill("check memory status")

    if skill:
        # Sandbox
        sandbox_result = executor.execute_skill(skill, sandbox=True)
        print(f"Sandbox - Steps: {sandbox_result['total_steps']}, Risk: {sandbox_result['risk_level']}")

        # Real execution
        real_result = executor.execute_skill(skill, sandbox=False)
        print(f"Real - Steps: {real_result['total_steps']}, Success: {real_result['success']}")

    print("\n" + "=" * 60)
    print("Sandbox execution tests complete!")
    print("=" * 60)


def test_step_simulation():
    print("\n" + "=" * 60)
    print("Testing Step Simulation")
    print("=" * 60)

    manager = MemoryManager()
    manager.load(session_id="simulation-test")

    executor = SkillExecutor(memory_manager=manager)

    # Test different action types
    test_steps = [
        {"action": "check", "target": "memory server", "raw": "Check memory server status"},
        {"action": "initialize", "target": "manager", "raw": "Initialize MemoryManager"},
        {"action": "load", "target": "memory", "raw": "Load MEMORY.md and USER.md"},
        {"action": "configure", "target": "port", "parameters": {"port": 8765}, "raw": "Configure port 8765"},
        {"action": "start", "target": "service", "parameters": {"port": 4321}, "raw": "Start service on port 4321"},
        {"action": "send", "target": "webhook", "raw": "Send to Discord webhook"},
        {"action": "delete", "target": "old sessions", "raw": "Delete expired sessions"},
    ]

    print("\nSimulating different step types:")
    for i, step in enumerate(test_steps, 1):
        sim = executor._simulate_step(step, {}, step_number=i)
        print(f"\n  {i}. {sim['action'].upper()}: {sim['target']}")
        print(f"     Predicted: {sim['predicted_outcome']}")
        print(f"     Side effects: {sim['has_side_effects']}")
        print(f"     Reversible: {sim['reversible']}")

    print("\n" + "=" * 60)
    print("Step simulation tests complete!")
    print("=" * 60)


def test_memory_manager_integration():
    print("\n" + "=" * 60)
    print("Testing MemoryManager Integration")
    print("=" * 60)

    manager = MemoryManager()
    manager.load(session_id="manager-sandbox-test")

    # Test 1: Execute skill in sandbox mode via manager
    print("\n[Test 1] Sandbox execution via MemoryManager...")
    result = manager.execute_skill(user_input="how to setup memory", sandbox=True)

    if result.get('sandbox'):
        print(f"Skill: {result.get('skill_name')}")
        print(f"Risk level: {result.get('risk_level')}")
        print(f"Safe to execute: {result.get('safe_to_execute')}")

    # Test 2: Risk assessment via manager
    print("\n[Test 2] Risk assessment via MemoryManager...")
    result = manager.assess_skill_risk(user_input="Changkong bot setup")

    print(f"Risk level: {result.get('risk_level', 'N/A')}")
    print(f"Risk score: {result.get('risk_score', 'N/A')}")
    print(f"Irreversible: {result.get('irreversible', 'N/A')}")
    print(f"Warnings: {result.get('warnings', [])}")

    # Test 3: Real execution for comparison
    print("\n[Test 3] Real execution for comparison...")
    result = manager.execute_skill(user_input="verify memory loaded", sandbox=False)

    print(f"Success: {result.get('success')}")
    print(f"Steps completed: {result.get('success_count', 0)}/{result.get('total_steps', 0)}")

    print("\n" + "=" * 60)
    print("MemoryManager integration tests complete!")
    print("=" * 60)


if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    test_risk_assessor()
    test_sandbox_execution()
    test_step_simulation()
    test_memory_manager_integration()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)

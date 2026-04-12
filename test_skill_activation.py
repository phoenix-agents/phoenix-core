#!/usr/bin/env python3
"""
Test script for Skill Activation System

Tests:
1. SkillActivator initialization
2. Skill loading and parsing
3. Trigger keyword extraction
4. Skill recommendation
5. Active skill detection
6. Integration with MemoryManager
"""

import sys
sys.path.insert(0, str(Path(__file__).parent))

from skill_activation import SkillActivator
from memory_manager import MemoryManager


def test_skill_activator():
    print("=" * 60)
    print("Testing SkillActivator")
    print("=" * 60)

    # Create manager and activator
    manager = MemoryManager()
    manager.load(session_id="skill-activation-test")

    activator = SkillActivator(memory_manager=manager)

    # Test 1: Load skills
    print("\n[Test 1] Loading skills...")
    skills = activator.load_skills()
    print(f"Loaded {len(skills)} skills")
    for skill in skills:
        print(f"  - {skill['name']}")

    # Test 2: Check trigger keywords
    print("\n[Test 2] Checking trigger keywords...")
    for skill in skills[:2]:
        print(f"  {skill['name']}: {skill['trigger_keywords'][:5]}")

    # Test 3: Recommend skills for memory query
    print("\n[Test 3] Testing recommendation for 'how to configure memory'...")
    recs = activator.recommend_skills("how to configure memory", threshold=0.1)
    print(f"Recommendations: {len(recs)}")
    for skill, score in recs[:3]:
        print(f"  - {skill['name']} (score: {score:.2f})")

    # Test 4: Recommend skills for Changkong query
    print("\n[Test 4] Testing recommendation for 'Changkong bot setup'...")
    recs = activator.recommend_skills("Changkong bot setup for field control", threshold=0.1)
    print(f"Recommendations: {len(recs)}")
    for skill, score in recs[:3]:
        print(f"  - {skill['name']} (score: {score:.2f})")

    # Test 5: Get active skill
    print("\n[Test 5] Getting active skill for 'memory configuration'...")
    skill = activator.get_active_skill("how do I configure the memory system", threshold=0.3)
    if skill:
        print(f"Active skill: {skill['name']}")
        print(f"Description: {skill['description'][:80]}...")
    else:
        print("No active skill found")

    # Test 6: Format skill context
    print("\n[Test 6] Formatting skill context...")
    if skill:
        context = activator.format_skill_context(skill)
        print(f"Context preview: {context[:200]}...")

    # Test 7: Status
    print("\n[Test 7] Checking activator status...")
    status = activator.get_status()
    print(f"Status: {status}")

    print("\n" + "=" * 60)
    print("SkillActivator tests complete!")
    print("=" * 60)


def test_memory_manager_integration():
    print("\n" + "=" * 60)
    print("Testing MemoryManager Integration")
    print("=" * 60)

    # Create manager
    manager = MemoryManager()
    manager.load(session_id="integration-test")

    # Test 1: Check activator exists
    print("\n[Test 1] Checking skill activator...")
    print(f"Has _skill_activator: {hasattr(manager, '_skill_activator')}")

    # Test 2: Get status
    print("\n[Test 2] Getting skill activator status...")
    status = manager.get_skill_activator_status()
    print(f"Status: {status}")

    # Test 3: Recommend skills via manager
    print("\n[Test 3] Recommending skills via manager...")
    recs = manager.recommend_skills("Changkong field control configuration", threshold=0.1)
    print(f"Recommendations: {len(recs)}")
    for skill, score in recs[:2]:
        print(f"  - {skill['name']} (score: {score:.2f})")

    # Test 4: Get active skill via manager
    print("\n[Test 4] Getting active skill via manager...")
    skill = manager.get_active_skill("how to setup memory configuration", threshold=0.3)
    if skill:
        print(f"Active skill: {skill['name']}")
    else:
        print("No active skill found")

    # Test 5: Build skill context
    print("\n[Test 5] Building skill context...")
    context = manager.build_skill_context("how to configure Changkong bot for live monitoring")
    if context:
        print(f"Context generated ({len(context)} chars)")
        print(f"Preview: {context[:150]}...")
    else:
        print("No context generated")

    # Test 6: Low threshold test
    print("\n[Test 6] Testing with low threshold (0.2)...")
    context = manager.build_skill_context("Discord output setup", threshold=0.2)
    if context:
        print(f"Context generated with lower threshold")
    else:
        print("Still no context - topic may not match existing skills")

    print("\n" + "=" * 60)
    print("MemoryManager integration tests complete!")
    print("=" * 60)


def test_edge_cases():
    print("\n" + "=" * 60)
    print("Testing Edge Cases")
    print("=" * 60)

    manager = MemoryManager()
    manager.load(session_id="edge-case-test")
    activator = manager._skill_activator

    # Test 1: Empty input
    print("\n[Test 1] Empty input...")
    recs = activator.recommend_skills("")
    print(f"Recommendations for empty input: {len(recs)}")

    # Test 2: Random input
    print("\n[Test 2] Random unrelated input...")
    recs = activator.recommend_skills("what is the weather like today")
    print(f"Recommendations for random input: {len(recs)}")

    # Test 3: Very specific input
    print("\n[Test 3] Very specific input...")
    recs = activator.recommend_skills("start live-monitor service port 4321 5 minute Discord webhook")
    print(f"Recommendations for specific input: {len(recs)}")
    for skill, score in recs:
        print(f"  - {skill['name']} (score: {score:.2f})")

    # Test 4: Case insensitivity
    print("\n[Test 4] Case insensitivity...")
    recs1 = activator.recommend_skills("MEMORY Configuration")
    recs2 = activator.recommend_skills("memory configuration")
    print(f"Uppercase recs: {len(recs1)}, Lowercase recs: {len(recs2)}")
    print(f"Same results: {len(recs1) == len(recs2)}")

    print("\n" + "=" * 60)
    print("Edge case tests complete!")
    print("=" * 60)


if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    test_skill_activator()
    test_memory_manager_integration()
    test_edge_cases()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)

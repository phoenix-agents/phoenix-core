#!/usr/bin/env python3
"""
Test script for Background Review Agent

Tests:
1. BackgroundReviewAgent initialization
2. Spawn review
3. Skill extraction from conversation
4. Integration with MemoryManager
5. Queue handling
"""

import sys
import time
sys.path.insert(0, str(Path(__file__).parent))

from background_review import BackgroundReviewAgent
from memory_manager import MemoryManager


def test_background_review_agent():
    print("=" * 60)
    print("Testing BackgroundReviewAgent")
    print("=" * 60)

    # Create manager and agent
    manager = MemoryManager()
    manager.load(session_id="background-review-test")

    agent = BackgroundReviewAgent(memory_manager=manager)

    # Test 1: Spawn review with meaningful conversation
    print("\n[Test 1] Spawning background review...")
    user_content = "How do I configure the Changkong bot for field control?"
    assistant_content = """To configure Changkong bot:
1. Start live-monitor service on port 4321
2. Set analysis interval to 5 minutes
3. Configure Discord webhook for output
4. Test the connection

This is the standard procedure for field control setup."""

    agent.spawn_review(user_content, assistant_content)

    # Wait for background processing
    print("Waiting for background processing...")
    for i in range(30):
        status = agent.get_status()
        if not status["is_processing"]:
            print(f"Processing complete after {i+1} seconds")
            break
        time.sleep(1)

    # Check skills created
    result = manager._skill_store.read()
    print(f"Skills in SKILL.md: {result['count']}")
    print(f"Usage: {result['usage']}")

    # Test 2: Check status
    print("\n[Test 2] Checking agent status...")
    status = agent.get_status()
    print(f"Status: {status}")

    # Test 3: Multiple reviews (queue test)
    print("\n[Test 3] Testing queue with multiple reviews...")
    agent.spawn_review("Question 1", "Answer 1")
    agent.spawn_review("Question 2", "Answer 2")
    status = agent.get_status()
    print(f"Queue size after 2 spawns: {status['queue_size']}")

    # Wait for queue to process
    print("Waiting for queue processing...")
    time.sleep(5)
    status = agent.get_status()
    print(f"Queue size after processing: {status['queue_size']}")

    print("\n" + "=" * 60)
    print("BackgroundReviewAgent tests complete!")
    print("=" * 60)


def test_memory_manager_integration():
    print("\n" + "=" * 60)
    print("Testing MemoryManager Integration")
    print("=" * 60)

    # Create manager
    manager = MemoryManager()
    manager.load(session_id="integration-test")

    # Test 1: Check background review agent exists
    print("\n[Test 1] Checking background review agent...")
    print(f"Has _background_review: {hasattr(manager, '_background_review')}")

    # Test 2: Get background review status
    print("\n[Test 2] Getting background review status...")
    status = manager.get_background_review_status()
    print(f"Status: {status}")

    # Test 3: Trigger learning (should spawn background review)
    print("\n[Test 3] Triggering learning (should spawn background review)...")

    # Simulate 10 iterations to trigger learning
    for i in range(10):
        manager.sync_turn(
            user_content=f"Question {i+1} about memory configuration",
            assistant_content=f"Answer {i+1} with detailed explanation about memory setup...",
            tool_iterations=1
        )

    print("Waiting for background review to complete...")
    time.sleep(10)

    # Check status
    learner_status = manager.get_learner_status()
    review_status = manager.get_background_review_status()
    print(f"Learner status: {learner_status}")
    print(f"Review status: {review_status}")

    # Check skills
    skills = manager._skill_store.read()
    print(f"Total skills: {skills['count']}")

    print("\n" + "=" * 60)
    print("MemoryManager integration tests complete!")
    print("=" * 60)


if __name__ == "__main__":
    # Set logging
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    test_background_review_agent()
    test_memory_manager_integration()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)

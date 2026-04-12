#!/usr/bin/env python3
"""
Test Automatic Learning Feature

Simulates conversations to trigger automatic learning.
"""

import json
import urllib.request
import time

MEMORY_SERVER = "http://localhost:8765"


def test_learner_status():
    """Test getting learner status."""
    print("\n=== Test 1: Get Learner Status ===")

    req = urllib.request.Request(
        f"{MEMORY_SERVER}/memory/status",
        method="GET"
    )

    with urllib.request.urlopen(req, timeout=10) as response:
        result = json.loads(response.read().decode('utf-8'))
        print(f"Status: {result.get('status')}")
        print(f"Learner: {json.dumps(result.get('learner'), indent=2)}")
        return result.get('success', False)


def test_store_interaction(iteration=1):
    """Store a test interaction."""
    print(f"\n=== Test 2: Store Interaction #{iteration} ===")

    data = {
        "user_content": f"Test question #{iteration}: How to configure the memory system?",
        "assistant_content": f"Test answer #{iteration}: To configure the memory system, follow these steps: 1) Start the memory server. 2) Configure agent to use memory endpoint. 3) Test with /memory/context. This is a simulated response for testing automatic learning.",
        "tool_iterations": 2
    }

    req = urllib.request.Request(
        f"{MEMORY_SERVER}/memory/store",
        data=json.dumps(data).encode('utf-8'),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=10) as response:
        result = json.loads(response.read().decode('utf-8'))
        print(f"Stored: {result.get('success')}")
        return result.get('success', False)


def test_memory_context():
    """Test getting memory context."""
    print("\n=== Test 3: Get Memory Context ===")

    req = urllib.request.Request(
        f"{MEMORY_SERVER}/memory/context",
        method="GET"
    )

    with urllib.request.urlopen(req, timeout=10) as response:
        result = json.loads(response.read().decode('utf-8'))
        context = result.get('context', '')
        print(f"Context length: {len(context)} chars")
        if context:
            print(f"Preview: {context[:200]}...")
        return result.get('success', False)


def main():
    print("========================================")
    print("     Automatic Learning Feature Test")
    print("========================================")

    # Test 1: Initial status
    if not test_learner_status():
        print("❌ Test 1 failed")
        return

    # Test 2: Store multiple interactions to trigger learning
    print("\n--- Storing 5 interactions (10 tool iterations) ---")
    for i in range(5):
        if not test_store_interaction(i + 1):
            print(f"❌ Failed to store interaction {i + 1}")
        time.sleep(0.5)

    # Test 3: Check learner status after interactions
    print("\n--- Checking learner status after interactions ---")
    time.sleep(2)  # Wait for background processing
    if not test_learner_status():
        print("❌ Failed to get status")
        return

    # Test 4: Get memory context
    if not test_memory_context():
        print("❌ Test 4 failed")
        return

    print("\n========================================")
    print("          All tests completed!")
    print("========================================")
    print("\nNote: Automatic learning triggers in background.")
    print("Check /tmp/memory_server.log for learning output.")


if __name__ == "__main__":
    main()

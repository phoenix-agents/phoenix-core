#!/usr/bin/env python3
"""
Test script for Phoenix Core memory system
"""

import sys
import json
sys.path.insert(0, str(Path(__file__).parent))

from memory_manager import MemoryManager
from session_store import SessionStore

def test_memory_store():
    print("=" * 50)
    print("Testing Memory Store")
    print("=" * 50)

    manager = MemoryManager()
    manager.load(session_id="test-001")

    # Test read initial state
    print("\n1. Initial memory state:")
    result = manager.handle_tool_call("memory", {"action": "read", "target": "memory"})
    print(result)

    # Test add memory
    print("\n2. Add memory entry:")
    result = manager.handle_tool_call("memory", {
        "action": "add",
        "target": "memory",
        "content": "测试记忆条目 1"
    })
    print(result)

    # Test add user preference
    print("\n3. Add user preference:")
    result = manager.handle_tool_call("memory", {
        "action": "add",
        "target": "user",
        "content": "用户喜欢简洁的回答"
    })
    print(result)

    # Test build memory context
    print("\n4. Memory context for system prompt:")
    context = manager.build_memory_context()
    print(context)

    # Test read after add
    print("\n5. Read memory after additions:")
    result = manager.handle_tool_call("memory", {"action": "read", "target": "memory"})
    print(result)

    # Test replace
    print("\n6. Replace memory entry:")
    result = manager.handle_tool_call("memory", {
        "action": "replace",
        "target": "memory",
        "old_text": "测试记忆条目 1",
        "new_content": "更新后的测试记忆"
    })
    print(result)

    # Test search (should show the updated entry)
    print("\n7. Read final state:")
    result = manager.handle_tool_call("memory", {"action": "read", "target": "memory"})
    print(result)

    manager.shutdown()
    print("\nMemory store test complete!")


def test_session_store():
    print("\n" + "=" * 50)
    print("Testing Session Store")
    print("=" * 50)

    store = SessionStore()

    # Create a test session
    session_id = "test-session-001"
    print(f"\n1. Create session: {session_id}")
    created = store.create_session(session_id, source='test', model='qwen-2.5')
    print(f"Created: {created}")

    # Add messages
    print("\n2. Add messages:")
    store.append_message(session_id, "user", "你好，我想查询场控 Bot 的配置")
    store.append_message(session_id, "assistant", "好的，让我帮你查找场控 Bot 的配置信息",
                         tool_name="memory", tool_calls=[{"name": "memory"}])
    store.append_message(session_id, "user", "场控的数据源是什么？")
    store.append_message(session_id, "assistant", "场控 Bot 从 4321 端口读取直播数据",
                         tool_name="exec", finish_reason="stop")
    print("Messages added")

    # Get messages
    print("\n3. Get session messages:")
    messages = store.get_messages(session_id)
    for msg in messages:
        print(f"  [{msg['role']}] {msg['content'][:50]}...")

    # Search
    print("\n4. Search for '场控':")
    results = store.search("场控", limit=5)
    for r in results:
        print(f"  - [{r['role']}] {r.get('snippet', r['content'][:50])}")

    # List sessions
    print("\n5. List recent sessions:")
    sessions = store.list_sessions(limit=5)
    for s in sessions:
        print(f"  - {s['session_id']} | {s['source']} | {s['model']}")

    store.close()
    print("\nSession store test complete!")


def test_learning_loop():
    print("\n" + "=" * 50)
    print("Testing Learning Loop")
    print("=" * 50)

    manager = MemoryManager()
    manager.load(session_id="test-learning-001")

    learning_triggers = []

    def on_learning(user_content, assistant_content):
        learning_triggers.append({
            "user": user_content[:100],
            "assistant": assistant_content[:100]
        })
        print(f"  [LEARNING TRIGGER] User: {user_content[:50]}...")

    manager.set_learning_trigger_callback(on_learning)

    # Simulate multiple turns with tool iterations
    print("\n1. Simulating 12 tool iterations (threshold=10):")
    for i in range(12):
        manager.sync_turn(
            user_content=f"Message {i}",
            assistant_content=f"Response {i}",
            tool_iterations=1
        )
        print(f"  Iteration {i+1}, counter={manager._iters_since_learning}")

    print(f"\n2. Total learning triggers: {len(learning_triggers)}")
    for trigger in learning_triggers:
        print(f"  - {trigger['user']}")

    manager.shutdown()
    print("\nLearning loop test complete!")


if __name__ == "__main__":
    test_memory_store()
    test_session_store()
    test_learning_loop()
    print("\n" + "=" * 50)
    print("All tests completed!")
    print("=" * 50)

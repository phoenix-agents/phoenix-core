#!/usr/bin/env python3
"""
Test script for Skill System

Tests:
1. Create SkillStore
2. Add skills
3. Read skills
4. Search skills
5. Replace skills
6. Remove skills
7. Integration with MemoryManager
"""

import sys
sys.path.insert(0, str(Path(__file__).parent))

from skill_store import SkillStore, SKILL_TOOL_SCHEMA, skill_tool
from memory_manager import MemoryManager

def test_skill_store():
    print("=" * 60)
    print("Testing SkillStore")
    print("=" * 60)

    # Create store
    store = SkillStore()
    store.load_from_disk()

    # Test 1: Add skill
    print("\n[Test 1] Adding skill...")
    result = store.add("""[SKILL] Memory Configuration Setup
Description: Standard procedure for configuring memory system
Triggers: When user asks about memory setup or configuration
Steps:
1. Check if memory server is running on port 8765
2. Initialize MemoryManager with session_id
3. Call load() to load MEMORY.md and USER.md
4. Inject memory context into system prompt
Examples: Used when setting up new agent sessions""")
    print(f"Result: {result['success']} - {result.get('message', result.get('error', ''))}")

    # Test 2: Read skills
    print("\n[Test 2] Reading skills...")
    result = store.read()
    print(f"Skill count: {result['count']}")
    print(f"Usage: {result['usage']}")

    # Test 3: Search skills
    print("\n[Test 3] Searching skills for 'memory'...")
    result = store.search("memory", limit=5)
    print(f"Search results: {result['count']} matches")
    if result['matches']:
        print(f"First match preview: {result['matches'][0][:100]}...")

    # Test 4: Add another skill
    print("\n[Test 4] Adding second skill...")
    result = store.add("""[SKILL] Changkong Bot Configuration
Description: Field control bot setup for live data analysis
Triggers: When user mentions Changkong, field control, or port 4321
Steps:
1. Start live-monitor service on port 4321
2. Configure 5-minute analysis interval
3. Setup Discord output channel
4. Test data stream connectivity
Examples: Used for live stream monitoring""")
    print(f"Result: {result['success']} - {result.get('message', result.get('error', ''))}")

    # Test 5: Read all skills
    print("\n[Test 5] Reading all skills...")
    result = store.read()
    print(f"Total skills: {result['count']}")
    print(f"Usage: {result['usage']}")

    # Test 6: Skill tool integration
    print("\n[Test 6] Testing skill_tool function...")
    result = skill_tool(action="read", store=store)
    print(f"Tool result type: {type(result)}")

    # Test 7: Duplicate rejection
    print("\n[Test 7] Testing duplicate rejection...")
    result = store.add("""[SKILL] Memory Configuration Setup
Description: Standard procedure for configuring memory system""")
    print(f"Duplicate rejected: {not result['success']}")

    print("\n" + "=" * 60)
    print("SkillStore tests complete!")
    print("=" * 60)


def test_memory_manager_integration():
    print("\n" + "=" * 60)
    print("Testing MemoryManager Integration")
    print("=" * 60)

    # Create manager
    manager = MemoryManager()
    manager.load(session_id="skill-test")

    # Test tool schemas
    print("\n[Test 1] Checking tool schemas...")
    schemas = manager.get_tool_schemas()
    print(f"Total schemas: {len(schemas)}")
    schema_names = [s['name'] for s in schemas]
    print(f"Tools: {schema_names}")
    print(f"skill_manage included: {'skill_manage' in schema_names}")

    # Test add skill via manager
    print("\n[Test 2] Adding skill via MemoryManager...")
    result = manager.add_skill("[SKILL] Test Skill\nDescription: Integration test skill")
    print(f"Add result: {result}")

    # Test search skills via manager
    print("\n[Test 3] Searching skills via MemoryManager...")
    result = manager.search_skills("test", limit=5)
    print(f"Search result: {result['count']} matches")

    # Test handle_tool_call
    print("\n[Test 4] Testing handle_tool_call...")
    result = manager.handle_tool_call("skill_manage", {
        "action": "read"
    })
    print(f"Tool call result type: {type(result)}")

    print("\n" + "=" * 60)
    print("MemoryManager integration tests complete!")
    print("=" * 60)


if __name__ == "__main__":
    test_skill_store()
    test_memory_manager_integration()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)

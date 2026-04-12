#!/usr/bin/env python3
"""
AI Data Push with Memory Integration

This script:
1. Fetches live stream data from port 4321
2. Loads memory context from Phoenix Core memory system
3. Calls AI analysis with memory-enhanced prompt
4. Stores results in session database
5. Pushes suggestion to port 4321

Usage:
    python3 ai_push_with_memory.py
"""

import sys
import json
import urllib.request
import urllib.error
from datetime import datetime

# Add phoenix-core to path
sys.path.insert(0, str(Path(__file__).parent))

from memory_manager import MemoryManager

# Configuration
API_BASE = "http://localhost:4321"
MEMORY_MANAGER = None
SESSION_ID = None


def init_memory():
    """Initialize memory system"""
    global MEMORY_MANAGER, SESSION_ID

    SESSION_ID = f"ai-push-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    MEMORY_MANAGER = MemoryManager()
    MEMORY_MANAGER.load(session_id=SESSION_ID)

    print(f"[Memory] Loaded session {SESSION_ID}")

    # Get memory context
    memory_context = MEMORY_MANAGER.build_memory_context()
    if memory_context:
        print(f"[Memory] Context loaded ({len(memory_context)} chars)")
    else:
        print("[Memory] No memory context available")

    return memory_context


def fetch_live_data():
    """Fetch live stream dashboard data from port 4321"""
    try:
        url = f"{API_BASE}/api/agent/dashboard"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get('data', {})
    except Exception as e:
        print(f"[Error] Failed to fetch live data: {e}")
        return None


def call_ai_with_memory(data: dict, memory_context: str) -> dict:
    """
    Call AI analysis with memory-enhanced prompt

    Two approaches:
    1. Use existing 4321 API (simple)
    2. Call Gateway API directly with memory context (recommended)
    """

    # Approach 1: Use existing /api/jianyi/analyze endpoint
    session = data.get('session', {})
    realtime = data.get('realtime', {})
    profile = data.get('profile', {})
    trends = data.get('trends', {})

    payload = {
        "agent_id": "jianyi",
        "session_id": session.get('session_id', ''),
        "trigger_type": "periodic",
        "data": {
            "realtime": realtime,
            "profile": profile,
            "trends": trends
        },
        "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        # Add memory context
        "memory_context": memory_context
    }

    try:
        url = f"{API_BASE}/api/jianyi/analyze"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            return result
    except urllib.error.HTTPError as e:
        print(f"[Error] AI analysis failed: {e.code} - {e.read().decode()}")
        return None
    except Exception as e:
        print(f"[Error] AI analysis failed: {e}")
        return None


def call_gateway_with_memory(data: dict, memory_context: str) -> str:
    """
    Call Gateway API directly with memory context
    This uses the real Changkong bot with full knowledge base
    """

    realtime = data.get('realtime', {})

    # Build enhanced prompt with memory
    prompt = f"""{memory_context}

Current live stream data:
- Online viewers: {realtime.get('online_viewers', 0)}
- Total viewers: {realtime.get('total_viewers', 0)}
- Comments: {realtime.get('comments_count', 0)}
- Gifts: {realtime.get('gifts_count', 0)}
- Likes: {realtime.get('likes_count', 0)}
- Shares: {realtime.get('shares_count', 0)}

Please provide a concise, actionable suggestion (50 characters max in Chinese)."""

    gateway_endpoint = "http://localhost:18789/v1/chat/completions"
    gateway_token = "clawx-cbdb04ecfd55e3f3198e373baeaf5ee1"

    try:
        req = urllib.request.Request(
            gateway_endpoint,
            data=json.dumps({
                "model": "phoenix/changkong",
                "messages": [
                    {
                        "role": "system",
                        "content": "你是场控 Bot，谦歌行 277 直播团队的气氛控制专家。你有丰富的直播运营知识库。请根据直播数据，简洁、直接地给出可执行的建议（50 字以内）。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 150,
                "temperature": 0.7,
                "stream": False
            }).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {gateway_token}'
            },
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            suggestion = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            return suggestion

    except Exception as e:
        print(f"[Error] Gateway call failed: {e}")
        return None


def push_suggestion(suggestion: str, priority: str = "medium"):
    """Push suggestion to port 4321 /api/push/suggestion endpoint"""

    payload = {
        "suggestion": suggestion,
        "priority": priority,
        "source": "memory-enhanced-ai"
    }

    try:
        url = f"{API_BASE}/api/push/suggestion"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            print(f"[Push] Suggestion pushed: {result.get('message', '')}")
            return True
    except Exception as e:
        print(f"[Error] Push failed: {e}")
        return False


def store_result(data: dict, suggestion: str):
    """Store analysis result in session database"""
    if MEMORY_MANAGER:
        # Store in session
        user_content = f"AI analysis request with live data: viewers={data.get('realtime', {}).get('online_viewers', 0)}"
        assistant_content = f"AI suggestion: {suggestion}"

        MEMORY_MANAGER.sync_turn(
            user_content=user_content,
            assistant_content=assistant_content,
            tool_iterations=1
        )
        print("[Memory] Result stored in session")


def search_memory(query: str):
    """Search memory for past analyses"""
    if not MEMORY_MANAGER:
        return []

    results = MEMORY_MANAGER.search_sessions(query, limit=5)
    print(f"\n[Search] Found {len(results)} results for '{query}':")
    for r in results:
        print(f"  - [{r.get('created_at', 'unknown')}] {r.get('content', '')[:80]}...")
    return results


def main():
    """Main entry point"""
    print("=" * 50)
    print("AI Data Push with Memory Integration")
    print("=" * 50)

    # Step 1: Initialize memory
    memory_context = init_memory()

    # Step 2: Fetch live data
    print("\n[Step 1] Fetching live data...")
    data = fetch_live_data()
    if not data:
        print("[Error] Failed to fetch live data")
        return

    realtime = data.get('realtime', {})
    print(f"[OK] Online viewers: {realtime.get('online_viewers', 0)}")

    # Step 3: Optional - search past analyses
    # Uncomment to enable:
    # search_memory("场控")

    # Step 4: Call AI with memory context
    print("\n[Step 2] Calling AI with memory context...")

    # Option A: Use Gateway API (recommended)
    suggestion = call_gateway_with_memory(data, memory_context)

    # Option B: Use existing 4321 API
    # result = call_ai_with_memory(data, memory_context)
    # suggestion = result.get('suggestion', '') if result else ''

    if not suggestion:
        print("[Error] AI returned no suggestion")
        return

    print(f"[OK] AI suggestion: {suggestion}")

    # Step 5: Store result in memory
    print("\n[Step 3] Storing result...")
    store_result(data, suggestion)

    # Step 6: Push suggestion
    print("\n[Step 4] Pushing suggestion...")
    push_suggestion(suggestion, priority="medium")

    # Step 7: End session
    if MEMORY_MANAGER:
        MEMORY_MANAGER.shutdown()

    print("\n[Done] AI push complete!")


if __name__ == "__main__":
    from datetime import timezone
    main()

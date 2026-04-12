#!/usr/bin/env python3
"""
Test Learning Loop - 测试学习循环是否正常工作

验证：
1. MemoryManager 记录会话
2. AutomaticLearner 触发学习
3. 知识点写入 MEMORY.md
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from memory_manager import MemoryManager

def test_learning_loop():
    """测试学习循环"""
    print("=" * 50)
    print("测试学习循环")
    print("=" * 50)

    # 初始化 MemoryManager
    manager = MemoryManager()
    manager.load(session_id="test-learning-001")

    print(f"✅ MemoryManager 已加载")
    print(f"   学习阈值：{manager._learning_threshold} 次工具调用")
    print(f"   当前计数：{manager._iters_since_learning}")

    # 模拟 10 次工具调用
    print("\n📝 模拟 10 次工具调用...")
    for i in range(10):
        manager.sync_turn(
            user_content=f"测试消息 {i+1}",
            assistant_content=f"这是测试回复 {i+1}",
            tool_iterations=1
        )
        print(f"   第 {i+1} 次调用完成")

    # 等待异步学习完成
    import time
    print("\n⏳ 等待异步学习完成 (5 秒)...")
    time.sleep(5)

    # 检查 MEMORY.md 是否有新内容
    from memory_store import get_memory_dir
    memory_file = get_memory_dir() / "MEMORY.md"

    if memory_file.exists():
        with open(memory_file, 'r', encoding='utf-8') as f:
            content = f.read()

        print(f"\n📄 MEMORY.md 内容 ({len(content)} 字符):")
        print("-" * 30)
        print(content[-1000:])  # 显示最后 1000 字符
        print("-" * 30)

    # 检查 AutomaticLearner 状态
    learner = manager._automatic_learner
    print(f"\n📊 AutomaticLearner 状态:")
    print(f"   迭代计数：{learner._iteration_count}")
    print(f"   对话缓冲：{len(learner._conversation_buffer)} 条")
    print(f"   是否在处理：{learner._is_processing}")

    print("\n✅ 测试完成!")

if __name__ == "__main__":
    test_learning_loop()

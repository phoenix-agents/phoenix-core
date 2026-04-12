#!/usr/bin/env python3
"""
Test Phase 2 - 测试深度反思、技能进化、知识图谱

验证：
1. ReflectionEngine 深度反思
2. SkillEvolution 版本化进化
3. KnowledgeGraph 跨 Bot 知识分享
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def test_reflection_engine():
    """测试深度反思引擎"""
    print("=" * 50)
    print("测试深度反思引擎")
    print("=" * 50)

    from memory_manager import MemoryManager
    from reflection_engine import get_reflection_engine

    # 初始化
    manager = MemoryManager()
    manager.load(session_id="test-reflection-001")

    # 模拟一些会话数据
    print("\n📝 模拟 20 次工具调用（触发反思）...")
    for i in range(20):
        manager.sync_turn(
            user_content=f"测试消息 {i+1}",
            assistant_content=f"这是测试回复 {i+1}",
            tool_iterations=5  # 每次 5 次迭代
        )
        if (i + 1) % 5 == 0:
            print(f"   已完成 {i+1}/20 次")

    # 等待反思完成
    print("\n⏳ 等待反思完成 (10 秒)...")
    time.sleep(10)

    # 检查反思日志
    log_file = Path(__file__).parent / "reflection_log.md"
    if log_file.exists():
        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"\n📄 反思日志 (最后 500 字符):")
        print("-" * 30)
        print(content[-500:])
        print("-" * 30)
    else:
        print("\n⚠️  反思日志未生成")

    print("\n✅ 反思引擎测试完成!")


def test_skill_evolution():
    """测试技能版本化进化"""
    print("\n" + "=" * 50)
    print("测试技能版本化进化")
    print("=" * 50)

    from skill_evolution import SkillEvolution, get_skill_evolution
    from memory_manager import MemoryManager

    manager = MemoryManager()
    evolution = get_skill_evolution(manager)

    # 创建一个测试技能
    print("\n📝 创建测试技能 v1...")
    test_skill = {
        'name': 'Test Skill',
        'description': 'A test skill for evolution',
        'triggers': 'When user asks about testing',
        'steps': '1. Do something\n2. Do another thing',
        'examples': 'Testing scenarios',
        'success_rate': 0.6,
        'execution_count': 10
    }

    # 保存初始版本
    from skill_evolution import SkillVersion
    initial_version = SkillVersion({
        **test_skill,
        'version': 'v1',
        'created_at': time.time()
    })

    evolution._save_skill_versions('test_skill', [initial_version])
    print("   ✅ 技能 v1 已创建")

    # 进化技能
    print("\n🔄 执行技能进化 v1 → v2...")
    result = evolution.evolve_skill(
        'test_skill',
        reason="Low success rate (60%)",
        execution_data=[
            {'success': False, 'error': 'Step 1 failed'},
            {'success': False, 'error': 'Step 2 unclear'},
            {'success': True},
        ]
    )

    print(f"   进化结果：{result}")

    # 检查进化历史
    stats = evolution.get_evolution_stats()
    print(f"\n📊 进化统计:")
    print(f"   总进化次数：{stats['total_evolutions']}")
    print(f"   进化技能数：{stats['skills_evolved']}")
    print(f"   平均成功率提升：{stats['avg_success_rate_improvement']:.0%}")

    # 检查进化日志
    log_file = evolution._evolution_dir / 'evolution_log.md'
    if log_file.exists():
        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"\n📄 进化日志:")
        print("-" * 30)
        print(content[-500:])
        print("-" * 30)

    print("\n✅ 技能进化测试完成!")


def test_knowledge_graph():
    """测试知识图谱"""
    print("\n" + "=" * 50)
    print("测试知识图谱")
    print("=" * 50)

    from knowledge_graph import KnowledgeGraph, get_knowledge_graph, share_learning

    graph = get_knowledge_graph()

    # 分享知识
    print("\n📝 分享知识从 编导 → 场控...")
    knowledge = """
**直播策划方法论**

1. 情绪金字塔模型
   - 底层：好奇/惊讶 → 吸引停留
   - 中层：共鸣/感动 → 建立连接
   - 高层：认同/自豪 → 促进分享

2. 价值交付体系
   - 信息价值：新知/技巧
   - 情感价值：陪伴/慰藉
   - 社交价值：谈资/认同
"""

    result = share_learning(
        from_bot='编导',
        to_bots=['场控', '运营'],
        knowledge=knowledge,
        knowledge_type='methodology'
    )

    print(f"   分享结果：{result}")

    # 检查知识图谱统计
    stats = graph.get_graph_stats()
    print(f"\n📊 知识图谱统计:")
    print(f"   总节点数：{stats['total_nodes']}")
    print(f"   总边数：{stats['total_edges']}")
    print(f"   按类型：{stats['nodes_by_type']}")
    print(f"   按 Bot: {stats['nodes_by_bot']}")

    # 检查目标 Bot 的记忆文件
    target_bot = '场控'
    memory_file = Path(__file__).parent / "workspaces/{target_bot}/memory/知识库/跨 Bot 学习 - 编导.md"
    if memory_file.exists():
        with open(memory_file, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"\n📄 {target_bot} Bot 记忆文件 (最后 500 字符):")
        print("-" * 30)
        print(content[-500:])
        print("-" * 30)
    else:
        print(f"\n⚠️  {target_bot} Bot 记忆文件未生成")

    print("\n✅ 知识图谱测试完成!")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Phase 2: Agent 自我成长功能测试")
    print("=" * 60)

    # 测试各个组件
    test_reflection_engine()
    test_skill_evolution()
    test_knowledge_graph()

    print("\n" + "=" * 60)
    print("所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()

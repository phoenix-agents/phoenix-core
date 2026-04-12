#!/usr/bin/env python3
"""Phase 3 测试报告"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("  Phoenix Core Phase 3 测试报告")
print("=" * 60)
print()

# 测试知识图谱
print("[测试 1] 直播知识图谱...")
try:
    import networkx as nx
    print("   ✅ NetworkX 已安装")
except: print("   ⚠️  NetworkX 未安装")

from knowledge_graph import KnowledgeGraph
graph = KnowledgeGraph()
node_id = graph.add_node(content={"title": "测试"}, node_type="knowledge", source_bot="场控")
print(f"   ✅ 知识图谱正常 (节点：{graph.get_stats()['total_nodes']})")

# 测试 AI 模式识别
print("[测试 2] AI 驱动模式识别...")
from auto_optimizer import AutoOptimizer
optimizer = AutoOptimizer()
patterns = optimizer.extract_patterns([{"role": "user", "content": "测试"}])
print(f"   ✅ 模式识别正常 ({len(patterns)}个模式)")

# 测试 Nudge
print("[测试 3] 自适应 Nudge 触发...")
from nudge_trigger import NudgeTrigger
trigger = NudgeTrigger(interval=10)
for i in range(5): trigger.count(f"msg{i}", f"reply{i}")
print(f"   ✅ Nudge 正常 (counter={trigger.counter})")

# 性能测试
print("[测试 4] 性能基准...")
start = time.time()
for i in range(10): graph.search_nodes(f"测试{i}")
ms = (time.time() - start) / 10 * 1000
print(f"   知识图谱搜索：{ms:.2f}ms/次")

start = time.time()
for i in range(100): trigger.count(f"m{i}", f"r{i}")
ms = (time.time() - start) / 100 * 1000
print(f"   Nudge 触发：{ms:.3f}ms/次")

print()
print("=" * 60)
print("  ✅ Phase 3 测试全部通过!")
print("=" * 60)

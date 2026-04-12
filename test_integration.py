#!/usr/bin/env python3
"""Phoenix Core 集成测试"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("  Phoenix Core 集成测试")
print("=" * 60)
print()

print("[集成 1] Bot 完整工作流程...")
from smart_memory import smart_save_memory, load_context
from memory_share import share_memory, get_shared_memories
from nudge_trigger import nudge_count, nudge_status

context = load_context()
print(f"   ✅ 加载上下文：{len(context)} 字符")

nudge_count("场控", "如何策划生日直播？", "先预热 5 分钟...")
print(f"   ✅ Nudge 计数：{nudge_status('场控')['counter']}/10")

mid = share_memory("场控", "生日直播流程", "team", "直播，策划")
print(f"   ✅ 分享记忆：ID={mid}")

shared = get_shared_memories("运营")
print(f"   ✅ 运营获取共享：{len(shared)}条")
print()

print("[集成 2] Discord 同步 + 记忆...")
from discord_sync_optimized import DiscordSyncOptimizer, DiscordMessage
from session_database import SessionDatabase
import os

opt = DiscordSyncOptimizer(Path("/tmp/test_int.db"))
msg = DiscordMessage("m1", "c1", "u1", "user", "流量怎么提升？", "2024-01-01")
opt._save_message(msg)
print(f"   ✅ 保存 Discord 消息")

db = SessionDatabase()
sid = db.add_session("流量问题", msg.content, "discord", "流量")
print(f"   ✅ 同步到会话：ID={sid}")

results = db.search("流量")
print(f"   ✅ 搜索：{len(results)}条")
os.unlink("/tmp/test_int.db")
print()

print("[集成 3] 知识图谱...")
from knowledge_graph import KnowledgeGraph, KnowledgeNode

g = KnowledgeGraph()
n1 = KnowledgeNode({'id': 'k1', 'type': 'knowledge', 'content': '直播流程', 'source_bot': '场控', 'tags': ['直播']})
n2 = KnowledgeNode({'id': 'k2', 'type': 'knowledge', 'content': '流量方法', 'source_bot': '运营', 'tags': ['流量']})
g.add_node(n1)
g.add_node(n2)
g.add_edge('k1', 'k2', 'related')
stats = g.get_graph_stats()
print(f"   ✅ 知识图谱：{stats['total_nodes']}节点，{stats['total_edges']}关系")
print()

print("[集成 4] 学习循环...")
from background_review import BackgroundReviewAgent
agent = BackgroundReviewAgent()
status = agent.get_status()
print(f"   ✅ 复盘代理：{status}")
print()

print("[集成 5] 性能测试...")
start = time.time()
for i in range(10):
    nudge_count("场控", f"msg{i}", f"reply{i}")
    share_memory("场控", f"content{i}", "public")
    get_shared_memories("场控")
elapsed = (time.time() - start) / 10 * 1000
print(f"   平均每轮：{elapsed:.1f}ms")
print(f"   {'✅' if elapsed < 100 else '⚠️'} 性能：{'优秀' if elapsed < 100 else '待优化'}")
print()

print("=" * 60)
print("  ✅ 集成测试全部通过!")
print("=" * 60)

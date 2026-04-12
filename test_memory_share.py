#!/usr/bin/env python3
"""
跨 Bot 记忆共享系统 - 快速测试
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from memory_share import MemoryShareManager, get_share_manager, share_memory, get_shared_memories, search_memories

print("=" * 60)
print("  Phoenix Core 跨 Bot 记忆共享系统测试")
print("=" * 60)
print()

# 使用临时数据库
TEST_DB = Path("/tmp/test_memory_share.db")
if TEST_DB.exists():
    TEST_DB.unlink()

manager = MemoryShareManager(TEST_DB)

# ============= 测试 1: 基础共享 =============
print("[测试 1] 基础记忆共享...")

memory_id = manager.share_memory("场控", "测试内容", "public", "测试")
assert memory_id > 0

memories = get_shared_memories("场控")
assert len(memories) > 0

print("✅ 基础共享正常")
print()

# ============= 测试 2: 可见性隔离 =============
print("[测试 2] 可见性隔离测试...")

# 公开记忆
manager.share_memory("场控", "公开内容", "public")

# 团队记忆
manager.share_memory("运营", "团队内容", "team")

# 私有记忆
manager.share_memory("客服", "私有内容", "private")

# 场控应该看到：公开 + 团队 (同属内容团队)
changkong_memories = get_shared_memories("场控")
public_count = sum(1 for m in changkong_memories if m['visibility'] == 'public')
team_count = sum(1 for m in changkong_memories if m['visibility'] == 'team')

assert public_count > 0, "场控应看到公开记忆"
assert team_count > 0, "场控应看到内容团队记忆"

# 客服应该看到：公开 + 私有
kefu_memories = get_shared_memories("客服")
kefu_private = sum(1 for m in kefu_memories if m['visibility'] == 'private' and m['bot_name'] == '客服')

assert kefu_private > 0, "客服应看到自己的私有记忆"

print(f"✅ 可见性隔离正常 (场控：{len(changkong_memories)}条，客服：{len(kefu_memories)}条)")
print()

# ============= 测试 3: 团队分组 =============
print("[测试 3] 团队分组测试...")

# 验证团队配置
assert manager.get_bot_team("场控") == "内容团队"
assert manager.get_bot_team("运营") == "内容团队"
assert manager.get_bot_team("编导") == "内容团队"
assert manager.get_bot_team("剪辑") == "制作团队"
assert manager.get_bot_team("美工") == "制作团队"
assert manager.get_bot_team("客服") == "商务团队"
assert manager.get_bot_team("渠道") == "商务团队"

print("✅ 团队分组正确")
print()

# ============= 测试 4: 访问授权 =============
print("[测试 4] 访问授权测试...")

# 客服创建私有记忆
private_id = manager.share_memory("客服", "重要客户资料", "private")

# 重新初始化管理器（刷新缓存）
manager2 = MemoryShareManager(TEST_DB)

# 初始场控看不到
changkong_before = manager2.get_shared_memories("场控")
assert not any(m['id'] == private_id for m in changkong_before)

# 客服授权场控
success = manager2.grant_access("客服", "场控", private_id)
assert success == True

# 场控现在能看到
changkong_after = manager2.get_shared_memories("场控")
assert any(m['id'] == private_id for m in changkong_after), f"授权后场控应能看到私有记忆，实际：{changkong_after}"

# 撤销授权
success = manager2.revoke_access("客服", "场控", private_id)
assert success == True

# 场控又看不到了
changkong_final = manager2.get_shared_memories("场控")
assert not any(m['id'] == private_id for m in changkong_final)

print("✅ 访问授权和撤销正常")
print()

# ============= 测试 5: 记忆搜索 =============
print("[测试 5] 记忆搜索测试...")

# 添加测试数据
manager.share_memory("场控", "直播流程策划方案", "public", "直播，策划，流程")
manager.share_memory("运营", "流量获取方法", "public", "流量，运营，推广")
manager.share_memory("剪辑", "视频剪辑技巧", "public", "剪辑，特效，后期")

# 搜索 (测试简单关键词)
results = search_memories("场控", "直播")
assert len(results) > 0, f"搜索'直播'应有结果，实际：{results}"

results = search_memories("场控", "内容")  # 搜索通用词
print(f"✅ 记忆搜索正常 (搜索结果:{len(results)}条)")
print()

# ============= 测试 6: 统计信息 =============
print("[测试 6] 统计信息测试...")

stats = manager.get_stats()
assert stats["total"] > 0, "总记忆数应大于 0"
assert stats["bot_count"] > 0, "Bot 数量应大于 0"

personal_stats = manager.get_stats("场控")
assert "total" in personal_stats

print(f"✅ 统计信息正确 (总记忆：{stats['total']}, Bot: {stats['bot_count']})")
print()

# ============= 测试 7: 删除记忆 =============
print("[测试 7] 删除记忆测试...")

test_id = manager.share_memory("场控", "临时测试", "private")
assert test_id > 0

success = manager.delete_memory("场控", test_id)
assert success == True

# 验证已删除
memories = manager.get_shared_memories("场控")
assert not any(m['id'] == test_id for m in memories)

# 删除他人记忆应失败
test_id2 = manager.share_memory("运营", "运营测试", "public")
success = manager.delete_memory("场控", test_id2)  # 场控尝试删除运营的记忆
assert success == False

print("✅ 删除记忆正常")
print()

# ============= 测试 8: 并发共享 =============
print("[测试 8] 并发共享测试...")

import concurrent.futures

def share_task(bot_id):
    for i in range(5):
        manager.share_memory(f"Bot{bot_id}", f"并发内容{bot_id}_{i}", "public", f"并发，bot{bot_id}")
    return True

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(share_task, i) for i in range(5)]
    results = [f.result() for f in futures]

assert all(results), "并发共享应全部成功"

stats = manager.get_stats()
print(f"✅ 并发共享正常 (5 线程 x5 次，总记忆：{stats['total']})")
print()

# ============= 测试 9: 性能测试 =============
print("[测试 9] 性能测试...")

# 大量数据
print("   导入 1000 条记忆...")
for i in range(1000):
    manager.share_memory("测试 Bot", f"性能测试内容{i}" * 10, "public", f"性能，测试，{i % 10}")

# 搜索性能
print("   测试搜索性能...")
start = time.time()
results = search_memories("场控", "性能")
elapsed = time.time() - start

assert elapsed < 0.1, f"搜索太慢：{elapsed}s"
print(f"✅ 搜索性能：{elapsed * 1000:.2f}ms ({len(results)}结果)")

# 获取性能
print("   测试获取性能...")
start = time.time()
results = manager.get_shared_memories("场控")  # 不使用 limit 参数
elapsed = time.time() - start

assert elapsed < 0.1, f"获取太慢：{elapsed}s"
print(f"✅ 获取性能：{elapsed * 1000:.2f}ms ({len(results)}结果)")
print()

# ============= 测试 10: 边界条件 =============
print("[测试 10] 边界条件测试...")

# 空标签
manager.share_memory("测试", "内容", "public", "")

# 超长内容
long_content = "x" * 100000
manager.share_memory("测试", long_content, "public")

# 特殊字符
manager.share_memory("测试", "特殊@#$%^&*()", "public", "标签！@#")

print("✅ 边界条件处理正常")
print()

# 清理
TEST_DB.unlink()

print("=" * 60)
print("  测试完成!")
print("=" * 60)
print()
print("测试总结:")
print("- ✅ 基础记忆共享")
print("- ✅ 可见性隔离")
print("- ✅ 团队分组")
print("- ✅ 访问授权")
print("- ✅ 记忆搜索")
print("- ✅ 统计信息")
print("- ✅ 删除记忆")
print("- ✅ 并发共享")
print("- ✅ 性能测试")
print("- ✅ 边界条件")
print()
print("✅ 跨 Bot 记忆共享系统测试全部通过")

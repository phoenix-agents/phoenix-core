#!/usr/bin/env python3
"""
Phoenix Core 快速测试 - 测试 smart_memory 功能
"""

import sys
import time
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("  Phoenix Core smart_memory 测试")
print("=" * 60)
print()

# 测试 1: 导入测试
print("[测试 1] 导入 smart_memory 模块...")
try:
    from smart_memory import smart_save_memory, load_context, MEMORY_FILE, MAX_MEMORY_CHARS
    print("✅ 导入成功")
except Exception as e:
    print(f"❌ 导入失败：{e}")
    sys.exit(1)

print()

# 测试 2: 记忆文件状态
print("[测试 2] 检查记忆文件状态...")
if MEMORY_FILE.exists():
    size = MEMORY_FILE.stat().st_size
    print(f"✅ MEMORY.md 存在：{size:,} 字符 (限制：{MAX_MEMORY_CHARS:,})")
    if size <= MAX_MEMORY_CHARS:
        print("✅ 符合字符限制")
    else:
        print(f"⚠️  超出限制：{size} > {MAX_MEMORY_CHARS}")
else:
    print("⚠️  MEMORY.md 不存在")

print()

# 测试 3: 短内容保存测试
print("[测试 3] 短内容保存测试...")
content = "这是测试短内容，应该直接保存到 MEMORY.md"
result = smart_save_memory(content)
print(f"结果：{result}")
print("✅ 短内容保存完成")

print()

# 测试 4: 长内容保存测试
print("[测试 4] 长内容保存测试 (5000 字符)...")
long_content = "x" * 5000
result = smart_save_memory(long_content, title="测试长文档")
print(f"结果：{result}")
if "projects/" in result:
    print("✅ 长内容正确保存到 projects/目录")
else:
    print("⚠️  长内容未保存到 projects/目录")

print()

# 测试 5: 上下文加载性能测试
print("[测试 5] 上下文加载性能测试...")
start = time.time()
context = load_context()
elapsed = time.time() - start
print(f"加载时间：{elapsed:.3f}s")
if elapsed < 0.1:
    print(f"✅ 性能达标 (< 0.1s)")
else:
    print(f"⚠️  性能不达标 (> 0.1s)")

print()

# 测试 6: 项目文件索引
print("[测试 6] 项目文件索引检查...")
from smart_memory import PROJECTS_DIR
if PROJECTS_DIR.exists():
    projects = list(PROJECTS_DIR.glob("*.md"))
    print(f"✅ 项目目录存在：{len(projects)} 个文件")
    for p in projects[-5:]:
        print(f"   - {p.name} ({p.stat().st_size:,} 字符)")
else:
    print("⚠️  项目目录不存在")

print()
print("=" * 60)
print("  测试完成!")
print("=" * 60)

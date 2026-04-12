"""
Phoenix Core 测试框架
质量优先：每个功能都要测试到最优
"""

import pytest
import time
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# ============= 性能测试 =============

class TestPerformance:
    """性能测试套件"""

    def test_search_response_time(self):
        """搜索响应时间 < 100ms"""
        from smart_memory import load_context

        start = time.time()
        context = load_context()
        elapsed = time.time() - start

        assert elapsed < 0.1, f"搜索太慢：{elapsed:.3f}s > 0.1s"
        print(f"✅ 搜索响应时间：{elapsed:.3f}s")

    def test_memory_load_time(self):
        """记忆加载时间 < 50ms"""
        from smart_memory import load_context

        start = time.time()
        _ = load_context()
        elapsed = time.time() - start

        assert elapsed < 0.05, f"记忆加载太慢：{elapsed:.3f}s > 0.05s"
        print(f"✅ 记忆加载时间：{elapsed:.3f}s")

    def test_nudge_trigger_time(self):
        """Nudge 触发时间 < 10ms"""
        # TODO: 实现 Nudge 后添加测试
        pass


# ============= 功能测试 =============

class TestSmartMemory:
    """智能记忆管理测试"""

    def test_short_content_save(self):
        """测试短内容直接保存"""
        from smart_memory import smart_save_memory

        content = "这是短内容，测试保存功能"
        result = smart_save_memory(content)

        assert "MEMORY.md" in result

    def test_long_content_save(self):
        """测试长内容保存为项目文件"""
        from smart_memory import smart_save_memory

        content = "x" * 5000  # 超出 2200 字符
        result = smart_save_memory(content, title="测试长文档")

        assert "projects/" in result
        assert "摘要已注入" in result

    def test_memory_limit_enforced(self):
        """测试字符限制被执行"""
        from smart_memory import MEMORY_FILE, MAX_MEMORY_CHARS

        if MEMORY_FILE.exists():
            with open(MEMORY_FILE, 'r') as f:
                content = f.read()
            assert len(content) <= MAX_MEMORY_CHARS, \
                f"MEMORY.md 超出限制：{len(content)} > {MAX_MEMORY_CHARS}"

    def test_project_index_generated(self):
        """测试项目索引生成"""
        from smart_memory import load_context

        context = load_context()

        assert "项目文件索引" in context or "projects" in context.lower()


class TestMemoryLimit:
    """字符限制测试"""

    def test_memory_file_limit(self):
        """MEMORY.md ≤ 2200 字符"""
        from smart_memory import MEMORY_FILE, MAX_MEMORY_CHARS

        if MEMORY_FILE.exists():
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
            assert len(content) <= MAX_MEMORY_CHARS, \
                f"MEMORY.md 超限：{len(content)} 字符"

    def test_user_file_limit(self):
        """USER.md ≤ 1375 字符"""
        user_file = Path(__file__).parent.parent / "shared_memory" / "USER.md"

        if user_file.exists():
            with open(user_file, 'r', encoding='utf-8') as f:
                content = f.read()
            assert len(content) <= 1375, \
                f"USER.md 超限：{len(content)} 字符"


# ============= 压力测试 =============

class TestStress:
    """压力测试套件"""

    def test_concurrent_memory_writes(self):
        """并发写入测试"""
        from smart_memory import smart_save_memory
        import concurrent.futures

        def write_content(i):
            content = f"测试内容 {i}" * 100
            return smart_save_memory(content, title=f"压力测试_{i}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(write_content, i) for i in range(10)]
            results = [f.result() for f in futures]

        assert all(r is not None for r in results)

    def test_large_file_handling(self):
        """大文件处理测试"""
        from smart_memory import smart_save_memory

        # 10 万字文档
        content = "测试 " * 50000
        result = smart_save_memory(content, title="10 万字测试文档")

        assert "projects/" in result


# ============= 集成测试 =============

class TestIntegration:
    """集成测试套件"""

    def test_discord_sync_integration(self):
        """Discord 同步集成测试"""
        # TODO: 实现 Discord 同步测试
        pass

    def test_bot_collaboration(self):
        """Bot 协作测试"""
        # TODO: 实现 Bot 协作测试
        pass


# ============= 回归测试 =============

class TestRegression:
    """回归测试套件"""

    def test_memory_not_lost_after_truncation(self):
        """测试截断后记忆不丢失"""
        from smart_memory import smart_save_memory, load_context, PROJECTS_DIR

        # 保存长文档
        long_content = "重要记忆内容 " * 1000
        smart_save_memory(long_content, title="回归测试记忆")

        # 加载上下文
        context = load_context()

        # 验证：要么在 MEMORY.md，要么在 projects/
        assert "重要记忆内容" in context or \
               list(PROJECTS_DIR.glob("*回归测试*"))


# ============= 测试运行 =============

if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",                    # 详细输出
        "--tb=short",            # 简洁 traceback
        "--capture=no",          # 显示 print 输出
        "--benchmark-only",      # 仅运行性能测试
    ])

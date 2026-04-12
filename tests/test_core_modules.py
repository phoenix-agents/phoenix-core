#!/usr/bin/env python3
"""
Phoenix Core 核心模块测试套件
测试覆盖率目标：80%+
"""

import pytest
import time
import tempfile
import json
from pathlib import Path


# ============= Memory Store 测试 =============

class TestMemoryStore:
    """MemoryStore 核心功能测试"""

    def test_memory_store_init(self):
        """测试 MemoryStore 初始化"""
        from memory_store import MemoryStore

        store = MemoryStore()
        assert store is not None
        assert store.memory_char_limit == 5000

    def test_memory_store_add(self):
        """测试添加记忆"""
        from memory_store import MemoryStore

        store = MemoryStore()
        content = "测试记忆内容" * 100
        result = store.add("test_bot", content)

        assert result is not None

    def test_memory_store_read(self):
        """测试读取记忆"""
        from memory_store import MemoryStore

        store = MemoryStore()
        result = store.read()

        assert result is not None
        assert isinstance(result, dict)


# ============= Session Store 测试 =============

class TestSessionStore:
    """SessionStore 测试"""

    def test_session_store_init(self):
        """测试 SessionStore 初始化"""
        from session_store import SessionStore

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = SessionStore(db_path=str(db_path))
            assert store is not None

    def test_session_save(self):
        """测试保存会话"""
        from session_store import SessionStore

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = SessionStore(db_path=str(db_path))

            result = store.save_session(
                session_id="test_123",
                user_msg="你好",
                assistant_msg="你好！有什么可以帮助你的？"
            )

            assert result is not None


# ============= Skill Store 测试 =============

class TestSkillStore:
    """SkillStore 测试"""

    def test_skill_store_init(self):
        """测试 SkillStore 初始化"""
        from skill_store import SkillStore

        store = SkillStore()
        assert store is not None
        assert store.skill_char_limit == 10000

    def test_skill_add(self):
        """测试添加技能"""
        from skill_store import SkillStore

        store = SkillStore()

        skill_content = """[SKILL] 测试技能
Description: 这是一个测试技能
Steps: 1. 第一步 2. 第二步
"""
        result = store.add("test_skill", skill_content)

        assert result is not None

    def test_skill_read(self):
        """测试读取技能"""
        from skill_store import SkillStore

        store = SkillStore()
        result = store.read()
        assert isinstance(result, dict)


# ============= Bot Memory 测试 =============

class TestBotMemory:
    """Bot 记忆系统测试"""

    def test_bot_memory_adapter(self):
        """测试 BotMemoryAdapter"""
        from bot_memory_adapter import BotMemoryStore

        adapter = BotMemoryStore(bot_name="测试 Bot")
        assert adapter is not None

    def test_bot_memory_add(self):
        """测试 Bot 记忆添加"""
        from bot_memory_adapter import BotMemoryStore

        adapter = BotMemoryStore(bot_name="测试 Bot")
        content = "测试内容"
        result = adapter.add_memory(content)

        assert result is not None


# ============= Skill Extractor 测试 =============

class TestSkillExtractor:
    """SkillExtractor 测试"""

    def test_skill_extractor_init(self):
        """测试 SkillExtractor 初始化"""
        from skill_extractor import SkillExtractor

        extractor = SkillExtractor()
        assert extractor is not None
        assert extractor._extraction_count == 0

    def test_skill_name_generation(self):
        """测试技能名称生成"""
        from skill_extractor import SkillExtractor

        extractor = SkillExtractor()
        name = extractor._generate_skill_name("memory_config")

        assert "Memory" in name or "Config" in name


# ============= Task Queue 测试 =============

class TestTaskQueue:
    """任务队列测试"""

    def test_task_queue_init(self):
        """测试任务队列初始化"""
        from task_queue import TaskQueue

        queue = TaskQueue()
        assert queue is not None

    def test_add_task(self):
        """测试添加任务"""
        from task_queue import TaskQueue, TaskPriority

        queue = TaskQueue()
        task_id = queue.add_task(
            assigned_to="测试 Bot",
            title="测试任务",
            description="这是一个测试任务",
            priority=TaskPriority.NORMAL
        )
        assert task_id is not None

    def test_get_stats(self):
        """测试获取统计"""
        from task_queue import TaskQueue

        queue = TaskQueue()
        stats = queue.get_stats()

        assert isinstance(stats, dict)
        assert 'total_tasks' in stats


# ============= Phoenix CLI 测试 =============

class TestPhoenixCLI:
    """Phoenix CLI 测试"""

    def test_cli_version(self, capsys):
        """测试版本命令"""
        import subprocess

        result = subprocess.run(
            ["python3", "phoenix.py", "version"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0
        assert "Phoenix Core CLI" in result.stdout


# ============= 性能基准测试 =============

class TestBenchmarks:
    """性能基准测试"""

    def test_memory_store_performance(self):
        """MemoryStore 性能测试"""
        from memory_store import MemoryStore
        import time

        store = MemoryStore()

        # 批量写入测试
        start = time.time()
        for i in range(50):
            store.add(f"bot_{i}", f"内容 {i}" * 100)
        elapsed = time.time() - start

        # 50 次写入应在 2 秒内完成
        assert elapsed < 2.0, f"批量写入太慢：{elapsed:.2f}s"

    def test_skill_store_performance(self):
        """技能存储性能测试"""
        from skill_store import SkillStore
        import time

        store = SkillStore()

        # 添加多个技能
        for i in range(20):
            store.add(f"skill_{i}", f"[SKILL] 技能{i}")

        # 读取测试
        start = time.time()
        skills = store.read()
        elapsed = time.time() - start

        assert elapsed < 0.5, f"技能读取太慢：{elapsed:.2f}s"


# ============= 集成测试 =============

class TestIntegration:
    """集成测试"""

    def test_full_memory_flow(self):
        """完整记忆流程测试"""
        from memory_store import MemoryStore

        store = MemoryStore()

        # 1. 添加记忆
        add_result = store.add("test_bot", "测试记忆内容")
        assert add_result is not None

        # 2. 读取记忆
        result = store.read()
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

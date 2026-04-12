"""
Phoenix Core Memory System

分层持久化记忆系统，AI 驱动的直播运营团队系统：

1. 第一层：SQLite 会话存储 (SessionStore)
   - FTS5 全文搜索
   - 跨会话检索

2. 第二层：文件化 Curation 记忆 (MemoryStore)
   - MEMORY.md: 代理笔记和观察
   - USER.md: 用户偏好和期望
   - 冻结快照注入 system prompt

3. 第三层：学习循环 (LearningLoop)
   - 迭代计数器跟踪工具调用
   - 阈值触发后台反思
   - 自动创建/更新技能

Usage:
    from phoenix_core import MemoryManager

    manager = MemoryManager()
    manager.load(session_id="abc123")

    # Get memory context for system prompt
    context = manager.build_memory_context()

    # Sync after turn
    manager.sync_turn(user_msg, assistant_msg, tool_iterations=3)

    # Handle tool calls
    result = manager.handle_tool_call("memory", {"action": "add", "target": "memory", "content": "..."})
"""

from memory_store import MemoryStore, MEMORY_TOOL_SCHEMA, memory_tool
from session_store import SessionStore, SESSION_STORE_SCHEMA, session_store_tool
from skill_store import SkillStore, SKILL_TOOL_SCHEMA, skill_tool
from memory_manager import MemoryManager, LearningLoopMixin
from background_review import BackgroundReviewAgent
from skill_activation import SkillActivator
from bot_memory_adapter import BotMemoryStore, BotMemoryManager, get_bot_memory, add_bot_memory
from bot_security_guard import BotGuard, BotSecurityManager, get_bot_guard, check_bot_permission
from bot_learning_loop import BotLearningLoop, BotLearningManager, get_bot_learning_loop, bot_sync_turn
from task_evaluation import TaskEvaluator, TaskOutcome, TaskEvaluation
from skill_extractor import SkillExtractor
from skill_executor import SkillExecutor
from skill_risk_assessor import RiskAssessor
from skill_optimizer import SkillOptimizer
from auto_optimizer import AutoOptimizer
from skills_guard import SkillsGuard, get_guard, check_skill_execution
from multi_agent_orchestrator import (
    AgentOrchestrator, AgentRole, TaskPriority,
    get_orchestrator, assign_task, get_status
)

__all__ = [
    'MemoryStore',
    'SessionStore',
    'SkillStore',
    'MemoryManager',
    'LearningLoopMixin',
    'BackgroundReviewAgent',
    'SkillActivator',
    'BotMemoryStore',
    'BotMemoryManager',
    'BotGuard',
    'BotSecurityManager',
    'BotLearningLoop',
    'BotLearningManager',
    'get_bot_memory',
    'add_bot_memory',
    'get_bot_guard',
    'check_bot_permission',
    'get_bot_learning_loop',
    'bot_sync_turn',
    'TaskEvaluator',
    'TaskOutcome',
    'TaskEvaluation',
    'SkillExtractor',
    'SkillExecutor',
    'RiskAssessor',
    'SkillOptimizer',
    'AutoOptimizer',
    'SkillsGuard',
    'AgentOrchestrator',
    'AgentRole',
    'TaskPriority',
    'MEMORY_TOOL_SCHEMA',
    'SESSION_STORE_SCHEMA',
    'SKILL_TOOL_SCHEMA',
    'memory_tool',
    'session_store_tool',
    'skill_tool',
    'get_guard',
    'check_skill_execution',
    'get_orchestrator',
    'assign_task',
    'get_status',
]

#!/usr/bin/env python3
"""
Phoenix Core - 主大脑 (Core Brain)

这是 Phoenix Core 系统的核心控制模块，负责:
1. 统一入口 - 所有请求的调度中心
2. 资源管理 - 内存、上下文、任务状态
3. 决策引擎 - 意图识别 → 任务拆解 → 执行编排
4. MCP 工具调用 - Layer 3 手脚
5. 记忆管理 - Layer 2 RAG
6. LLM 调用 - Layer 1 大脑

架构:
┌─────────────────────────────────────────────────────────┐
│                    Phoenix Core                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │              CoreBrain (主大脑)                      ││
│  │  - 统一入口                                          ││
│  │  - 资源管理                                          ││
│  │  - 决策引擎                                          ││
│  └──────────┬──────────────────────────────────────────┘│
│             │                                            │
│    ┌────────┼───────────┬────────────┐                  │
│    ▼        ▼           ▼            ▼                  │
│  LLM      RAG         MCP         Agent                 │
│  大脑     记忆        手脚         编排                  │
│    │        │           │            │                  │
│    ▼        ▼           ▼            ▼                  │
│  intent   memory      tools      tasks                 │
│  识别     存储        调用        追踪                  │
└─────────────────────────────────────────────────────────┘

Usage:
    from phoenix_core import CoreBrain

    brain = CoreBrain()
    response = await brain.process("帮我查订单 #12345")
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from datetime import datetime

# Phoenix Core 模块
from phoenix_core.intent_recognition import IntentRecognizer, Intent
from phoenix_core.memory_db import MemoryDatabase, get_memory_db
from phoenix_core.task_tracker import TaskTracker, Task, TaskStatus
from phoenix_core.result_aggregator import ResultAggregator
from phoenix_core.link_tracing import LinkTracer, get_tracer, trace_operation
from phoenix_core.progress_reporter import ProgressReporter, get_progress_reporter
from phoenix_core.audit_logger import AuditLogger, get_audit_logger
from phoenix_core.skill_registry import get_skill_registry
from phoenix_core.skill_learner import get_learner
from phoenix_core.team_delegator import get_team_delegator, TeamDelegationPolicy

logger = logging.getLogger(__name__)


@dataclass
class BrainConfig:
    """主大脑配置"""
    # 工作区路径
    workspace: str = "workspaces/default"

    # LLM 配置
    llm_model: str = "qwen-3.6-plus"
    llm_max_tokens: int = 4000
    llm_temperature: float = 0.7

    # 记忆配置
    memory_db_path: Optional[str] = None  # None 则使用默认路径
    memory_ttl_minutes: int = 30

    # 任务配置
    max_concurrent_tasks: int = 10
    task_timeout_seconds: int = 300

    # MCP 配置
    mcp_enabled: bool = True
    mcp_servers_config: Optional[str] = None

    # 调试模式
    debug: bool = False


@dataclass
class BrainResponse:
    """主大脑响应"""
    success: bool
    message: str
    request_id: str
    task_id: Optional[str] = None
    context: Dict[str, Any] = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.context is None:
            self.context = {}


class CoreBrain:
    """
    Phoenix Core 主大脑

    核心职责:
    1. 接收用户输入
    2. 意图识别 (Layer 1)
    3. 记忆检索 (Layer 2)
    4. 任务拆解 (Layer 4)
    5. MCP 工具调用 (Layer 3)
    6. 返回响应
    """

    def __init__(self, config: Optional[BrainConfig] = None):
        self.config = config or BrainConfig()

        # 初始化核心模块
        logger.info("初始化主大脑...")

        # Layer 1: LLM 意图识别
        self.intent_recognizer = IntentRecognizer()
        logger.info("  ✓ 意图识别模块已加载")

        # Layer 2: RAG 记忆存储
        self.memory_db = MemoryDatabase()
        logger.info("  ✓ 记忆数据库已加载")

        # Layer 4: 任务追踪
        self.task_tracker = TaskTracker()
        logger.info("  ✓ 任务追踪模块已加载")

        # Layer 3: MCP 工具调用 (可选)
        self.mcp_client = None
        if self.config.mcp_enabled:
            try:
                from mcp_client import MCPClient
                self.mcp_client = MCPClient(workspace=self.config.workspace)
                logger.info("  ✓ MCP 客户端已加载")
            except ImportError:
                logger.warning("  ⚠ MCP SDK 不可用，工具调用功能将被禁用")

        # 结果聚合
        self.result_aggregator = ResultAggregator()
        logger.info("  ✓ 结果聚合模块已加载")

        # P1 功能：链路追踪
        self.tracer = get_tracer()
        logger.info("  ✓ 链路追踪已加载")

        # P1 功能：进度汇报
        self.progress_reporter = get_progress_reporter()
        logger.info("  ✓ 进度汇报已加载")

        # P1 功能：审计日志
        self.audit_logger = get_audit_logger()
        logger.info("  ✓ 审计日志已加载")

        # 技能注册表（用于技能匹配）
        self.skill_registry = get_skill_registry()
        logger.info("  ✓ 技能注册表已加载")

        # 技能学习者（自动学习）
        self.skill_learner = get_learner()
        logger.info("  ✓ 技能学习者已加载")

        # Phase 2: Team Delegation器
        self.team_delegator = get_team_delegator(gateway=None, config_loader=None)
        logger.info(f"  ✓ Team Delegation器已加载 ({len(self.team_delegator.teams)} 个团队)")

        # 上下文管理 (内存缓存)
        self.contexts: Dict[str, Dict] = {}

        # 回调函数
        self._send_callback: Optional[Callable] = None
        self._receive_callback: Optional[Callable] = None

        logger.info("主大脑初始化完成")

    # ============ 核心方法 ============

    async def process(self, user_input: str, user_id: str = "default") -> BrainResponse:
        """
        处理用户输入 - 主入口 (集成链路追踪、进度汇报、审计日志)

        Args:
            user_input: 用户输入 (自然语言)
            user_id: 用户 ID

        Returns:
            BrainResponse: 响应对象
        """
        logger.info(f"收到用户输入：{user_input[:50]}...")

        # Step 1: 生成请求 ID
        request_id = self._generate_request_id(user_id)

        # Step 2: 开始链路追踪
        trace_id = self.tracer.start_trace(user_id=user_id, request_id=request_id)

        # Step 3: 创建进度追踪 (如果有子任务)
        progress = None

        # Step 4: 记录审计日志
        self.audit_logger.log_message(
            content=user_input,
            user_id=user_id,
            request_id=request_id,
            message_type="ASK"
        )

        try:
            # Step 5: 检索上下文
            context = self._get_context(user_id)

            # Step 6: 意图识别 (Layer 1)
            with self.tracer.trace_operation(trace_id, "intent_recognition") as span:
                intent = self.intent_recognizer.recognize(user_input)
                span.add_log("intent_detected", intent_type=intent.intent_type)
                logger.info(f"识别意图：{intent.intent_type} -> {intent.target_bot}")

            # Step 7: 记忆检索 (Layer 2)
            with self.tracer.trace_operation(trace_id, "memory_retrieval") as span:
                relevant_memory = await self._retrieve_memory(user_id, user_input)
                span.add_log("memory_found", count=len(relevant_memory))
                if relevant_memory:
                    logger.info(f"检索到相关记忆：{len(relevant_memory)} 条")

            # Step 8: 任务拆解 (Layer 4)
            with self.tracer.trace_operation(trace_id, "task_decomposition") as span:
                subtasks = await self._decompose_task(intent, user_input, context)
                span.add_log("subtasks_created", count=len(subtasks))
                logger.info(f"拆解为 {len(subtasks)} 个子任务")

            # Step 9: 初始化进度追踪
            if subtasks:
                progress = self.progress_reporter.create_progress(
                    task_id=request_id,
                    user_id=user_id,
                    description=user_input[:100],
                    subtasks=[f"sub-{i}" for i in range(len(subtasks))]
                )

            # Step 10: 执行子任务
            if len(subtasks) == 0:
                # 无需执行子任务 (闲聊)
                with self.tracer.trace_operation(trace_id, "chat_response") as span:
                    response = await self._handle_chat(user_input, intent)
                    span.add_log("chat_response_sent")
                brain_response = BrainResponse(
                    success=True,
                    message=response,
                    request_id=request_id
                )
                # 自动学习：闲聊不学习
                return brain_response

            elif len(subtasks) == 1:
                # 单个子任务
                with self.tracer.trace_operation(trace_id, "single_subtask") as span:
                    result = await self._execute_subtask(subtasks[0], request_id)
                    span.add_log("subtask_completed", success=result.success)

                # 更新进度
                if progress:
                    self.progress_reporter.mark_subtask_done(request_id, "sub-0")
                    self.progress_reporter.update_progress(
                        task_id=request_id,
                        status="completed",
                        description="任务完成"
                    )

                brain_response = BrainResponse(
                    success=result.success,
                    message=result.message,
                    request_id=request_id,
                    task_id=result.task_id,
                    context={"subtask_result": result}
                )

                # ========== 自动学习（新增） ==========
                # 任务成功后自动学习
                if result.success:
                    asyncio.create_task(
                        self.skill_learner.analyze_task_result(
                            task_id=request_id,
                            user_input=user_input,
                            bot_response=result.message,
                            bot_name="brain",
                            success=True
                        )
                    )
                # =======================================

                return brain_response

            else:
                # 多个子任务 (并行执行)
                with self.tracer.trace_operation(trace_id, "parallel_subtasks") as span:
                    results = await self._execute_parallel_subtasks(subtasks, request_id)
                    aggregated = self.result_aggregator.aggregate(results)
                    span.add_log("all_subtasks_completed", count=len(results))

                # 更新进度为完成
                if progress:
                    self.progress_reporter.update_progress(
                        task_id=request_id,
                        status="completed",
                        description="任务完成"
                    )

                brain_response = BrainResponse(
                    success=True,
                    message=aggregated,
                    request_id=request_id,
                    task_id=request_id,
                    context={"subtask_results": results}
                )

                # ========== 自动学习（新增） ==========
                # 任务成功后自动学习
                if brain_response.success:
                    asyncio.create_task(
                        self.skill_learner.analyze_task_result(
                            task_id=request_id,
                            user_input=user_input,
                            bot_response=aggregated,
                            bot_name="brain",
                            success=True
                        )
                    )
                # =======================================

                return brain_response

        finally:
            # 记录审计日志
            self.audit_logger.log_operation(
                operation="process_complete",
                user_id=user_id,
                request_id=request_id,
                details=f"input={user_input[:50]}..."
            )

    async def process_with_callback(
        self,
        user_input: str,
        user_id: str = "default",
        send_callback: Optional[Callable] = None,
        receive_callback: Optional[Callable] = None
    ) -> BrainResponse:
        """
        处理用户输入 (带回调 - 用于 Bot 集成)

        Args:
            user_input: 用户输入
            user_id: 用户 ID
            send_callback: 发送协议消息的回调 (async, 接收 protocol_str)
            receive_callback: 接收协议消息的回调 (async, 接收 protocol_str)

        Returns:
            BrainResponse: 响应对象
        """
        self._send_callback = send_callback
        self._receive_callback = receive_callback
        return await self.process(user_input, user_id)

    # ============ 内部方法 ============

    def _generate_request_id(self, user_id: str) -> str:
        """生成请求 ID"""
        user_prefix = user_id[-4:] if len(user_id) >= 4 else user_id
        date_str = datetime.now().strftime("%Y%m%d")

        # 简单计数 (实际应该用持久化计数器)
        count = len(self.contexts.get(user_id, {}).get("requests", [])) + 1

        request_id = f"{user_prefix}-{date_str}-{count:03d}"

        # 记录请求
        if user_id not in self.contexts:
            self.contexts[user_id] = {"requests": []}
        self.contexts[user_id]["requests"].append(request_id)

        return request_id

    def _get_context(self, user_id: str) -> Dict:
        """获取用户上下文"""
        return self.contexts.get(user_id, {})

    async def _retrieve_memory(self, user_id: str, query: str, limit: int = 5) -> List[Dict]:
        """检索记忆 (Layer 2 RAG)"""
        try:
            # 从 SQLite 检索最近的记忆
            conn = self.memory_db._get_connection()
            cursor = conn.execute(
                """SELECT bot_id, role, content, timestamp
                   FROM memory
                   WHERE bot_id LIKE ? OR role = 'user'
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (f"%{user_id}%", limit)
            )
            rows = cursor.fetchall()
            return [
                {"bot_id": row[0], "role": row[1], "content": row[2], "timestamp": row[3]}
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"记忆检索失败：{e}")
            return []

    async def _decompose_task(self, intent: Intent, user_input: str, context: Dict) -> List[Dict]:
        """
        任务拆解 (Layer 4)

        Returns:
            [{"type": "mcp", "tool": "xxx", "args": {...}},
             {"type": "bot", "bot_id": "xxx", "message": "..."}]
        """
        subtasks = []

        # 简单版本：根据意图类型决定
        if intent.intent_type == "chat":
            # 闲聊不需要子任务
            return []

        elif intent.intent_type == "inquiry":
            # 查询类任务 - 可能调用 MCP 工具
            if self.mcp_client and self._is_mcp_query(intent):
                subtasks.append({
                    "type": "mcp",
                    "tool": "query_data",
                    "args": {"query": user_input}
                })

        elif intent.intent_type == "execution":
            # 执行类任务 - 使用技能匹配找到最合适的 Bot
            subtasks = await self._plan_execution_with_skill_match(intent, user_input)

        return subtasks

    def _is_mcp_query(self, intent: Intent) -> bool:
        """判断是否是 MCP 查询类任务"""
        keywords = ["查询", "查", "看看", "检查", "diagnose", "check"]
        return any(kw in intent.content for kw in keywords)

    async def _plan_execution_with_skill_match(self, intent: Intent, user_input: str) -> List[Dict]:
        """
        使用技能匹配规划执行步骤（新增）

        流程:
        1. 调用 SkillRegistry 匹配最合适的 Bot
        2. 如果没有匹配，使用意图识别的 target_bot
        3. 创建子任务
        """
        # Step 1: 使用技能注册表匹配最合适的 Bot
        matched_bot = self.skill_registry.find_bot_for_task(user_input)

        if matched_bot:
            logger.info(f"技能匹配结果：'{user_input[:30]}...' → {matched_bot}")
            bot_id = matched_bot
        else:
            # 没有技能匹配，回退到意图识别的目标 Bot
            bot_id = intent.target_bot
            logger.info(f"技能未匹配，使用意图识别 Bot: {bot_id}")

        # Step 2: 创建子任务
        return [
            {
                "type": "bot",
                "bot_id": bot_id,
                "message": user_input
            }
        ]

    async def _plan_execution(self, intent: Intent, user_input: str) -> List[Dict]:
        """规划执行步骤（旧方法，保留作为后备）"""
        # 简单版本：直接返回一个子任务
        # 复杂版本：可以用 LLM 规划多步执行
        return [
            {
                "type": "bot",
                "bot_id": intent.target_bot,
                "message": user_input
            }
        ]

    async def _handle_chat(self, user_input: str, intent: Intent) -> str:
        """处理闲聊"""
        # TODO: 集成 LLM 回复
        return "我在~ 有什么可以帮您的吗？"

    async def _execute_subtask(self, subtask: Dict, request_id: str) -> BrainResponse:
        """执行单个子任务"""
        if subtask["type"] == "mcp":
            # MCP 工具调用 (Layer 3)
            return await self._execute_mcp_tool(subtask, request_id)
        elif subtask["type"] == "bot":
            # Bot 调用
            return await self._execute_bot_task(subtask, request_id)
        else:
            return BrainResponse(
                success=False,
                message=f"未知子任务类型：{subtask['type']}",
                request_id=request_id
            )

    async def _execute_mcp_tool(self, subtask: Dict, request_id: str) -> BrainResponse:
        """执行 MCP 工具调用"""
        if not self.mcp_client:
            return BrainResponse(
                success=False,
                message="MCP 客户端不可用",
                request_id=request_id
            )

        try:
            # 连接 MCP Server
            await self.mcp_client.connect_server("filesystem")

            # 调用工具
            tool_name = subtask.get("tool", "read_file")
            args = subtask.get("args", {})

            result = await self.mcp_client.call_tool("filesystem", tool_name, args)

            return BrainResponse(
                success=True,
                message=str(result),
                request_id=request_id,
                task_id=request_id
            )
        except Exception as e:
            logger.error(f"MCP 工具调用失败：{e}")
            return BrainResponse(
                success=False,
                message=f"MCP 调用失败：{e}",
                request_id=request_id
            )

    async def _execute_bot_task(self, subtask: Dict, request_id: str) -> BrainResponse:
        """执行 Bot 任务"""
        bot_id = subtask.get("bot_id", "")
        message = subtask.get("message", "")

        # 如果有发送回调，发送协议消息
        if self._send_callback:
            from phoenix_core.protocol_v2 import create_ask
            protocol_msg = create_ask(
                target_bot=bot_id,
                request_id=request_id,
                sub_task_id="main",
                sender="brain",
                content=message
            )
            await self._send_callback(bot_id, protocol_msg)

            # 等待回复 (简化版本，实际应该用 Future 等待)
            await asyncio.sleep(1)

        return BrainResponse(
            success=True,
            message=f"任务已派发给 {bot_id}",
            request_id=request_id,
            task_id=request_id
        )

    async def _execute_parallel_subtasks(
        self,
        subtasks: List[Dict],
        request_id: str
    ) -> Dict[str, Any]:
        """并行执行多个子任务"""
        tasks = []
        for i, subtask in enumerate(subtasks):
            sub_task_id = f"sub-{i}"
            tasks.append(self._execute_subtask_with_id(subtask, request_id, sub_task_id))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            f"sub-{i}": str(r) if not isinstance(r, Exception) else f"错误：{r}"
            for i, r in enumerate(results)
        }

    async def _execute_subtask_with_id(
        self,
        subtask: Dict,
        request_id: str,
        sub_task_id: str
    ) -> Any:
        """执行带子任务 ID 的子任务"""
        result = await self._execute_subtask(subtask, request_id)
        return {
            "sub_task_id": sub_task_id,
            "success": result.success,
            "message": result.message
        }

    # ============ 资源管理 ============

    def cleanup_context(self, user_id: str):
        """清理用户上下文"""
        if user_id in self.contexts:
            del self.contexts[user_id]
        logger.info(f"清理用户上下文：{user_id}")

    def cleanup_all(self):
        """清理所有资源"""
        self.contexts.clear()
        self.task_tracker.cleanup_completed()
        logger.info("清理所有资源完成")

    async def shutdown(self):
        """关闭主大脑 (包括链路追踪、进度汇报、审计日志)"""
        logger.info("关闭主大脑...")
        self.cleanup_all()
        if self.mcp_client:
            await self.mcp_client.disconnect_server("filesystem")
        if self.tracer:
            self.tracer.close()
        if self.progress_reporter:
            self.progress_reporter.close()
        if self.audit_logger:
            self.audit_logger.close()
        logger.info("主大脑已关闭")


# ============ 便捷函数 ============

_global_brain: Optional[CoreBrain] = None


def get_brain(config: Optional[BrainConfig] = None) -> CoreBrain:
    """获取全局主大脑实例"""
    global _global_brain
    if _global_brain is None:
        _global_brain = CoreBrain(config)
    return _global_brain


async def process_input(user_input: str, user_id: str = "default") -> BrainResponse:
    """便捷函数：处理用户输入"""
    brain = get_brain()
    return await brain.process(user_input, user_id)


# ============ 跨 Bot 协作方法 (新增) ============

async def process_collaboration_request(
    self,
    user_query: str,
    user_id: str = "default"
) -> BrainResponse:
    """
    处理需要多 Bot 协作的请求

    流程 (两轮讨论模式):
    1. LLM 拆解任务 → 识别需要哪些 Bot 参与
    2. 创建任务 ID 和子任务
    3. 通过 TaskDispatcher 分发给各 Bot (第一轮)
    4. 汇总第一轮结果
    5. 广播给各 Bot，征求意见 (第二轮)
    6. 汇总最终结果

    Args:
        user_query: 用户请求 (如"组织大家讨论下次直播方案")
        user_id: 用户 ID

    Returns:
        BrainResponse: 汇总后的响应
    """
    from phoenix_core.task_dispatcher import get_dispatcher, SubTask
    from datetime import timedelta

    # Step 1: 生成任务 ID
    task_id = f"TASK-{user_id[-4:]}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    request_id = self._generate_request_id(user_id)

    logger.info(f"收到协作请求：{user_query[:50]}... task_id={task_id}")

    # Step 2: 记录审计日志
    self.audit_logger.log_operation(
        operation="collaboration_request",
        user_id=user_id,
        request_id=request_id,
        details=user_query[:200],
        metadata={"task_id": task_id}
    )

    # Step 3: LLM 拆解任务 (识别需要哪些 Bot 参与)
    subtask_specs = await self._llm_decompose_collaboration(user_query)

    # Step 4: 创建子任务对象
    subtasks = []
    for spec in subtask_specs:
        deadline = datetime.now() + timedelta(minutes=spec.get("timeout", 30))
        subtasks.append(SubTask(
            bot_id=spec["bot_id"],
            prompt=spec["prompt"],
            deadline=deadline,
            priority=spec.get("priority", 5),
            timeout_seconds=spec.get("timeout", 30) * 60
        ))

    if not subtasks:
        return BrainResponse(
            success=False,
            message="无法拆解任务，请重试或联系管理员",
            request_id=request_id,
            task_id=task_id
        )

    logger.info(f"拆解为 {len(subtasks)} 个子任务：{[st.bot_id for st in subtasks]}")

    # Step 5: 通过 TaskDispatcher 分发 (第一轮)
    dispatcher = get_dispatcher(self._gateway if hasattr(self, '_gateway') else None)

    # 设置 gateway 引用 (用于发送消息给 Bot)
    if hasattr(self, '_gateway'):
        dispatcher.gateway = self._gateway

    first_round_results = await dispatcher.dispatch(
        task_id=task_id,
        user_id=user_id,
        query=user_query,
        subtasks=subtasks
    )

    # Step 6: 汇总第一轮结果
    first_summary = await self._llm_summarize_collaboration(user_query, first_round_results)

    # ============ 第二轮：征求意见 ============
    # 构建广播 prompt，包含各 Bot 的第一轮观点
    second_round_prompts = []
    for bot_id, response in first_round_results.items():
        if not bot_id.startswith("error_"):
            second_round_prompts.append(f"【{bot_id}】{response[:200]}...")

    second_summary = "\n\n".join(second_round_prompts)

    # 向每个 Bot 征求意见
    second_subtasks = []
    for bot_id in [st.bot_id for st in subtasks]:
        prompt = f"""【协作讨论 - 第二轮征求意见】

原始问题：{user_query}

=== 其他 Bot 的观点 ===
{second_summary}

=== 你的任务 ===
请阅读以上其他 Bot 的观点，然后：
1. 你的方案与他们有什么互补或不同？
2. 你有什么需要强调或补充的重点？
3. 你认为执行中最大的风险是什么？

请简洁回复（200 字内）。"""
        second_subtasks.append(SubTask(
            bot_id=bot_id,
            prompt=prompt,
            deadline=datetime.now() + timedelta(minutes=30),
            priority=5,
            timeout_seconds=30 * 60
        ))

    # 第二轮分发
    second_task_id = f"{task_id}-R2"
    second_round_results = await dispatcher.dispatch(
        task_id=second_task_id,
        user_id=user_id,
        query=f"{user_query} (第二轮征求意见)",
        subtasks=second_subtasks
    )

    # Step 7: LLM 汇总最终结果（包含两轮）
    final_summary = await self._llm_summarize_collaboration_with_rounds(
        user_query, first_round_results, second_round_results
    )

    # Step 8: 记录审计日志
    self.audit_logger.log_operation(
        operation="collaboration_complete",
        user_id=user_id,
        request_id=request_id,
        details=f"第一轮收到 {len(first_round_results)} 个 Bot 回复，第二轮收到 {len(second_round_results)} 个 Bot 回复",
        metadata={"task_id": task_id}
    )

    return BrainResponse(
        success=True,
        message=final_summary,
        request_id=request_id,
        task_id=task_id,
        context={"first_round": first_round_results, "second_round": second_round_results}
    )


async def _llm_decompose_collaboration(self, user_query: str) -> List[Dict]:
    """
    使用 LLM 拆解协作任务

    策略：
    1. 优先使用 SkillRegistry 语义匹配参与 Bot
    2. 如果匹配度低，降级使用关键词映射

    返回：[{"bot_id": "运营", "prompt": "...", "timeout": 30, "priority": 5}, ...]
    """
    # ========== 步骤 1: 尝试 SkillRegistry 动态匹配 ==========
    candidate_bots = self.skill_registry.find_bots_for_task(user_query, limit=5)

    # 检查是否有有效匹配（分数 > 0.5）
    matched_bots = []
    if candidate_bots:
        for bot_data in candidate_bots:
            bot_name = bot_data.get("bot_name")
            score = bot_data.get("score", 0)
            if score > 0.5:  # 阈值
                matched_bots.append(bot_name)

    if matched_bots:
        logger.info(f"SkillRegistry 匹配到 Bot: {matched_bots}")
        # 取前 3 个（避免太多 Bot 参与导致混乱）
        selected_bots = matched_bots[:3]
    else:
        # ========== 步骤 2: 降级使用关键词映射 ==========
        logger.info("SkillRegistry 未找到高匹配度 Bot，使用关键词降级")
        selected_bots = self._keyword_fallback_decompose(user_query)

    # ========== 步骤 3: 为每个 Bot 生成定制化 Prompt ==========
    subtask_specs = []
    for bot_id in selected_bots:
        # 获取 Bot 的技能描述（用于注入 Prompt）
        skills = self.skill_registry.get_skills(bot_id)
        skill_desc = ""
        if skills:
            skill_desc = "你具备以下专业技能：\n"
            for skill in skills:
                skill_desc += f"- {skill['description']}\n"

        # 生成定制化 Prompt
        if skill_desc:
            prompt = f"""{skill_desc}
请从你的专业角度，参与以下协作讨论：

【用户需求】
{user_query}

请给出你的专业方案（简洁，200 字以内）。"""
        else:
            prompt = f"参与协作讨论：{user_query}\n\n请从你的专业角度给出方案。"

        subtask_specs.append({
            "bot_id": bot_id,
            "prompt": prompt,
            "timeout": 30,
            "priority": 5
        })

    return subtask_specs


async def delegate_to_team(self, team_name: str, brief: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Phase 2: 委托团队任务

    将任务委托给整个团队，根据策略汇总结果

    Args:
        team_name: 团队名称（如"内容团队"、"制作团队"）
        brief: 任务简述
        context: 上下文信息

    Returns:
        {
            "success": bool,
            "team_name": str,
            "results": {bot_id: result},
            "summary": str,
            ...
        }

    Usage:
        result = await brain.delegate_to_team("内容团队", "策划直播活动")
    """
    logger.info(f"委托团队任务：{team_name} - {brief[:50]}...")

    if not self.team_delegator:
        return {
            "success": False,
            "error": "TeamDelegator not available"
        }

    # 执行Team Delegation
    result = await self.team_delegator.delegate_to_team(
        team_name=team_name,
        brief=brief,
        context=context or {}
    )

    if result.get("success"):
        logger.info(f"团队任务完成：{team_name} - {len(result.get('results', {}))} 个 Bot 回复")

        # 记录技能使用（成功的团队调用）
        for bot_id in result.get("bots_responded", []):
            self.skill_registry.record_usage(
                bot_name=bot_id,
                skill_name=f"调用{team_name}",
                success=True
            )

    return result


# 为 CoreBrain 类添加方法
CoreBrain.delegate_to_team = delegate_to_team


def _keyword_fallback_decompose(self, user_query: str) -> List[str]:
    """
    关键词映射降级方法（当 SkillRegistry 匹配失败时使用）

    Returns:
        需要参与的 Bot 列表
    """
    bot_mapping = {
        "流程": "运营",
        "方案": "运营",
        "互动": "运营",
        "策划": "运营",
        "内容": "编导",
        "脚本": "编导",
        "框架": "编导",
        "分镜": "编导",
        "技术": "场控",
        "Device": "场控",
        "推流": "场控",
        "客服": "客服",
        "用户": "客服",
        "设计": "美工",
        "视觉": "美工",
        "剪辑": "剪辑",
        "视频": "剪辑",
        "商务": "渠道",
        "合作": "渠道"
    }

    # 分析查询，分配 Bot
    needed_bots = set()
    for keyword, bot_id in bot_mapping.items():
        if keyword in user_query:
            needed_bots.add(bot_id)

    # 直播相关请求：需要多 Bot 协作（运营 + 编导 + 场控）
    if "直播" in user_query:
        needed_bots.add("运营")
        needed_bots.add("编导")
        needed_bots.add("场控")

    # 活动方案：运营 + 编导
    if "活动" in user_query:
        needed_bots.add("运营")
        needed_bots.add("编导")

    # 默认至少需要运营和编导
    if not needed_bots:
        needed_bots = {"运营", "编导"}

    return list(needed_bots)


async def _llm_summarize_collaboration(
    self,
    user_query: str,
    results: Dict[str, str]
) -> str:
    """
    使用 LLM 汇总各 Bot 回复

    简单版本：直接拼接
    复杂版本：调用 LLM API 进行智能汇总
    """
    if not results:
        return "未收到任何 Bot 回复"

    # 分离成功和错误结果
    success_results = {k: v for k, v in results.items() if not k.startswith("error_")}
    error_results = {k: v for k, v in results.items() if k.startswith("error_")}

    # 拼接回复
    lines = [f"关于：{user_query}\n"]
    lines.append("-" * 40)

    for bot_id, response in success_results.items():
        lines.append(f"\n【{bot_id}】")
        lines.append(response)

    if error_results:
        lines.append("\n" + "-" * 40)
        lines.append("以下 Bot 未响应:")
        for bot_id, error in error_results.items():
            lines.append(f"- {bot_id}: {error}")

    lines.append("\n" + "-" * 40)
    lines.append("如需查看任务详情，请访问 Dashboard 或回复任务 ID 查询。")

    return "\n".join(lines)


async def _llm_summarize_collaboration_with_rounds(
    self,
    user_query: str,
    first_round: Dict[str, str],
    second_round: Dict[str, str]
) -> str:
    """
    汇总两轮讨论结果

    Args:
        user_query: 用户原始问题
        first_round: 第一轮各 Bot 方案
        second_round: 第二轮补充意见

    Returns:
        str: 最终汇总结果
    """
    if not first_round:
        return "未收到任何 Bot 回复"

    lines = [f"关于：{user_query}\n"]
    lines.append("=" * 50)
    lines.append("【第一轮：各 Bot 方案】")
    lines.append("=" * 50)

    # 第一轮结果
    first_success = {k: v for k, v in first_round.items() if not k.startswith("error_")}
    for bot_id, response in first_success.items():
        lines.append(f"\n【{bot_id}】")
        lines.append(response)

    # 第二轮结果
    second_success = {k: v for k, v in second_round.items() if not k.startswith("error_")}
    if second_success:
        lines.append("\n" + "=" * 50)
        lines.append("【第二轮：补充意见】")
        lines.append("=" * 50)
        for bot_id, response in second_success.items():
            lines.append(f"\n【{bot_id} 补充】")
            lines.append(response)

    lines.append("\n" + "=" * 50)
    lines.append("讨论结束。如需进一步细化，请回复具体指令。")

    return "\n".join(lines)


# 给 CoreBrain 类添加方法
CoreBrain.process_collaboration_request = process_collaboration_request
CoreBrain._llm_decompose_collaboration = _llm_decompose_collaboration
CoreBrain._llm_summarize_collaboration = _llm_summarize_collaboration
CoreBrain._llm_summarize_collaboration_with_rounds = _llm_summarize_collaboration_with_rounds
CoreBrain._keyword_fallback_decompose = _keyword_fallback_decompose


# ============ 命令行测试 ============

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    async def main():
        print("=" * 60)
        print("Phoenix Core - 主大脑测试")
        print("=" * 60)

        brain = CoreBrain(BrainConfig(debug=True))

        # 测试用例
        test_inputs = [
            "你好",  # 闲聊
            "帮我查订单 #12345",  # 查询任务
            "退款订单 #12345",  # 执行任务
        ]

        for user_input in test_inputs:
            print(f"\n用户：{user_input}")
            response = await brain.process(user_input, "test_user")
            print(f"回复：{response.message}")
            print(f"成功：{response.success}")
            print(f"请求 ID: {response.request_id}")

        await brain.shutdown()

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        asyncio.run(main())
    else:
        print("Usage: python3 core_brain.py test")
        print("\n模块已就绪，可以通过以下方式导入:")
        print("  from phoenix_core import CoreBrain, get_brain, process_input")

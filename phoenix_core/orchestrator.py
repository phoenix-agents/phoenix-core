#!/usr/bin/env python3
"""
Phoenix Core Orchestrator - 编排器模块

小小谦 (XiaoXiaoQian) 的总控逻辑封装。

职责：
1. 接收用户消息
2. 意图识别
3. 协议生成
4. 路由分发到 Worker Bot
5. 等待 Bot 回复
6. 结果汇总
7. 返回用户友好回复

Usage:
    from phoenix_core.orchestrator import Orchestrator

    orchestrator = Orchestrator()
    response = await orchestrator.handle_user_message("问问场控在不在")
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Callable

from phoenix_core.intent_recognition import IntentRecognizer, Intent
from phoenix_core.protocol_generator import ProtocolGenerator
from phoenix_core.protocol_parser import ProtocolParser, ProtocolMessage
from phoenix_core.task_tracker import TaskTracker, TaskStatus
from phoenix_core.result_aggregator import ResultAggregator
from phoenix_core.intent_router import IntentRouter

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    """编排器配置"""

    # Bot 名称
    controller_name: str = "小小谦"

    # Bot ID
    controller_id: str = "1483335704590155786"

    # 默认超时（秒）
    simple_inquiry_timeout: int = 30
    execution_task_timeout: int = 300
    complex_analysis_timeout: int = 600

    # 最大重试次数
    max_retries: int = 2

    # 是否启用调试日志
    debug: bool = False


class Orchestrator:
    """
    Phoenix Core 编排器

    负责协调用户消息和 Worker Bot 之间的交互
    """

    def __init__(self, config: Optional[OrchestratorConfig] = None):
        """
        初始化编排器

        Args:
            config: 配置对象（可选）
        """
        self.config = config or OrchestratorConfig()

        # 初始化核心模块
        self.intent_recognizer = IntentRecognizer(default_bot=self.config.controller_name)
        self.protocol_generator = ProtocolGenerator()
        self.protocol_parser = ProtocolParser()
        self.task_tracker = TaskTracker()
        self.result_aggregator = ResultAggregator()
        self.intent_router = IntentRouter()

        # Bot 回复回调（由外部设置）
        self._send_protocol_callback: Optional[Callable] = None
        self._receive_protocol_callback: Optional[Callable] = None

        # 待处理任务
        self._pending_tasks: Dict[str, asyncio.Future] = {}

        logger.info(f"Orchestrator initialized (controller={self.config.controller_name})")

    def set_send_callback(self, callback: Callable):
        """
        设置发送协议消息的回调

        Args:
            callback: 异步函数，接收 protocol_str，返回 None
        """
        self._send_protocol_callback = callback

    def set_receive_callback(self, callback: Callable):
        """
        设置接收协议消息的回调

        Args:
            callback: 异步函数，接收 protocol_str，返回 None
        """
        self._receive_protocol_callback = callback

    async def handle_user_message(
        self,
        user_message: str,
        user_id: str = "user",
        channel_id: str = "default"
    ) -> str:
        """
        处理用户消息

        Args:
            user_message: 用户消息（自然语言）
            user_id: 用户 ID
            channel_id: 频道 ID

        Returns:
            回复用户的消息
        """
        logger.info(f"收到用户消息：{user_message[:50]}...")

        # Step 1: 意图识别
        intent = self.intent_recognizer.recognize(user_message)
        logger.info(f"识别意图：{intent.intent_type} -> {intent.target_bot} (confidence={intent.confidence})")

        # Step 2: 闲聊直接回复
        if intent.intent_type == "chat":
            return await self._handle_chat(user_message, intent)

        # Step 3: 生成协议消息
        # 先生成 request_id，用于任务创建和协议生成（确保一致性）
        request_id = self.protocol_generator.generate_request_id()
        protocol = self.protocol_generator.generate_from_intent(intent, request_id=request_id)
        logger.info(f"生成协议：{protocol[:80]}...")

        # Step 4: 创建任务并追踪
        task = self.task_tracker.create_task(
            request_id=request_id,
            intent_type=intent.intent_type,
            target_bot=intent.target_bot,
            content=intent.content,
            protocol=protocol,
        )

        # Step 5: 发送协议消息给 Worker Bot
        if self._send_protocol_callback:
            await self._send_protocol_callback(protocol)

        self.task_tracker.mark_sent(task.request_id)
        logger.info(f"任务已发送：{task.request_id}")

        # Step 6: 等待 Bot 回复
        timeout = self._get_timeout(intent.intent_type)
        response = await self._wait_for_bot_response(
            task.request_id,
            timeout=timeout,
            bot_name=intent.target_bot
        )

        if not response:
            return self._handle_timeout(intent.target_bot)

        # Step 7: 解析 Bot 回复（RESPONSE 类型已经是纯文本，不需要解析协议）
        # 只有 CONFIRM/DONE/FAIL 等类型才需要协议解析
        if response.startswith('['):
            parsed = self.protocol_parser.parse(response)
            if not parsed:
                logger.error(f"无法解析 Bot 回复：{response[:50]}...")
                return f"{intent.target_bot} 已收到，但回复格式有误。"

            # Step 8: 更新任务状态
            self._update_task_status(task, parsed)

            # Step 9: 结果汇总
            result = self.result_aggregator.aggregate(response, intent.target_bot)
            if not result:
                return parsed.content

            logger.info(f"汇总结果：{result.user_message}")
            return result.user_message
        else:
            # 直接返回 RESPONSE 内容（纯文本）
            logger.info(f"收到 RESPONSE 内容：{response[:50]}...")
            return response

    async def _handle_chat(self, user_message: str, intent: Intent) -> str:
        """
        处理闲聊

        Args:
            user_message: 用户消息
            intent: 意图对象

        Returns:
            回复消息
        """
        # 闲聊直接回复，不经过 Worker Bot
        # TODO: 集成 LLM 回复
        return "我在~ 有什么可以帮您的吗？😊"

    async def _wait_for_bot_response(
        self,
        request_id: str,
        timeout: int = 30,
        bot_name: str = ""
    ) -> Optional[str]:
        """
        等待 Bot 回复

        Args:
            request_id: 请求 ID
            timeout: 超时时间（秒）
            bot_name: Bot 名称

        Returns:
            Bot 回复内容，超时返回 None
        """
        logger.info(f"等待 {bot_name} 回复 (timeout={timeout}s)...")

        # 创建 Future 用于等待
        future = asyncio.Future()
        self._pending_tasks[request_id] = future

        try:
            # 等待回复
            response = await asyncio.wait_for(future, timeout=timeout)
            logger.info(f"收到 {bot_name} 回复")
            return response
        except asyncio.TimeoutError:
            logger.warning(f"{bot_name} 回复超时")
            return None
        finally:
            self._pending_tasks.pop(request_id, None)

    async def handle_protocol_message(self, protocol_str: str):
        """
        处理收到的协议消息（由 Worker Bot 发送）

        Args:
            protocol_str: 协议格式消息
        """
        # 解析协议
        parsed = self.protocol_parser.parse(protocol_str)
        if not parsed:
            logger.warning(f"无法解析协议消息：{protocol_str[:50]}...")
            return

        # 忽略非回复消息
        if parsed.message_type not in {"CONFIRM", "REPORT", "DONE", "FAIL", "RESPONSE"}:
            return

        # 查找待处理任务
        future = self._pending_tasks.get(parsed.request_id)
        if future and not future.done():
            logger.info(f"收到任务回复：{parsed.request_id} ({parsed.message_type})")
            # For RESPONSE type, extract just the content (not the protocol header)
            if parsed.message_type == "RESPONSE":
                future.set_result(parsed.content)
            else:
                future.set_result(protocol_str)
        else:
            logger.debug(f"未找到待处理任务：{parsed.request_id}")

    def _update_task_status(self, task, parsed: ProtocolMessage):
        """更新任务状态"""
        if parsed.message_type == "CONFIRM":
            self.task_tracker.mark_confirmed(task.request_id, parsed.content)
        elif parsed.message_type == "DONE":
            self.task_tracker.mark_done(task.request_id, parsed.content)
        elif parsed.message_type == "FAIL":
            self.task_tracker.mark_failed(task.request_id, parsed.content)
        elif parsed.message_type == "REPORT":
            # 进度汇报，不改变状态
            pass

    def _get_timeout(self, intent_type: str) -> int:
        """根据意图类型获取超时时间"""
        if intent_type == "inquiry":
            return self.config.simple_inquiry_timeout
        elif intent_type == "task":
            return self.config.execution_task_timeout
        elif intent_type == "status":
            return self.config.simple_inquiry_timeout
        else:
            return self.config.simple_inquiry_timeout

    def _handle_timeout(self, bot_name: str) -> str:
        """处理超时"""
        return f"{bot_name} 响应超时，请稍后重试。"

    def get_task_status(self, request_id: str) -> Optional[Dict]:
        """
        获取任务状态

        Args:
            request_id: 请求 ID

        Returns:
            任务状态字典
        """
        task = self.task_tracker.get_task(request_id)
        if not task:
            return None

        return {
            "request_id": task.request_id,
            "status": task.status.value,
            "target_bot": task.target_bot,
            "created_at": task.created_at,
            "response": task.response,
        }

    def list_active_tasks(self) -> List[Dict]:
        """列出所有活跃任务"""
        tasks = self.task_tracker.get_active_tasks()
        return [
            {
                "request_id": task.request_id,
                "status": task.status.value,
                "target_bot": task.target_bot,
                "content": task.content[:30],
            }
            for task in tasks
        ]

    def cleanup(self):
        """清理资源"""
        self.task_tracker.cleanup_completed()
        logger.info("Orchestrator cleanup complete")


# 全局单例
_global_orchestrator: Optional[Orchestrator] = None


def get_orchestrator(config: Optional[OrchestratorConfig] = None) -> Orchestrator:
    """获取全局编排器实例"""
    global _global_orchestrator
    if _global_orchestrator is None:
        _global_orchestrator = Orchestrator(config)
    return _global_orchestrator


# 命令行测试
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    async def test_orchestrator():
        """测试编排器"""
        print("=" * 60)
        print("编排器测试")
        print("=" * 60)

        orchestrator = Orchestrator()

        # 测试用例
        test_messages = [
            "你好",  # 闲聊
            "问问场控在不在",  # 询问
            "场控任务完成了吗",  # 状态查询
        ]

        for msg in test_messages:
            print(f"\n用户：{msg}")
            # 注意：实际使用需要设置回调
            # response = await orchestrator.handle_user_message(msg)
            # print(f"回复：{response}")

        print("\n提示：完整测试需要设置 send/receive 回调")

    asyncio.run(test_orchestrator())

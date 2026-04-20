#!/usr/bin/env python3
"""
Phoenix Core Gateway Concurrency Manager - 并发管理模块

功能:
1. 多用户并发隔离
2. 多子任务并行执行
3. 结果汇总
4. 错误重试机制
"""

import asyncio
import uuid
import logging
from collections import defaultdict
from typing import Dict, List, Optional, Set, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class SubTaskResult:
    """子任务执行结果"""
    def __init__(self, sub_task_id: str, bot_id: str, content: str,
                 is_final: bool = False, error: Optional[str] = None):
        self.sub_task_id = sub_task_id
        self.bot_id = bot_id
        self.content = content
        self.is_final = is_final
        self.error = error
        self.timestamp = datetime.now()

    def __repr__(self):
        return f"SubTaskResult({self.sub_task_id}, {self.bot_id}, final={self.is_final})"


class GatewayConcurrencyManager:
    """
    Gateway 并发管理器

    数据结构:
    self.pending: user_id -> request_id -> sub_task_id -> Future
    self.task_subtasks: request_id -> {sub_task_id_set}
    self.subtask_results: request_id -> {sub_task_id -> SubTaskResult}
    """

    def __init__(self, max_retries: int = 2, default_timeout: float = 30.0):
        # 用户 -> 请求 -> 子任务 -> Future
        self.pending: Dict[str, Dict[str, Dict[str, asyncio.Future]]] = defaultdict(dict)
        # 请求 ID -> 子任务 ID 集合
        self.task_subtasks: Dict[str, Set[str]] = defaultdict(set)
        # 请求 ID -> 子任务 ID -> 结果
        self.subtask_results: Dict[str, Dict[str, SubTaskResult]] = defaultdict(dict)
        # 重试配置
        self.max_retries = max_retries
        self.default_timeout = default_timeout
        # 发送回调 (由外部设置)
        self._send_callback: Optional[callable] = None

    def set_send_callback(self, callback: callable):
        """设置发送协议消息的回调"""
        self._send_callback = callback

    # ============ 请求生命周期管理 ============

    def create_request(self, user_id: str) -> str:
        """
        为用户创建一个新的请求 ID

        Args:
            user_id: 用户 Discord ID

        Returns:
            request_id (格式：UID-YYYYMMDD-XXX)
        """
        user_prefix = user_id[-4:] if len(user_id) >= 4 else user_id
        date_str = datetime.now().strftime("%Y%m%d")

        # 生成唯一序列号
        seq = len(self.pending.get(user_id, {})) + 1
        request_id = f"{user_prefix}-{date_str}-{seq:03d}"

        # 初始化数据结构
        self.pending[user_id][request_id] = {}
        self.task_subtasks[request_id] = set()
        self.subtask_results[request_id] = {}

        logger.info(f"创建请求：user={user_id}, request_id={request_id}")
        return request_id

    def cancel_request(self, user_id: str, request_id: str, reason: str = "用户取消"):
        """
        取消请求，清理所有相关资源

        Args:
            user_id: 用户 ID
            request_id: 请求 ID
            reason: 取消原因
        """
        if user_id in self.pending and request_id in self.pending[user_id]:
            # 取消所有待处理的 Future
            for sub_task_id, future in self.pending[user_id][request_id].items():
                if not future.done():
                    future.set_exception(asyncio.CancelledError(f"任务取消：{reason}"))

            # 清理数据结构
            del self.pending[user_id][request_id]

            # 清理子任务集合 (保留结果用于查询)
            # self.task_subtasks.pop(request_id, None)
            # self.subtask_results.pop(request_id, None)

            logger.info(f"取消请求：request_id={request_id}, reason={reason}")

    def cleanup_user(self, user_id: str):
        """
        清理用户所有资源 (用户离线时调用)

        Args:
            user_id: 用户 Discord ID
        """
        if user_id in self.pending:
            for request_id in list(self.pending[user_id].keys()):
                self.cancel_request(user_id, request_id, "用户离线")
            del self.pending[user_id]

        logger.info(f"清理用户资源：user={user_id}")

    # ============ 子任务管理 ============

    def register_subtask(self, user_id: str, request_id: str, sub_task_id: str) -> asyncio.Future:
        """
        注册一个子任务，返回等待 Future

        Args:
            user_id: 用户 ID
            request_id: 请求 ID
            sub_task_id: 子任务 ID

        Returns:
            asyncio.Future: 用于等待子任务结果
        """
        future = asyncio.get_event_loop().create_future()

        # 确保数据结构初始化
        if user_id not in self.pending:
            self.pending[user_id] = {}
        if request_id not in self.pending[user_id]:
            self.pending[user_id][request_id] = {}

        self.pending[user_id][request_id][sub_task_id] = future
        self.task_subtasks[request_id].add(sub_task_id)

        logger.debug(f"注册子任务：request={request_id}, sub_task={sub_task_id}")
        return future

    def resolve_subtask(self, user_id: str, request_id: str, sub_task_id: str,
                        result: str, bot_id: str = "", is_final: bool = False):
        """
        子任务完成，设置结果

        Args:
            user_id: 用户 ID
            request_id: 请求 ID
            sub_task_id: 子任务 ID
            result: 子任务结果
            bot_id: Bot ID
            is_final: 是否是最终结果
        """
        if request_id not in self.pending.get(user_id, {}):
            logger.warning(f"请求不存在：user={user_id}, request={request_id}")
            return

        if sub_task_id not in self.pending[user_id][request_id]:
            logger.warning(f"子任务不存在：request={request_id}, sub_task={sub_task_id}")
            return

        future = self.pending[user_id][request_id][sub_task_id]
        if not future.done():
            future.set_result(result)

        # 保存结果
        self.subtask_results[request_id][sub_task_id] = SubTaskResult(
            sub_task_id=sub_task_id,
            bot_id=bot_id,
            content=result,
            is_final=is_final
        )

        logger.info(f"子任务完成：request={request_id}, sub_task={sub_task_id}, final={is_final}")

    def fail_subtask(self, user_id: str, request_id: str, sub_task_id: str,
                     error: str, bot_id: str = ""):
        """
        子任务失败

        Args:
            user_id: 用户 ID
            request_id: 请求 ID
            sub_task_id: 子任务 ID
            error: 错误信息
            bot_id: Bot ID
        """
        if request_id not in self.pending.get(user_id, {}):
            return

        if sub_task_id not in self.pending[user_id][request_id]:
            return

        future = self.pending[user_id][request_id][sub_task_id]
        if not future.done():
            future.set_exception(Exception(error))

        # 保存错误结果
        self.subtask_results[request_id][sub_task_id] = SubTaskResult(
            sub_task_id=sub_task_id,
            bot_id=bot_id,
            content="",
            error=error
        )

        logger.warning(f"子任务失败：request={request_id}, sub_task={sub_task_id}, error={error}")

    # ============ 状态查询 ============

    def is_all_subtasks_done(self, request_id: str) -> bool:
        """
        检查某个请求的所有子任务是否都已完成

        Args:
            request_id: 请求 ID

        Returns:
            bool: 是否全部完成
        """
        if request_id not in self.task_subtasks:
            return True

        return all(
            sub in self.subtask_results[request_id]
            for sub in self.task_subtasks[request_id]
        )

    def is_any_subtask_final(self, request_id: str) -> bool:
        """
        检查是否有任意子任务标记为 FINAL

        Args:
            request_id: 请求 ID

        Returns:
            bool: 是否有 FINAL 标志
        """
        results = self.subtask_results.get(request_id, {})
        return any(r.is_final for r in results.values())

    def get_all_results(self, request_id: str) -> Dict[str, SubTaskResult]:
        """
        获取某个请求的所有子任务结果

        Args:
            request_id: 请求 ID

        Returns:
            Dict: sub_task_id -> SubTaskResult
        """
        return self.subtask_results.get(request_id, {})

    def get_pending_subtasks(self, request_id: str) -> Set[str]:
        """
        获取尚未完成的子任务 ID

        Args:
            request_id: 请求 ID

        Returns:
            Set: 未完成的 sub_task_id 集合
        """
        completed = set(self.subtask_results.get(request_id, {}).keys())
        all_tasks = self.task_subtasks.get(request_id, set())
        return all_tasks - completed

    # ============ 并行执行 ============

    async def call_bot_with_subtask(
        self,
        user_id: str,
        request_id: str,
        sub_task_id: str,
        bot_id: str,
        message: str,
        protocol_msg: str,
        timeout: Optional[float] = None
    ) -> str:
        """
        带子任务 ID 的 Bot 调用 (支持重试)

        Args:
            user_id: 用户 ID
            request_id: 请求 ID
            sub_task_id: 子任务 ID
            bot_id: Bot ID
            message: 消息内容
            protocol_msg: 协议格式消息
            timeout: 超时时间 (秒)

        Returns:
            str: Bot 回复内容
        """
        if timeout is None:
            timeout = self.default_timeout

        # 注册子任务
        future = self.register_subtask(user_id, request_id, sub_task_id)

        retry_count = 0
        last_error = None

        while retry_count <= self.max_retries:
            try:
                # 发送协议消息
                if self._send_callback:
                    await self._send_callback(bot_id, protocol_msg)
                else:
                    logger.error("未设置发送回调")

                # 等待回复
                result = await asyncio.wait_for(future, timeout=timeout)
                return result

            except asyncio.TimeoutError:
                retry_count += 1
                last_error = f"超时 (重试{retry_count}/{self.max_retries})"
                logger.warning(f"子任务超时：{bot_id}, 重试 {retry_count}/{self.max_retries}")

                if retry_count > self.max_retries:
                    break

                # 重试前等待一小段时间
                await asyncio.sleep(1.0 * retry_count)

            except asyncio.CancelledError:
                logger.info(f"子任务取消：{bot_id}")
                return f"[取消] 任务已被终止 ({sub_task_id})"

            except Exception as e:
                logger.error(f"子任务异常：{bot_id}, error={e}")
                last_error = str(e)
                retry_count += 1

                if retry_count > self.max_retries:
                    break

        # 所有重试失败
        error_msg = f"[错误] {bot_id} 调用失败：{last_error} (重试{retry_count}次)"
        self.fail_subtask(user_id, request_id, sub_task_id, error_msg, bot_id)
        return error_msg

    async def execute_parallel_subtasks(
        self,
        user_id: str,
        request_id: str,
        subtasks: List[Dict[str, str]]
    ) -> Dict[str, str]:
        """
        并行执行多个子任务

        Args:
            user_id: 用户 ID
            request_id: 请求 ID
            subtasks: [{"bot_id": "xxx", "sub_task_id": "sub-0", "message": "xxx", "protocol": "xxx"}]

        Returns:
            Dict: sub_task_id -> result
        """
        tasks = []
        for subtask in subtasks:
            tasks.append(
                self.call_bot_with_subtask(
                    user_id=user_id,
                    request_id=request_id,
                    sub_task_id=subtask["sub_task_id"],
                    bot_id=subtask["bot_id"],
                    message=subtask["message"],
                    protocol_msg=subtask["protocol"]
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            subtask["sub_task_id"]: str(r) if not isinstance(r, Exception) else f"错误：{r}"
            for subtask, r in zip(subtasks, results)
        }

    async def wait_for_all_subtasks(
        self,
        user_id: str,
        request_id: str,
        timeout: Optional[float] = None
    ) -> Dict[str, str]:
        """
        等待所有子任务完成

        Args:
            user_id: 用户 ID
            request_id: 请求 ID
            timeout: 总超时时间 (秒)

        Returns:
            Dict: sub_task_id -> result
        """
        if timeout is None:
            timeout = self.default_timeout * len(self.task_subtasks.get(request_id, {1}))

        start_time = datetime.now()

        while not self.is_all_subtasks_done(request_id):
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > timeout:
                logger.warning(f"等待子任务超时：request={request_id}")
                break
            await asyncio.sleep(0.5)

        return self.get_all_results(request_id)


# ============ 聚合器 ============

class ResultAggregator:
    """结果聚合器"""

    @staticmethod
    def aggregate(results: Dict[str, SubTaskResult]) -> str:
        """
        聚合多个子任务结果

        Args:
            results: sub_task_id -> SubTaskResult

        Returns:
            str: 聚合后的消息
        """
        if not results:
            return "无结果"

        parts = []
        for sub_task_id, result in sorted(results.items()):
            if result.error:
                parts.append(f"[{result.bot_id}] {result.error}")
            else:
                parts.append(f"[{result.bot_id}] {result.content}")

        return "\n\n".join(parts)

    @staticmethod
    def aggregate_with_summary(results: Dict[str, SubTaskResult], summary: str = "") -> str:
        """
        聚合结果 + 总结

        Args:
            results: 子任务结果
            summary: 总结语

        Returns:
            str: 聚合后的消息
        """
        aggregated = ResultAggregator.aggregate(results)
        if summary:
            return f"{summary}\n\n{aggregated}"
        return aggregated

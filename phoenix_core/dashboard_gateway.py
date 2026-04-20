#!/usr/bin/env python3
"""
Phoenix Core Dashboard Gateway - 虚拟网关

用于 Dashboard 直接与大脑交互，不依赖 Discord

特点:
1. 无需 Discord 连接
2. 任务直接分发到"虚拟 Bot"
3. 响应基于 Bot 身份模拟生成
4. 适用于快速测试和离线场景

架构:
┌─────────────────────────────────────────┐
│         Dashboard (HTTP)                 │
│              ↓                           │
│    DashboardGateway                      │
│    - 虚拟分发                            │
│    - 模拟响应                            │
│    - 状态持久化                          │
└─────────────────────────────────────────┘
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from phoenix_core.task_dispatcher import TaskDispatcher, SubTask, get_dispatcher
from phoenix_core.task_tracker import TaskTracker

logger = logging.getLogger(__name__)


class DashboardGateway:
    """
    Dashboard 虚拟网关

    模拟 Bot 响应，用于离线测试和快速原型
    """

    # Bot 身份和职责映射
    BOT_PROFILES = {
        "运营": {
            "role": "直播运营专家",
            "style": "注重流程、互动、数据",
            "keywords": ["流程", "互动", "方案", "推广", "数据", "转化"]
        },
        "编导": {
            "role": "内容编导专家",
            "style": "注重内容、节奏、脚本",
            "keywords": ["内容", "脚本", "分镜", "节奏", "创意"]
        },
        "场控": {
            "role": "直播场控专家",
            "style": "注重技术、设备、配合",
            "keywords": ["技术", "设备", "推流", "配合", "现场"]
        },
        "客服": {
            "role": "客服专家",
            "style": "注重用户、解答、反馈",
            "keywords": ["用户", "解答", "反馈", "咨询"]
        },
        "美工": {
            "role": "视觉设计专家",
            "style": "注重视觉、设计、品牌",
            "keywords": ["设计", "视觉", "海报", "品牌"]
        },
        "剪辑": {
            "role": "视频剪辑专家",
            "style": "注重剪辑、特效、节奏",
            "keywords": ["剪辑", "特效", "视频", "后期"]
        },
        "渠道": {
            "role": "商务合作专家",
            "style": "注重合作、资源、商务",
            "keywords": ["合作", "资源", "商务", "拓展"]
        },
        "小小谦": {
            "role": "协调整合专家",
            "style": "注重汇总、分工、进度",
            "keywords": ["协调", "分工", "进度", "汇总"]
        }
    }

    def __init__(self, workspace: str = "."):
        self.workspace = Path(workspace)
        self.bot_name = "DashboardGateway"

        # 并发管理器（用于等待响应）
        self._pending_responses: Dict[str, asyncio.Future] = {}

        # 任务分发器
        self.dispatcher = TaskDispatcher(gateway=self)

        # 任务追踪器
        self.tracker = TaskTracker()

        logger.info("DashboardGateway 初始化完成")

    async def send_to_bot(
        self,
        bot_id: str,
        message: str,
        request_id: str = None
    ) -> str:
        """
        发送消息给 Bot 并等待响应（虚拟模拟）

        Args:
            bot_id: Bot 名称
            message: 消息内容
            request_id: 请求 ID

        Returns:
            Bot 响应
        """
        logger.info(f"[虚拟] 发送给 {bot_id}: {message[:50]}...")

        # 创建 Future 等待响应
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending_responses[request_id or f"req-{datetime.now().timestamp()}"] = future

        # 模拟 Bot 处理延迟
        await asyncio.sleep(0.5)

        # 生成模拟响应
        response = self._simulate_bot_response(bot_id, message)

        # 设置响应结果
        future.set_result(response)

        return response

    def _simulate_bot_response(self, bot_id: str, message: str) -> str:
        """
        根据 Bot 身份模拟响应

        Args:
            bot_id: Bot 名称
            message: 消息内容

        Returns:
            模拟的 Bot 响应
        """
        profile = self.BOT_PROFILES.get(bot_id, {
            "role": "助手",
            "style": "通用",
            "keywords": []
        })

        # 生成符合 Bot 身份的响应
        timestamp = datetime.now().strftime("%H:%M:%S")

        response_lines = [
            f"【{bot_id}】{timestamp}",
            f"角色：{profile['role']}",
            f"风格：{profile['style']}",
            "",
            "收到任务，我的建议：",
            "",
        ]

        # 根据 Bot 类型生成专业回复
        if bot_id == "运营":
            response_lines.extend([
                "1. 流程设计：建议采用三段式结构（开场→高潮→收尾）",
                "2. 互动抓手：设置 2-3 个弹幕触发点，提升参与感",
                "3. 数据盯盘：重点关注停留时长和互动率",
                "",
                "需要我输出详细 SOP 吗？"
            ])
        elif bot_id == "编导":
            response_lines.extend([
                "1. 内容框架：先定情绪曲线（平→起→高→落）",
                "2. 钩子预埋：前 3 秒必须有留人点",
                "3. 脚本节奏：每 5 分钟一个小高潮",
                "",
                "需要我出分镜脚本吗？"
            ])
        elif bot_id == "场控":
            response_lines.extend([
                "1. 技术检查：推流、收音、灯光提前测试",
                "2. 配合节点：标记好需要切镜/特效的时间点",
                "3. 应急预案：准备好备用方案",
                "",
                "需要我列设备清单吗？"
            ])
        elif bot_id == "客服":
            response_lines.extend([
                "1. 用户问题预判：提前准备 FAQ",
                "2. 反馈收集：设置专门的反馈入口",
                "3. 响应时效：承诺 24 小时内回复",
                "",
                "需要我整理常见问题吗？"
            ])
        elif bot_id == "美工":
            response_lines.extend([
                "1. 视觉风格：先确定主色调和字体",
                "2. 输出物清单：封面、海报、贴片",
                "3. 品牌一致性：保持统一视觉语言",
                "",
                "需要我出设计稿吗？"
            ])
        elif bot_id == "剪辑":
            response_lines.extend([
                "1. 素材整理：先归类再剪辑",
                "2. 节奏把控：根据 BGM 切点",
                "3. 特效适度：不要喧宾夺主",
                "",
                "需要我出剪辑方案吗？"
            ])
        elif bot_id == "渠道":
            response_lines.extend([
                "1. 合作资源：盘点现有合作渠道",
                "2. 引流策略：设置专属引流入口",
                "3. 转化路径：明确用户流转路径",
                "",
                "需要我出合作方案吗？"
            ])
        else:
            response_lines.extend([
                f"我会从 {profile['style']} 角度提供支持",
                "",
                "请告诉我具体需求"
            ])

        return "\n".join(response_lines)

    async def dispatch_collaboration(
        self,
        user_query: str,
        user_id: str,
        target_bots: List[str] = None
    ) -> Dict[str, Any]:
        """
        分发协作任务

        Args:
            user_query: 用户请求
            user_id: 用户 ID
            target_bots: 目标 Bot 列表（None 则自动识别）

        Returns:
            任务结果
        """
        # 生成任务 ID
        task_id = self.dispatcher.generate_task_id(user_id)

        # 如果没有指定 Bot，自动识别
        if not target_bots:
            target_bots = self._auto_identify_bots(user_query)

        logger.info(f"创建协作任务：{task_id}, Bots: {target_bots}")

        # 创建子任务
        subtasks = []
        for bot_id in target_bots:
            subtasks.append(SubTask(
                bot_id=bot_id,
                prompt=f"参与协作：{user_query}\n请从你的专业角度给出方案。",
                deadline=datetime.now().replace(minute=59, second=59),
                priority=5,
                timeout_seconds=60
            ))

        # 分发给 Bot
        results = await self.dispatcher.dispatch(
            task_id=task_id,
            user_id=user_id,
            query=user_query,
            subtasks=subtasks
        )

        return {
            "task_id": task_id,
            "user_id": user_id,
            "query": user_query,
            "target_bots": target_bots,
            "results": results,
            "created_at": datetime.now().isoformat()
        }

    def _auto_identify_bots(self, user_query: str) -> List[str]:
        """
        根据查询自动识别需要的 Bot

        Args:
            user_query: 用户请求

        Returns:
            Bot 列表
        """
        bot_keywords = {
            "运营": ["流程", "互动", "方案", "推广", "数据", "转化", "活动"],
            "编导": ["内容", "脚本", "分镜", "节奏", "创意", "策划"],
            "场控": ["技术", "设备", "推流", "配合", "现场", "调试"],
            "客服": ["用户", "解答", "反馈", "咨询", "问题"],
            "美工": ["设计", "视觉", "海报", "封面", "品牌"],
            "剪辑": ["剪辑", "特效", "视频", "后期", "切片"],
            "渠道": ["合作", "资源", "商务", "拓展", "引流"]
        }

        needed_bots = set()
        for bot_id, keywords in bot_keywords.items():
            for kw in keywords:
                if kw in user_query:
                    needed_bots.add(bot_id)
                    break

        # 默认至少需要运营和编导
        if not needed_bots:
            needed_bots = {"运营", "编导"}

        return list(needed_bots)

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """查询任务状态"""
        return self.dispatcher.get_task_status(task_id)

    def list_tasks(self, limit: int = 20) -> List[Dict]:
        """列出最近任务"""
        tasks_dir = self.dispatcher.storage_path
        if not tasks_dir.exists():
            return []

        task_files = sorted(
            tasks_dir.glob("TASK-*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )[:limit]

        tasks = []
        for f in task_files:
            import json
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                tasks.append(data)
            except:
                continue

        return tasks


# 单例模式
_gateway: Optional[DashboardGateway] = None


def get_dashboard_gateway() -> DashboardGateway:
    """获取 Dashboard Gateway 单例"""
    global _gateway
    if _gateway is None:
        _gateway = DashboardGateway()
    return _gateway

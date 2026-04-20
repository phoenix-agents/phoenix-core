#!/usr/bin/env python3
"""
Phoenix Core Dashboard API Server

提供:
1. /api/chat - 与大脑对话
2. /api/bots - Bot 列表
3. /api/tasks - 任务状态
4. /api/github/* - GitHub 监控
5. WebSocket 实时推送

Usage:
    # 独立运行模式（用于调试，会自己创建大脑实例）
    python3 api_server.py --port 8001

    # 嵌入式模式（由 Gateway 调用，复用 Gateway 的大脑）
    from phoenix_core.api_server import create_app
    app = create_app(brain=gateway.brain, gateway=gateway)
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional, Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str
    user_id: str = "dashboard-user"


def create_app(
    brain: Any = None,
    gateway: Any = None,
    discord_client: Any = None,
    discord_brain_gateway: Any = None,
    project_dir: str = None
) -> FastAPI:
    """
    创建 FastAPI 应用

    Args:
        brain: Phoenix Core 大脑实例（可选，未提供则自己创建）
        gateway: PhoenixCoreGateway 实例（可选，用于发送 Discord 消息）
        discord_client: BrainDiscordClient 实例（可选，用于直连 Discord）
        discord_brain_gateway: DiscordBrainGateway 实例（可选，用于接收 Discord 响应）
        project_dir: 项目根目录（可选，默认当前目录）

    Returns:
        FastAPI 应用实例
    """
    from pathlib import Path

    if project_dir:
        PROJECT_DIR = Path(project_dir)
    else:
        PROJECT_DIR = Path(__file__).parent.parent

    app = FastAPI(
        title="Phoenix Core Dashboard",
        description="Phoenix Core 多 Bot 协作管理平台",
        version="2.0"
    )

    # 存储全局状态
    app.state.brain = brain
    app.state.gateway = gateway
    app.state.discord_client = discord_client
    app.state.discord_brain_gateway = discord_brain_gateway
    app.state.PROJECT_DIR = PROJECT_DIR

    # ============ 辅助函数 ============

    def _get_brain():
        """获取大脑实例（优先使用传入的，否则自己创建）"""
        if app.state.brain:
            return app.state.brain
        # 独立调试模式：自己创建大脑
        from phoenix_core.core_brain import get_brain
        return get_brain()

    def _is_collaboration_request(content: str) -> bool:
        """判断是否是协作请求"""
        collaboration_keywords = ["讨论", "组织", "协调", "大家一起", "一起", "都", "各自", "协作", "配合", "分工"]
        for kw in collaboration_keywords:
            if kw in content:
                return True

        strong_planning_keywords = ["直播方案", "直播策划", "活动方案", "活动策划", "多 Bot", "团队协作"]
        for kw in strong_planning_keywords:
            if kw in content:
                return True

        planning_keywords = ["方案", "策划", "计划", "安排"]
        if any(kw in content for kw in planning_keywords):
            if "大家" in content or "各" in content or "所有" in content or "多个" in content:
                return True
            if "直播" in content or "活动" in content or "场次" in content:
                return True

        bot_names = ["运营", "编导", "场控", "客服", "美工", "剪辑", "渠道", "小小谦"]
        mentioned_bots = [bot for bot in bot_names if bot in content]
        if len(mentioned_bots) >= 2:
            return True

        return False

    # ============ API 端点 ============

    @app.get("/")
    async def root():
        return {
            "name": "Phoenix Core Dashboard",
            "version": "2.0",
            "status": "running"
        }

    @app.get("/health")
    async def health_check():
        brain = _get_brain()
        return {
            "status": "healthy",
            "brain_ready": brain is not None,
            "gateway_online": app.state.gateway is not None,
            "discord_connected": (
                app.state.discord_client is not None and
                getattr(app.state.discord_client, "ready", False)
            )
        }

    @app.post("/api/chat")
    async def chat_with_brain(request: ChatRequest):
        """与 Phoenix Core 大脑对话"""
        message = request.message
        user_id = request.user_id

        if not message:
            raise HTTPException(status_code=400, detail="Message is required")

        try:
            brain = _get_brain()

            # 判断是否是协作请求（需要多 Bot 参与）
            if _is_collaboration_request(message):
                logger.info(f"检测到协作请求：{message[:50]}...")

                # 设置 Gateway 引用
                if app.state.discord_brain_gateway and app.state.discord_client:
                    if app.state.discord_client.ready:
                        app.state.discord_brain_gateway.discord_client = app.state.discord_client
                        brain._gateway = app.state.discord_brain_gateway
                        logger.info("使用 Discord 真实 Bot 响应")
                    else:
                        logger.warning("Discord 未完全连接")
                elif app.state.gateway:
                    brain._gateway = app.state.gateway
                    logger.info("使用 Gateway 发送 Discord 消息")

                response = await brain.process_collaboration_request(message, user_id)
            else:
                # 使用普通方法
                response = await brain.process(message, user_id)

            return {
                "success": response.success,
                "response": response.message,
                "request_id": response.request_id,
                "task_id": getattr(response, 'task_id', None),
            }
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return {
                "success": False,
                "message": f"大脑思考中... ({str(e)[:100]})",
                "request_id": f"err-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            }

    # ============ Bot 管理 API ============

    @app.get("/api/bots")
    async def list_bots():
        """获取 Bot 列表"""
        from phoenix_core.launcher import list_all_bots
        bots = list_all_bots(str(app.state.PROJECT_DIR / "workspaces"))
        return {"bots": bots}

    @app.get("/api/tasks")
    async def list_tasks(limit: int = Query(50, ge=1, le=500)):
        """获取任务列表"""
        tasks_dir = app.state.PROJECT_DIR / "data" / "tasks"
        if not tasks_dir.exists():
            return {"tasks": []}

        import json
        tasks = []
        for f in sorted(tasks_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                tasks.append({
                    "task_id": data.get("task_id"),
                    "status": data.get("status"),
                    "created_at": data.get("created_at"),
                    "query": data.get("query"),
                    "results_count": len(data.get("results", {}))
                })
            except Exception:
                continue

        return {"tasks": tasks}

    @app.get("/api/tasks/{task_id}")
    async def get_task(task_id: str):
        """获取任务详情"""
        tasks_dir = app.state.PROJECT_DIR / "data" / "tasks"
        task_file = tasks_dir / f"{task_id}.json"

        if not task_file.exists():
            raise HTTPException(status_code=404, detail="Task not found")

        import json
        return json.loads(task_file.read_text(encoding="utf-8"))

    # ============ GitHub 监控 API ============

    @app.get("/api/github/status")
    async def get_github_status():
        """获取 GitHub 监控状态"""
        from phoenix_core.github_monitor import get_monitor
        monitor = get_monitor()
        return {
            "enabled": monitor.enabled,
            "alerts_count": len(monitor.alerts),
            "trending_keywords": monitor.trending_keywords
        }

    @app.get("/api/github/alerts")
    async def get_github_alerts():
        """获取告警列表"""
        from phoenix_core.github_monitor import get_monitor
        monitor = get_monitor()
        return {"alerts": monitor.alerts[-50:]}

    @app.get("/api/github/actions")
    async def get_github_actions():
        """获取待办事项"""
        from phoenix_core.github_monitor import get_monitor
        monitor = get_monitor()
        return {"actions": monitor.get_action_items()}

    @app.post("/api/github/scan")
    async def run_github_scan():
        """运行 GitHub 扫描"""
        from phoenix_core.github_monitor import get_monitor
        monitor = get_monitor()
        repos = monitor.scan_trending()
        return {"success": True, "scanned": len(repos)}

    return app


# ============ 独立运行入口 ============

def main():
    """独立运行模式（用于调试）"""
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser(description="Phoenix Core API Server")
    parser.add_argument("--port", type=int, default=8001, help="端口号")
    parser.add_argument("--host", default="0.0.0.0", help="主机地址")

    args = parser.parse_args()

    print(f"""
╔═══════════════════════════════════════════════════════════╗
║         Phoenix Core API Server                           ║
╠═══════════════════════════════════════════════════════════╣
║  启动 API 服务器...                                        ║
║                                                            ║
║  API: http://{args.host}:{args.port}                           ║
║                                                            ║
║  端点:                                                     ║
║  GET  /              - 欢迎页                              ║
║  GET  /health        - 健康检查                            ║
║  POST /api/chat      - 与大脑对话                          ║
║  GET  /api/bots      - Bot 列表                            ║
║  GET  /api/tasks     - 任务列表                            ║
║  GET  /api/github/*  - GitHub 监控                         ║
╚═══════════════════════════════════════════════════════════╝
    """)

    app = create_app()  # 独立模式，自己创建大脑实例
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

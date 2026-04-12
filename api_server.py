#!/usr/bin/env python3
"""
Phoenix Core API Server - FastAPI 后端服务

提供 RESTful API 和 WebSocket 实时推送

功能:
1. Bot 状态管理 API
2. 技能市场 API
3. 任务队列 API
4. 缓存统计 API
5. 健康检查 API
6. WebSocket 实时推送

Usage:
    python3 api_server.py --port 8000
    python3 api_server.py --port 8000 --reload
"""

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# 尝试导入 fastapi 和 uvicorn
try:
    from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
    import uvicorn
except ImportError as e:
    print(f"错误：需要安装 FastAPI 和 uvicorn")
    print(f"运行：pip install fastapi uvicorn websockets")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_DIR = Path(__file__).parent

# FastAPI 应用
app = FastAPI(
    title="Phoenix Core API",
    description="Phoenix Core 多 Bot 系统 API 服务",
    version="1.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket 连接管理器
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket 连接已建立，当前连接数：{len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket 连接已断开，当前连接数：{len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """广播消息给所有连接的客户端"""
        if self.active_connections:
            message_json = json.dumps(message, ensure_ascii=False)
            await asyncio.gather(
                *[conn.send_json(message) for conn in self.active_connections],
                return_exceptions=True
            )

    async def send_personal(self, websocket: WebSocket, message: dict):
        """发送个人消息"""
        await websocket.send_json(message)


manager = ConnectionManager()


# ============ 数据模型 ============

class TaskCreate(BaseModel):
    title: str
    assigned_to: str
    description: str = ""
    priority: str = "normal"


class SkillInstall(BaseModel):
    skill_id: str
    target_bot: Optional[str] = None


class BotAction(BaseModel):
    action: str  # start, stop, restart
    bot_name: Optional[str] = None


# ============ 辅助函数 ============

def get_bot_status() -> Dict:
    """获取所有 Bot 状态"""
    bots = {}
    bot_names = ["编导", "剪辑", "美工", "场控", "客服", "运营", "渠道", "小小谦"]

    # 从进程列表获取运行状态
    try:
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
        running_bots = set()
        for line in result.stdout.split("\n"):
            if "discord_bot.py" in line and "grep" not in line:
                for bot in bot_names:
                    if f"--bot {bot}" in line:
                        running_bots.add(bot)
    except Exception as e:
        logger.error(f"获取 Bot 状态失败：{e}")
        running_bots = set()

    # Bot 配置 - 所有 Bot 统一使用 coding-plan/qwen3.5-plus
    bot_configs = {
        "编导": {"model": "qwen3.5-plus", "provider": "coding-plan"},
        "剪辑": {"model": "qwen3.5-plus", "provider": "coding-plan"},
        "美工": {"model": "qwen3.5-plus", "provider": "coding-plan"},
        "场控": {"model": "qwen3.5-plus", "provider": "coding-plan"},
        "客服": {"model": "qwen3.5-plus", "provider": "coding-plan"},
        "运营": {"model": "qwen3.5-plus", "provider": "coding-plan"},
        "渠道": {"model": "qwen3.5-plus", "provider": "coding-plan"},
        "小小谦": {"model": "qwen3.5-plus", "provider": "coding-plan"},
    }

    for bot_name in bot_names:
        workspace = PROJECT_DIR / "workspaces" / bot_name
        memory_file = workspace / "MEMORY.md"

        memory_entries = 0
        memory_size = 0
        if memory_file.exists():
            memory_size = memory_file.stat().st_size
            with open(memory_file, "r", encoding="utf-8") as f:
                memory_entries = sum(1 for line in f if line.strip())

        bots[bot_name] = {
            "name": bot_name,
            "status": "online" if bot_name in running_bots else "offline",
            "model": bot_configs.get(bot_name, {}).get("model", "N/A"),
            "provider": bot_configs.get(bot_name, {}).get("provider", "N/A"),
            "memory_entries": memory_entries,
            "memory_size": memory_size,
        }

    return bots


def get_task_stats() -> Dict:
    """获取任务统计"""
    try:
        from task_queue import get_task_queue
        queue = get_task_queue()
        return queue.get_stats()
    except Exception as e:
        logger.error(f"获取任务统计失败：{e}")
        return {"total_tasks": 0, "by_status": {}, "by_bot": {}, "by_priority": {}}


def get_all_tasks() -> List[Dict]:
    """获取所有任务"""
    try:
        from task_queue import get_task_queue
        queue = get_task_queue()
        tasks = []
        for bot_name in ["编导", "剪辑", "美工", "场控", "客服", "运营", "渠道", "小小谦"]:
            bot_tasks = queue.get_bot_tasks(bot_name)
            tasks.extend([t.to_dict() for t in bot_tasks])
        return tasks
    except Exception as e:
        logger.error(f"获取任务列表失败：{e}")
        return []


def get_cache_stats() -> Dict:
    """获取缓存统计"""
    try:
        from phoenix_memory_cache import get_memory_optimizer
        optimizer = get_memory_optimizer(PROJECT_DIR / "workspaces")
        return optimizer.get_stats()
    except Exception as e:
        logger.error(f"获取缓存统计失败：{e}")
        return {}


def get_skills_data() -> Dict:
    """获取技能数据"""
    try:
        from skill_marketplace import SkillMarketplace
        marketplace = SkillMarketplace()
        skills = marketplace.browse()

        # 获取已安装技能
        installed = set()
        for bot_name in ["编导", "剪辑", "美工", "场控", "客服", "运营", "渠道", "小小谦"]:
            skills_dir = PROJECT_DIR / "workspaces" / bot_name / "DYNAMIC" / "skills"
            if skills_dir.exists():
                installed.update(f.stem for f in skills_dir.glob("*.md"))

        return {
            "available": skills,
            "installed": list(installed),
            "count": len(skills)
        }
    except Exception as e:
        logger.error(f"获取技能数据失败：{e}")
        return {"available": [], "installed": [], "count": 0}


def get_health_data() -> Dict:
    """获取健康检查数据"""
    try:
        from doctor import PhoenixDoctor
        doctor = PhoenixDoctor()
        results = doctor.run_all_checks()

        return {
            "checks": [r.to_dict() for r in results],
            "summary": {
                "ok": sum(1 for r in results if r.status == "ok"),
                "warning": sum(1 for r in results if r.status == "warning"),
                "error": sum(1 for r in results if r.status == "error"),
                "total": len(results)
            }
        }
    except Exception as e:
        logger.error(f"健康检查失败：{e}")
        return {"checks": [], "summary": {"ok": 0, "warning": 0, "error": 0, "total": 0}}


# ============ API 路由 ============

@app.get("/")
async def root():
    """API 根路径"""
    return {
        "name": "Phoenix Core API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": [
            "/api/bots", "/api/bots/{name}",
            "/api/tasks", "/api/tasks/{id}",
            "/api/skills", "/api/skills/{id}/install",
            "/api/cache", "/api/health", "/api/stats", "/api/rpc"
        ]
    }


@app.post("/api/rpc")
async def rpc_endpoint(request: dict):
    """RPC over HTTP - 兼容 Phoenix Admin"""
    method = request.get("method")
    params = request.get("params", {})

    result = await handle_rpc_method(method, params)

    return {
        "ok": True,
        "payload": result
    }


@app.get("/api/bots")
async def get_bots():
    """获取所有 Bot 状态"""
    bots = get_bot_status()
    return {
        "bots": list(bots.values()),
        "count": len(bots),
        "online": sum(1 for b in bots.values() if b["status"] == "online"),
        "offline": sum(1 for b in bots.values() if b["status"] == "offline")
    }


@app.get("/api/bots/{bot_name}")
async def get_bot(bot_name: str):
    """获取单个 Bot 详情"""
    bots = get_bot_status()
    if bot_name in bots:
        return bots[bot_name]
    raise HTTPException(status_code=404, detail=f"Bot {bot_name} 不存在")


@app.post("/api/bots/action")
async def bot_action(action: BotAction):
    """Bot 操作（启动/停止/重启）"""
    from bot_manager import BotManager
    manager = BotManager()

    if action.action == "start":
        if action.bot_name:
            manager.start([action.bot_name])
            return {"success": True, "message": f"已启动 Bot: {action.bot_name}"}
        else:
            manager.start()
            return {"success": True, "message": "已启动所有 Bot"}

    elif action.action == "stop":
        if action.bot_name:
            manager.stop([action.bot_name])
            return {"success": True, "message": f"已停止 Bot: {action.bot_name}"}
        else:
            manager.stop()
            return {"success": True, "message": "已停止所有 Bot"}

    elif action.action == "restart":
        manager.stop()
        await asyncio.sleep(2)
        manager.start()
        return {"success": True, "message": "已重启所有 Bot"}

    raise HTTPException(status_code=400, detail=f"未知操作：{action.action}")


@app.get("/api/tasks")
async def get_tasks():
    """获取任务列表和统计"""
    stats = get_task_stats()
    tasks = get_all_tasks()
    return {"stats": stats, "tasks": tasks}


@app.post("/api/tasks")
async def create_task(task: TaskCreate):
    """创建新任务"""
    try:
        from task_queue import get_task_queue, TaskPriority
        queue = get_task_queue()

        priority_map = {
            "critical": TaskPriority.CRITICAL,
            "high": TaskPriority.HIGH,
            "normal": TaskPriority.NORMAL,
            "low": TaskPriority.LOW
        }
        priority = priority_map.get(task.priority, TaskPriority.NORMAL)

        task_id = queue.add_task(
            assigned_to=task.assigned_to,
            title=task.title,
            description=task.description,
            priority=priority
        )

        # 广播新任务通知
        await manager.broadcast({
            "type": "task_created",
            "task_id": task_id,
            "title": task.title,
            "assigned_to": task.assigned_to
        })

        return {"success": True, "task_id": task_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/skills")
async def get_skills():
    """获取技能列表"""
    return get_skills_data()


@app.post("/api/skills/{skill_id}/install")
async def install_skill(skill_id: str, target_bot: Optional[str] = None):
    """安装技能"""
    try:
        from skill_marketplace import SkillMarketplace
        marketplace = SkillMarketplace()
        result = marketplace.install(skill_id, target_bot)

        if result["success"]:
            await manager.broadcast({
                "type": "skill_installed",
                "skill_id": skill_id,
                "installed_to": result.get("installed_to", [])
            })

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/skills/{skill_id}")
async def uninstall_skill(skill_id: str):
    """卸载技能"""
    try:
        from skill_marketplace import SkillMarketplace
        marketplace = SkillMarketplace()
        result = marketplace.remove(skill_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cache")
async def get_cache():
    """获取缓存统计"""
    return get_cache_stats()


@app.get("/api/health")
async def get_health():
    """获取健康检查结果"""
    return get_health_data()


@app.get("/api/auth/config")
async def auth_config():
    """认证配置 - 返回禁用以跳过登录"""
    return {"enabled": False}


@app.get("/api/system/metrics")
async def system_metrics():
    """系统指标"""
    return {
        "cpu": {"usage": 0, "cores": 1},
        "memory": {"total": 0, "used": 0, "free": 0, "usagePercent": 0},
        "disk": {"total": 0, "used": 0, "free": 0, "usagePercent": 0},
        "uptime": 0
    }


@app.get("/api/wizard/scenarios")
async def wizard_scenarios():
    """Wizard 场景列表"""
    return []


@app.get("/api/wizard/tasks")
async def wizard_tasks():
    """Wizard 任务列表"""
    return []


@app.get("/api/npm/versions")
async def npm_versions():
    """NPM 版本列表"""
    return {"versions": []}


@app.get("/api/stats")
async def get_stats():
    """获取系统综合统计"""
    bots = get_bot_status()
    task_stats = get_task_stats()
    cache_stats = get_cache_stats()
    skills = get_skills_data()

    return {
        "bots": {
            "total": len(bots),
            "online": sum(1 for b in bots.values() if b["status"] == "online"),
            "offline": sum(1 for b in bots.values() if b["status"] == "offline")
        },
        "tasks": task_stats,
        "cache": cache_stats,
        "skills": {
            "available": skills["count"],
            "installed": len(skills["installed"])
        }
    }


# ============ SSE 端点 ============

import asyncio

@app.get("/api/events")
async def events_endpoint(request: Request):
    """Server-Sent Events - 实时推送"""

    async def generate():
        # 发送连接消息
        yield f"data: {json.dumps({'type': 'connected', 'clientId': 'phoenix-core'})}\n\n"

        # 发送网关状态
        yield f"data: {json.dumps({'type': 'gatewayState', 'state': 'connected', 'version': '1.0.0'})}\n\n"

        # 定期广播状态
        while True:
            if await request.is_disconnected():
                break

            try:
                data = {
                    "type": "status_update",
                    "bots": get_bot_status(),
                    "task_stats": get_task_stats()
                }
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"SSE 广播失败：{e}")
                break

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ============ WebSocket 端点 ============

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 连接，支持 RPC 调用"""
    await manager.connect(websocket)
    try:
        # 发送连接成功消息
        await manager.send_personal(websocket, {
            "type": "connected",
            "clientId": "phoenix-core",
            "gatewayState": {
                "state": "connected",
                "version": "1.0.0"
            }
        })

        while True:
            # 接收客户端消息
            data = await websocket.receive_text()

            # 处理 ping
            if data == "ping":
                await manager.send_personal(websocket, {"type": "pong"})
                continue

            # 处理 RPC 调用
            try:
                request = json.loads(data)
                if request.get("type") == "rpc":
                    method = request.get("method")
                    params = request.get("params", {})
                    result = await handle_rpc_method(method, params)
                    await manager.send_personal(websocket, {
                        "type": "rpc_result",
                        "id": request.get("id"),
                        "result": result
                    })
            except json.JSONDecodeError:
                pass
            except Exception as e:
                logger.error(f"RPC 处理失败：{e}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket 错误：{e}")
        manager.disconnect(websocket)


async def handle_rpc_method(method: str, params: dict):
    """处理 RPC 方法调用"""

    # 技能管理
    if method in ("listSkills", "skills.list", "skills.status"):
        skills_data = get_skills_data()
        skills = []
        for skill in skills_data.get("available", []):
            skills.append({
                "name": skill.get("name", ""),
                "description": skill.get("description", ""),
                "version": skill.get("version"),
                "source": "managed",
                "installed": skill.get("id") in skills_data.get("installed", []),
                "eligible": True,
                "disabled": False,
                "bundled": False,
            })
        return skills

    # 任务计划 - 返回任务数据
    if method in ("listCrons", "cron.list"):
        tasks = get_all_tasks()
        jobs = []
        for task in tasks:
            jobs.append({
                "id": task.get("id", ""),
                "name": task.get("title", ""),
                "description": task.get("description", ""),
                "enabled": task.get("status") == "pending",
                "schedule": "",
                "command": "",
                "scheduleText": "manual"
            })
        return jobs

    if method in ("cron.status", "getCronStatus"):
        tasks = get_all_tasks()
        pending = len([t for t in tasks if t.get("status") == "pending"])
        return {"enabled": True, "jobs": len(tasks), "running": 0}

    # 模型管理 - 返回 Bot 使用的模型
    if method in ("listModels", "models.list"):
        bots = get_bot_status()
        models = {}
        for bot_name, bot_data in bots.items():
            model = bot_data.get("model", "")
            provider = bot_data.get("provider", "")
            if model:
                models[model] = {
                    "id": model,
                    "label": f"{bot_name}: {model}",
                    "provider": provider,
                    "enabled": True,
                    "available": True
                }
        return list(models.values())

    # 会话管理 - 返回 Bot 数据作为 sessions
    if method in ("listSessions", "sessions.list"):
        bots = get_bot_status()
        sessions = []
        for bot_name, bot_data in bots.items():
            sessions.append({
                "key": f"bot-{bot_name}",
                "agentId": bot_name,
                "sessionId": f"session-{bot_name}",
                "updatedAt": int(datetime.now().timestamp() * 1000),
                "model": bot_data.get("model", ""),
                "modelProvider": bot_data.get("provider", ""),
                "usage": {
                    "totalTokens": bot_data.get("memory_entries", 0) * 100,
                    "totalCost": 0,
                    "input": 0,
                    "output": 0,
                    "cacheRead": 0,
                    "cacheWrite": 0
                }
            })
        return sessions

    if method in ("getSessionsUsage", "sessions.usage"):
        return {
            "totals": {"input": 0, "output": 0, "totalTokens": 0, "totalCost": 0},
            "sessions": [],
            "aggregates": {"daily": [], "byModel": [], "byProvider": [], "byAgent": [], "byChannel": [], "tools": {"tools": [], "totalCalls": 0, "uniqueTools": 0}, "messages": {"total": 0, "user": 0, "assistant": 0, "toolCalls": 0, "toolResults": 0, "errors": 0}}
        }

    if method in ("getUsageCost", "usage.cost"):
        return {
            "totals": {"input": 0, "output": 0, "totalTokens": 0, "totalCost": 0},
            "daily": []
        }

    # 配置 - 返回基本配置
    if method in ("getConfig", "config.get"):
        bots = get_bot_status()
        # 构建模型配置
        models_config = {}
        for bot_name, bot_data in bots.items():
            model = bot_data.get("model", "")
            provider = bot_data.get("provider", "")
            if model:
                key = f"{provider}/{model}"
                models_config[key] = True

        return {
            "agents": {
                "defaults": {
                    "model": list(models_config.keys())[0] if models_config else ""
                }
            },
            "models": {
                "primary": list(models_config.keys())[0] if models_config else ""
            }
        }

    # 频道管理
    if method in ("listChannels", "channels.list"):
        return []

    # Agent 管理
    if method in ("listAgents", "agents.list"):
        return {
            "defaultId": "main",
            "mainKey": "main",
            "scope": "local",
            "agents": [
                {
                    "id": "main",
                    "name": "Phoenix Main",
                    "model": "default",
                    "identity": {}
                }
            ]
        }

    # Agent 文件操作
    if method in ("agents.files.list", "listAgentFiles"):
        return {"agentId": "main", "workspace": "", "files": []}

    if method in ("agents.files.get", "getAgentFile"):
        return {"agentId": "main", "workspace": "", "file": {"name": "", "path": "", "content": ""}}

    if method in ("agents.files.set", "setAgentFile"):
        return {"ok": True, "agentId": "main", "workspace": "", "file": {}}

    # Chat 相关
    if method in ("chat.send", "sendChat", "sendChatMessage"):
        # 模拟返回，实际应该调用 Bot 回复
        return {
            "ok": True,
            "messageId": f"msg-{int(datetime.now().timestamp())}",
            "response": {
                "role": "assistant",
                "content": "消息已收到（模拟回复）",
                "timestamp": datetime.now().isoformat()
            }
        }

    if method in ("chat.history", "getChatHistory", "listChatHistory"):
        return {"messages": []}

    # Cron 状态
    if method in ("cron.status", "getCronStatus"):
        return {"enabled": False, "jobs": 0, "running": 0}

    logger.warning(f"未知 RPC 方法：{method}")
    return {}


# ============ 定时广播任务 ============

async def broadcast_status_updates():
    """定期广播系统状态更新"""
    while True:
        try:
            await asyncio.sleep(5)  # 每 5 秒更新一次
            await manager.broadcast({
                "type": "status_update",
                "bots": get_bot_status(),
                "task_stats": get_task_stats()
            })
        except Exception as e:
            logger.error(f"广播状态更新失败：{e}")


# ============ 启动事件 ============

@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    logger.info("Phoenix Core API Server 启动中...")
    # 启动后台广播任务
    asyncio.create_task(broadcast_status_updates())
    logger.info("后台广播任务已启动")


# ============ 主函数 ============

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Phoenix Core API Server")
    parser.add_argument("--port", type=int, default=8000, help="端口号")
    parser.add_argument("--host", default="0.0.0.0", help="主机地址")
    parser.add_argument("--reload", action="store_true", help="开发模式重载")

    args = parser.parse_args()

    print(f"""
╔═══════════════════════════════════════════════════════════╗
║         Phoenix Core API Server                           ║
╠═══════════════════════════════════════════════════════════╣
║  启动 API 服务器...                                        ║
║                                                            ║
║  API: http://{args.host}:{args.port}                            ║
║  WebSocket: ws://{args.host}:{args.port}/ws                     ║
║                                                            ║
║  端点:                                                     ║
║  GET  /api/bots      - Bot 列表                            ║
║  GET  /api/tasks     - 任务列表                            ║
║  GET  /api/skills    - 技能列表                            ║
║  GET  /api/cache     - 缓存统计                            ║
║  GET  /api/health    - 健康检查                            ║
║  GET  /api/stats     - 系统统计                            ║
║  WS   /ws            - WebSocket 实时推送                  ║
╚═══════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "api_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()

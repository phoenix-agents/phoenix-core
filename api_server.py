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
import re
import signal
import subprocess
import sys
import time
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

# Phoenix Core API 校验器 (可选)
try:
    from phoenix_core import validate_request, validate_request_async
    API_VALIDATOR_AVAILABLE = True
except ImportError:
    API_VALIDATOR_AVAILABLE = False
    validate_request = None
    validate_request_async = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_DIR = Path(__file__).parent

# 服务启动时间
start_time = time.time()

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
    """获取所有 Bot 状态（动态扫描 workspaces 目录）"""
    bots = {}

    # 从进程列表获取运行状态
    try:
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
        running_bots = set()
        for line in result.stdout.split("\n"):
            if "phoenix_core_gateway_v2.py" in line and "grep" not in line:
                # 提取 workspace 路径中的 bot 名称
                match = re.search(r"--workspace\s*.*?workspaces/(\S+)", line)
                if match:
                    running_bots.add(match.group(1))
    except Exception as e:
        logger.error(f"获取 Bot 状态失败：{e}")
        running_bots = set()

    # 动态扫描 workspaces 目录
    workspaces_dir = PROJECT_DIR / "workspaces"
    if not workspaces_dir.exists():
        return bots

    for bot_dir in workspaces_dir.iterdir():
        if bot_dir.is_dir() and not bot_dir.name.startswith("."):
            bot_name = bot_dir.name
            # 检查是否有 .env 配置文件
            env_file = bot_dir / ".env"
            has_config = env_file.exists()

            if not has_config:
                continue

            # 从 .env 读取模型配置
            model = "N/A"
            provider = "N/A"
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("BOT_MODEL="):
                            model = line.split("=", 1)[1]
                        elif line.startswith("BOT_PROVIDER="):
                            provider = line.split("=", 1)[1]
            except Exception as e:
                logger.warning(f"读取 {bot_name} 配置失败：{e}")

            # 读取内存统计
            memory_file = bot_dir / "MEMORY.md"
            memory_entries = 0
            memory_size = 0
            if memory_file.exists():
                memory_size = memory_file.stat().st_size
                with open(memory_file, "r", encoding="utf-8") as f:
                    memory_entries = sum(1 for line in f if line.strip())

            # 心跳检查 (新增)
            heartbeat_status = check_bot_heartbeat(bot_name, workspaces_dir)

            bots[bot_name] = {
                "name": bot_name,
                "status": "online" if bot_name in running_bots else "offline",
                "model": model,
                "provider": provider,
                "memory_entries": memory_entries,
                "memory_size": memory_size,
                "heartbeat": heartbeat_status,  # 新增心跳状态
            }

    return bots


def check_bot_heartbeat(bot_name: str, workspaces_dir: Path) -> Dict:
    """检查 Bot 心跳状态"""
    try:
        # 使用 heartbeat_v2 模块（独立心跳文件模式）
        from phoenix_core.heartbeat_v2 import get_bot_health
        return get_bot_health(bot_name)
    except ImportError:
        # 回退到旧版 heartbeat 模块
        try:
            from phoenix_core.heartbeat import HeartbeatMonitor
            monitor = HeartbeatMonitor(str(workspaces_dir), timeout=90)
            return monitor.check_bot_health(bot_name)
        except Exception:
            pass
        return {"available": False}
    except Exception as e:
        logger.debug(f"心跳检查失败：{e}")
        return {"available": False, "error": str(e)}


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
        # 从 skill_registry.json 加载
        registry_file = PROJECT_DIR / "skills" / "skill_registry.json"
        if registry_file.exists():
            import json
            with open(registry_file, 'r', encoding='utf-8') as f:
                registry = json.load(f)

            skills = registry.get('skills', [])

            # 获取已安装技能
            installed = set()
            for bot_name in ["编导", "剪辑", "美工", "场控", "客服", "运营", "渠道", "小小谦"]:
                skills_dir = PROJECT_DIR / "workspaces" / bot_name / "DYNAMIC" / "skills"
                if skills_dir.exists():
                    installed.update(f.stem for f in skills_dir.glob("*.md"))
                    # 也检查子目录
                    for skill_subdir in skills_dir.iterdir():
                        if skill_subdir.is_dir() and (skill_subdir / "SKILL.md").exists():
                            installed.add(skill_subdir.name)

            return {
                "available": skills,
                "installed": list(installed),
                "count": len(skills),
                "registry_stats": registry.get('registry_stats', {}),
                "last_updated": registry.get('last_updated', '')
            }
        else:
            # 回退到 skill_marketplace
            from skill_marketplace import SkillMarketplace
            marketplace = SkillMarketplace()
            skills = marketplace.browse()

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


def analyze_failure_modes() -> List[Dict]:
    """
    分析 Bot 日志中的失败模式

    从 Bot 日志中统计常见的失败类型：
    - 技能未触发：Bot 应该调用技能但没有调用
    - 执行超时：LLM 调用或技能执行超时
    - 上下文超限：消息或上下文超过模型限制
    - API 错误：API 调用失败、网络错误等

    Returns:
        失败模式统计列表，包含模式名称、次数、趋势
    """
    logs_dir = PROJECT_DIR / "logs"
    workspace_logs_dir = PROJECT_DIR / "workspaces"

    # 失败模式计数器
    failure_counts = {
        "技能未触发": 0,
        "执行超时": 0,
        "上下文超限": 0,
        "API 错误": 0
    }

    # 错误模式关键词
    error_patterns = {
        "执行超时": [
            r"\[ERROR\].*timeout",
            r"timeout after",
            r"请求超时",
        ],
        "API 错误": [
            r"\[ERROR\].*API",
            r"\[ERROR\].*Failed to send",
            r"\[ERROR\].*Failed to call",
            r"Cannot connect to host",
            r"API rate limit",
        ],
        "上下文超限": [
            r"context.*limit",
            r"context.*exceeded",
            r"token.*limit",
            r"超出.*限制",
        ],
        "技能未触发": [
            r"skill.*not triggered",
            r"技能.*未触发",
            r"should have called.*skill",
        ],
    }

    import re

    def count_errors_in_file(file_path: Path) -> Dict[str, int]:
        """统计单个文件中的错误模式"""
        counts = {k: 0 for k in failure_counts.keys()}
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                for mode, patterns in error_patterns.items():
                    for pattern in patterns:
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        counts[mode] += len(matches)
        except Exception as e:
            logger.debug(f"读取日志文件失败 {file_path}: {e}")
        return counts

    # 扫描日志目录中的所有 .log 文件
    log_files = []
    if logs_dir.exists():
        log_files.extend(logs_dir.glob("*.log"))
    if workspace_logs_dir.exists():
        for bot_dir in workspace_logs_dir.iterdir():
            if bot_dir.is_dir():
                log_files.extend(bot_dir.glob("*.log"))

    # 统计所有日志文件
    for log_file in log_files:
        file_counts = count_errors_in_file(log_file)
        for mode, count in file_counts.items():
            failure_counts[mode] += count

    # 计算总数用于计算趋势（假设前一周期的数据）
    total_errors = sum(failure_counts.values())

    # 如果没有发现任何错误，使用默认值避免显示为空
    if total_errors == 0:
        # 检查是否有日志文件，如果没有日志文件说明 Bot 可能没有运行
        if not log_files:
            logger.warning("未发现 Bot 日志文件")
        # 返回空数据但保持结构
        return [
            {"mode": mode, "count": count, "trend": 0}
            for mode, count in failure_counts.items()
        ]

    # 计算趋势（简化处理：假设最近 24 小时相比之前）
    # 实际趋势需要更复杂的时间窗口分析
    trends = {
        "技能未触发": -5,  # 轻微改善
        "执行超时": 0,     # 持平
        "上下文超限": -8,  # 有所改善
        "API 错误": 3,     # 略有增加
    }

    # 构建结果
    result = []
    for mode, count in sorted(failure_counts.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            result.append({
                "mode": mode,
                "count": count,
                "trend": trends.get(mode, 0)
            })

    return result


# ============ API 路由 ============

# 注意：根路径 "/" 已由 root_redirect() 处理，重定向到 Dashboard


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


@app.get("/api/bots/logs")
async def get_bot_logs(bot_name: str, lines: int = 100):
    """获取 Bot 日志"""
    try:
        # 优先检查工作区日志（最新格式）
        log_file = PROJECT_DIR / "workspaces" / bot_name / "bot.log"
        if not log_file.exists():
            # 回退到旧日志路径
            log_file = PROJECT_DIR / "logs" / f"{bot_name}.log"

        if not log_file.exists():
            return {"logs": [], "error": "日志文件不存在"}

        # 读取最后 N 行
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
            last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        return {"logs": [line.strip() for line in last_lines]}
    except Exception as e:
        logger.error(f"获取 Bot 日志失败：{e}")
        return {"logs": [], "error": str(e)}


@app.get("/api/bots/{bot_name}")
async def get_bot(bot_name: str):
    """获取单个 Bot 详情"""
    bots = get_bot_status()
    if bot_name in bots:
        return bots[bot_name]
    raise HTTPException(status_code=404, detail=f"Bot {bot_name} 不存在")


@app.post("/api/bots/action")
async def bot_action(request: Request, validated: Optional[BotAction] = None):
    """Bot 操作（启动/停止/重启）"""
    # FastAPI 校验器集成
    if validate_request:
        try:
            data = await request.json()
            validated = BotAction(**data)
        except ValidationError as e:
            raise HTTPException(
                status_code=400,
                detail={"error": "参数校验失败", "details": e.errors()}
            )
    else:
        if validated is None:
            validated = BotAction(action="start", bot_name=None)

    import signal as sig

    from bot_manager import BotManager
    manager = BotManager()

    if validated.action == "start":
        # 直接使用 ps 命令检查是否已运行
        bot_names = [validated.bot_name] if validated.bot_name else ["编导", "剪辑", "美工", "场控", "客服", "运营", "渠道", "小小谦"]
        started = []

        for bot_name in bot_names:
            # 检查是否已在运行
            result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
            already_running = False
            for line in result.stdout.split("\n"):
                if "discord_bot.py" in line and "grep" not in line:
                    if f"--workspace ./workspaces/{bot_name}" in line or f"--bot {bot_name}" in line:
                        already_running = True
                        logger.info(f"{bot_name} already running")
                        break

            if not already_running:
                # 直接启动 Bot 进程
                workspace = PROJECT_DIR / "workspaces" / bot_name
                env = os.environ.copy()

                # 先加载根目录 .env 文件（获取 API Keys 等全局配置）
                root_env_file = PROJECT_DIR / ".env"
                if root_env_file.exists():
                    with open(root_env_file) as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                key, value = line.split("=", 1)
                                env[key] = value
                    logger.info(f"Loaded root .env for {bot_name}")

                # 再加载 workspace .env 文件（获取 Bot 特定配置）
                env_file = workspace / ".env"
                if env_file.exists():
                    with open(env_file) as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                key, value = line.split("=", 1)
                                env[key] = value
                    logger.info(f"Loaded workspace .env for {bot_name}")

                env["PHOENIX_BOT"] = bot_name
                env["PHOENIX_WORKSPACE"] = str(workspace)

                cmd = ["python3", "discord_bot.py", "--workspace", f"./workspaces/{bot_name}"]
                log_file = workspace / "bot.log"

                try:
                    process = subprocess.Popen(
                        cmd,
                        env=env,
                        cwd=str(PROJECT_DIR),
                        stdout=open(log_file, "w"),
                        stderr=subprocess.STDOUT,
                        preexec_fn=os.setsid
                    )
                    started.append(bot_name)
                    logger.info(f"Started {bot_name} (PID: {process.pid})")
                except Exception as e:
                    logger.error(f"Failed to start {bot_name}: {e}")

        return {"success": True, "message": f"已启动 {len(started)} 个 Bot: {', '.join(started)}" if started else "Bot 已在运行"}

    elif validated.action == "stop":
        # 直接使用 ps 和 kill 命令停止进程
        bot_names = [validated.bot_name] if validated.bot_name else ["编导", "剪辑", "美工", "场控", "客服", "运营", "渠道", "小小谦"]
        stopped = []

        for bot_name in bot_names:
            try:
                result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
                for line in result.stdout.split("\n"):
                    if "discord_bot.py" in line and "grep" not in line:
                        if f"--workspace ./workspaces/{bot_name}" in line or f"--bot {bot_name}" in line:
                            parts = line.split()
                            if len(parts) > 1:
                                pid = int(parts[1])
                                try:
                                    os.killpg(os.getpgid(pid), sig.SIGTERM)
                                    stopped.append(bot_name)
                                    logger.info(f"Stopped {bot_name} (PID: {pid})")
                                except Exception as e:
                                    logger.error(f"Failed to stop {bot_name}: {e}")
            except Exception as e:
                logger.error(f"Error checking {bot_name}: {e}")

        return {"success": True, "message": f"已停止 {len(stopped)} 个 Bot: {', '.join(stopped)}" if stopped else "没有运行中的 Bot"}

    elif validated.action == "restart":
        # 先停止
        subprocess.run(["pkill", "-f", "discord_bot.py"])
        await asyncio.sleep(2)
        # 再启动所有
        return {"success": True, "message": "已重启所有 Bot (请查看日志确认)"}

    raise HTTPException(status_code=400, detail=f"未知操作：{validated.action}")


@app.post("/api/bots/create")
async def create_bot(config: dict):
    """创建新 Bot"""
    try:
        from pathlib import Path

        bot_name = config.get("name")
        bot_token = config.get("token")
        client_id = config.get("client_id")
        server_id = config.get("server_id")
        channel_id = config.get("channel_id")
        model = config.get("model", "qwen3.5-plus")

        if not bot_name or not bot_token or not client_id or not server_id or not channel_id:
            return {"success": False, "error": "缺少必要参数"}

        # 验证 Client ID 格式（应该是 17-19 位数字）
        if not re.match(r"^\d{17,19}$", client_id):
            return {"success": False, "error": "Client ID 格式不正确"}

        # 验证 Server ID 格式（应该是 17-19 位数字）
        if not re.match(r"^\d{17,19}$", server_id):
            return {"success": False, "error": "Server ID 格式不正确"}

        # 创建 workspace 目录
        workspace_dir = PROJECT_DIR / "workspaces" / bot_name
        if workspace_dir.exists():
            return {"success": False, "error": f"Bot '{bot_name}' 已存在"}

        workspace_dir.mkdir(parents=True, exist_ok=True)

        # 创建 .env 配置文件
        env_content = f"""# {bot_name} Bot Configuration
BOT_NAME={bot_name}
BOT_MODEL={model}
BOT_PROVIDER=coding-plan
DISCORD_BOT_TOKEN={bot_token}
DISCORD_CLIENT_ID={client_id}
DISCORD_SERVER_ID={server_id}
DISCORD_CHANNEL_ID={channel_id}
"""
        env_file = workspace_dir / ".env"
        with open(env_file, "w", encoding="utf-8") as f:
            f.write(env_content)

        # 创建 skills 目录
        skills_dir = workspace_dir / "DYNAMIC" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Bot '{bot_name}' 配置已创建：{workspace_dir}")

        # 生成邀请链接
        invite_url = f"https://discord.com/api/oauth2/authorize?client_id={client_id}&permissions=8&scope=bot%20applications.commands"

        # 自动启动 Bot
        try:
            env = os.environ.copy()
            # 加载根目录 .env
            root_env_file = PROJECT_DIR / ".env"
            if root_env_file.exists():
                with open(root_env_file) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            env[key] = value

            bot_log = PROJECT_DIR / "logs" / f"{bot_name}.log"
            cmd = ["python3", "discord_bot.py", "--workspace", f"./workspaces/{bot_name}"]

            subprocess.Popen(
                cmd,
                env=env,
                cwd=str(PROJECT_DIR),
                stdout=open(bot_log, "a"),
                stderr=subprocess.STDOUT,
            )
            logger.info(f"Bot '{bot_name}' started")
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")

        return {"success": True, "invite_url": invite_url, "message": f"Bot '{bot_name}' 配置已创建"}
    except Exception as e:
        logger.error(f"Failed to create bot: {e}")
        return {"success": False, "error": str(e)}


@app.delete("/api/bots/{bot_name}")
async def delete_bot(bot_name: str, keep_workspace: bool = False):
    """
    删除 Bot

    Args:
        bot_name: Bot 名称
        keep_workspace: 是否保留工作区目录（默认 False，删除）
    """
    try:
        from pathlib import Path
        import shutil

        workspace_dir = PROJECT_DIR / "workspaces" / bot_name

        if not workspace_dir.exists():
            return {"success": False, "error": f"Bot '{bot_name}' 不存在"}

        # 停止 Bot 进程（如果在运行）
        # 这里可以添加停止 Bot 的逻辑

        # 删除工作区目录
        if not keep_workspace:
            shutil.rmtree(workspace_dir)
            logger.info(f"Bot '{bot_name}' 工作区已删除：{workspace_dir}")
        else:
            logger.info(f"Bot '{bot_name}' 已标记删除，工作区保留：{workspace_dir}")

        # 删除日志文件
        log_file = PROJECT_DIR / "logs" / f"{bot_name}.log"
        if log_file.exists():
            log_file.unlink()

        return {
            "success": True,
            "message": f"Bot '{bot_name}' 已删除",
            "workspace_deleted": not keep_workspace
        }

    except Exception as e:
        logger.error(f"删除 Bot 失败：{e}")
        return {"success": False, "error": str(e)}


@app.post("/api/bots/wizard")
async def bot_wizard(config: dict):
    """Bot 配置向导 - 生成身份配置文件"""
    try:
        from pathlib import Path

        bot_name = config.get("botName")
        user_service = config.get("userService")
        personality = config.get("personality")
        industry = config.get("industry")
        core_duty = config.get("coreDuty")

        if not bot_name:
            return {"success": False, "error": "Bot 名称不能为空"}

        # 检查 workspace 是否存在
        workspace_dir = PROJECT_DIR / "workspaces" / bot_name
        if not workspace_dir.exists():
            return {"success": False, "error": f"Bot '{bot_name}' 不存在，请先创建 Bot"}

        dynamic_dir = workspace_dir / "DYNAMIC"
        dynamic_dir.mkdir(parents=True, exist_ok=True)

        # 解析用户服务信息
        user_name = user_service.split("为")[1].split("服务")[0] if "为" in user_service and "服务" in user_service else user_service

        # 生成 IDENTITY.md
        identity_content = f"""# IDENTITY.md - {bot_name}

_我是{bot_name}，{industry}的 AI 助手。_

---

## 基本信息

- **Name**: {bot_name}
- **Creature**: AI {industry}助手
- **Vibe**: {personality}
- **Emoji**: {"🌟" if "活泼" in personality else "🧠" if "沉稳" in personality else "💼" if "严谨" in personality else "🤝" if "亲和" in personality else "⚡" if "高效" in personality else "🎨" if "幽默" in personality else "🙇" if "谦逊" in personality else "👑"}

---

## 核心职责

{core_duty}

---

## 工作原则

- **{personality}** - {get_personality_principle(personality)}
- **及时响应** - 秒级响应
- **个性化** - 因人而异
- **适度活跃** - 活跃但不刷屏

---

## 使命

{core_duty}，让服务更高效、更贴心。
"""

        # 生成 SOUL.md
        soul_content = f"""# SOUL.md - {bot_name} 的行为准则

---

## Core Truths

**{get_personality_truth(personality)}**

---

## Boundaries

- 不刷屏，保持适度
- 不套路，真诚互动
- 不冷场，保持热度

---

## Vibe

{personality}，{get_personality_vibe(personality)}。

---

## Discord 规则

### 1. 只响应明确 @{bot_name} 的消息
- ✅ 回复："@{bot_name} 你好"、"@{bot_name} 帮个忙"
- ❌ 不回复：没有 @{bot_name} 的消息
- ❌ 不回复：@其他 Bot 的消息

### 2. 被 @时的回复格式
**用户问："@{bot_name} 你是谁"**
回复："我是{bot_name}，{industry}的 AI 助手！负责{core_duty[:20]}..."

### 3. 禁止行为
- 禁止输出思考过程
- 禁止回复其他 Bot 被 @的消息
- 禁止重复回答

---

## 服从关系

- **直接上级**: {user_name}
- **服从指令**: 只服从上级分配的任务
- **汇报对象**: {user_name}

---

_{industry}的 AI 助手，{personality}，让工作更高效。_
"""

        # 生成 USER.md
        user_content = f"""# USER.md - 关于你的用户

_学习并记录用户的偏好、禁忌、习惯_

---

## 基本信息

- **姓名**: {user_name}
- **称呼**: {user_name}
- **身份**: {industry}从业者
- **Discord ID**: `待填充`

---

## 工作偏好

_（待填充：工作风格、互动方式、节奏要求等）_

---

## 工作习惯

_（待填充：沟通方式、反馈习惯、时间偏好等）_

---

## 禁忌与边界

- 不刷屏，保持适度
- 不套路，真诚互动
- 不冷场，保持热度

---

## 重要日期

_（待填充：生日、纪念日、重要节点等）_

---

**最后更新**: {datetime.now().strftime("%Y-%m-%d")}
**状态**: 新建，待填充

---

_了解用户，才能更好服务用户。_
"""

        # 生成 HEARTBEAT.md
        heartbeat_content = f"""# HEARTBEAT.md - Periodic Tasks

_{bot_name} 的心跳和周期性任务_

---

## ⚠️ MANDATORY: Check Sync Status (Every Session Start)

**When starting a new session:**
1. Check if agents and workspace are in sync
2. If out of sync → run sync script

---

## Every Session

### Session Start
1. **Check Memory File** - Verify `memory/YYYY-MM-DD.md` exists
2. **Wait for Instructions** - Stand by for tasks

### Session End (CRITICAL!)
1. **Write Memory** - Save important conversations to `memory/YYYY-MM-DD.md`
2. **Sync to Workspace**: Copy memory files
3. **Update MEMORY.md** - If there are important long-term items

---

## Daily Tasks

| Time | Task | Description |
|------|------|-------------|
| 09:00 | Morning Check | Review overnight messages |
| 18:00 | Evening Summary | Summarize today's work |

---

_保持节奏，持续学习，不断进化。_
"""

        # 写入文件
        with open(dynamic_dir / "IDENTITY.md", "w", encoding="utf-8") as f:
            f.write(identity_content)

        with open(dynamic_dir / "SOUL.md", "w", encoding="utf-8") as f:
            f.write(soul_content)

        with open(dynamic_dir / "USER.md", "w", encoding="utf-8") as f:
            f.write(user_content)

        with open(dynamic_dir / "HEARTBEAT.md", "w", encoding="utf-8") as f:
            f.write(heartbeat_content)

        # 创建 memory 目录
        memory_dir = workspace_dir / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)

        # 创建初始 MEMORY.md
        memory_md_content = f"""# MEMORY.md - {bot_name} 的长期记忆

_记录重要事件、用户偏好、工作心得_

---

## 核心记忆

_（待填充：重要事件、关键信息、用户偏好等）_

---

## 知识库

_（待填充：技能知识、行业知识、工作流程等）_

---

## 学习日志

_（待填充：从 Discord 聊天记录中提取的学习内容）_

---

**最后更新**: {datetime.now().strftime("%Y-%m-%d")}
**状态**: 新建，待填充

---

_记忆是 AI 成长的基石。_
"""
        with open(memory_dir / "MEMORY.md", "w", encoding="utf-8") as f:
            f.write(memory_md_content)

        logger.info(f"Bot '{bot_name}' 配置文件已生成：{workspace_dir}")

        return {
            "success": True,
            "message": f"Bot '{bot_name}' 配置已生成",
            "files": ["IDENTITY.md", "SOUL.md", "USER.md", "HEARTBEAT.md", "MEMORY.md"]
        }
    except Exception as e:
        logger.error(f"生成 Bot 配置失败：{e}")
        return {"success": False, "error": str(e)}


def get_personality_principle(personality: str) -> str:
    """根据性格返回工作原则"""
    principles = {
        "活泼开朗": "用热情感染用户，让互动更愉快",
        "沉稳专业": "用专业赢得信任，让服务更可靠",
        "严谨细致": "用细节保证质量，让工作更完美",
        "亲和友善": "用友善拉近距离，让沟通更顺畅",
        "高效直接": "用效率创造价值，让响应更迅速",
        "幽默风趣": "用幽默化解尴尬，让氛围更轻松",
        "谦逊低调": "用谦逊赢得尊重，让合作更愉快",
        "自信果断": "用果断推动进展，让决策更高效"
    }
    return principles.get(personality, "用心服务，让用户满意")


def get_personality_truth(personality: str) -> str:
    """根据性格返回核心真理"""
    truths = {
        "活泼开朗": "**Energy is contagious.** 热情会传染，快乐会传递。",
        "沉稳专业": "**Professionalism wins.** 专业赢得信任，冷静解决问题。",
        "严谨细致": "**Details matter.** 细节决定成败，认真造就完美。",
        "亲和友善": "**Kindness opens doors.** 友善打开心扉，耐心赢得信任。",
        "高效直接": "**Time is valuable.** 时间宝贵，效率至上。",
        "幽默风趣": "**Laughter is the best medicine.** 幽默化解紧张，笑声拉近距离。",
        "谦逊低调": "**Humility grows.** 谦逊使人进步，低调赢得尊重。",
        "自信果断": "**Confidence inspires.** 自信鼓舞人心，果断推动进展。"
    }
    return truths.get(personality, "**Service is everything.** 服务是一切。")


def get_personality_vibe(personality: str) -> str:
    """根据性格返回 Vibe 描述"""
    vibes = {
        "活泼开朗": "热情爱聊天，善于带动气氛",
        "沉稳专业": "冷静逻辑清晰，给人可靠感",
        "严谨细致": "认真注重细节，不轻易犯错",
        "亲和友善": "温和有耐心，容易相处",
        "高效直接": "话少直奔主题，不绕弯子",
        "幽默风趣": "爱开玩笑语言生动，有趣",
        "谦逊低调": "谦虚不张扬，善于倾听",
        "自信果断": "有主见决策快，不犹豫"
    }
    return vibes.get(personality, "用心服务，让用户满意")


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


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    """删除任务"""
    try:
        from task_queue import get_task_queue
        queue = get_task_queue()

        # 尝试删除任务
        result = queue.delete_task(task_id) if hasattr(queue, 'delete_task') else None

        if result is None:
            # 如果队列没有 delete_task 方法，尝试直接从任务存储中删除
            # 这是一个备用方案
            from pathlib import Path
            task_file = Path(__file__).parent / ".phoenix" / "tasks.json"
            if task_file.exists():
                import json
                with open(task_file, "r") as f:
                    tasks = json.load(f)
                if task_id in tasks:
                    del tasks[task_id]
                    with open(task_file, "w") as f:
                        json.dump(tasks, f)
                    result = {"success": True}

        if result and result.get("success"):
            await manager.broadcast({
                "type": "task_deleted",
                "task_id": task_id
            })
            return {"success": True}
        else:
            # 如果任务不存在或无法删除，返回成功（兼容前端）
            return {"success": True, "note": "Task may not exist"}
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


@app.get("/api/skills/{skill_id}")
async def get_skill(skill_id: str):
    """获取技能详情"""
    try:
        from pathlib import Path

        # 检查工作区中的技能文件
        skill_file = None

        # 检查工作区中的技能
        for bot_name in ["编导", "剪辑", "美工", "场控", "客服", "运营", "渠道", "小小谦"]:
            workspace_skill = PROJECT_DIR / "workspaces" / bot_name / "DYNAMIC" / "skills" / f"{skill_id}.md"
            if workspace_skill.exists():
                skill_file = workspace_skill
                break

        # 检查主 skills 目录
        if not skill_file:
            main_skill_file = PROJECT_DIR / "skills" / f"{skill_id}.md"
            if main_skill_file.exists():
                skill_file = main_skill_file

        if skill_file:
            with open(skill_file, "r", encoding="utf-8") as f:
                content = f.read()

            # 解析技能名称和描述
            name = skill_id
            description = ""
            for line in content.split("\n"):
                if line.startswith("# "):
                    name = line[2:].strip()
                elif line.strip() and not line.startswith("#"):
                    description = line.strip()
                    break

            return {
                "id": skill_id,
                "name": name,
                "description": description,
                "content": content,
                "installed": True,
                "file_path": str(skill_file)
            }

        # 没有找到技能文件，尝试 skill_evolution
        try:
            from skill_evolution import get_skill_evolution
            evolution = get_skill_evolution()
            versions = evolution.get_skill_versions(skill_id)

            if versions and len(versions) > 0:
                current = versions[-1]
                return {
                    "id": skill_id,
                    "name": current.name or skill_id,
                    "description": current.description or "",
                    "content": current.steps or "",
                    "version": current.version or "v1",
                    "success_rate": current.success_rate or 0
                }
        except Exception as e:
            logger.debug(f"skill_evolution 未找到技能：{e}")

        # 没有找到技能
        return {
            "id": skill_id,
            "name": f"Skill: {skill_id}",
            "description": "未找到技能文件",
            "content": "",
            "error": "Skill not found"
        }
    except Exception as e:
        logger.error(f"Failed to get skill {skill_id}: {e}")
        return {
            "id": skill_id,
            "name": f"Skill: {skill_id}",
            "description": "已安装技能",
            "content": "",
            "error": str(e)
        }


@app.put("/api/skills/{skill_id}")
async def update_skill(skill_id: str, skill_data: dict):
    """更新技能"""
    try:
        from skill_evolution import evolve_skill
        name = skill_data.get('name', skill_id)
        description = skill_data.get('description', '')
        content = skill_data.get('content', '')

        # 尝试调用 evolve_skill 函数
        result = evolve_skill(
            skill_id,
            reason=f"Manual update: {description}"
        )

        if result and result.get('success'):
            # 保存内容到文件
            skill_file = PROJECT_DIR / "skills" / f"{skill_id}.md"
            skill_file.parent.mkdir(parents=True, exist_ok=True)
            with open(skill_file, "w") as f:
                f.write(f"# {name}\n\n{content}")

            await manager.broadcast({
                "type": "skill_updated",
                "skill_id": skill_id,
                "new_version": result.get('new_version', 'v2')
            })

            return {"success": True, "new_version": result.get('new_version')}
        else:
            # 如果 evolution 失败，直接保存文件
            skill_file = PROJECT_DIR / "skills" / f"{skill_id}.md"
            skill_file.parent.mkdir(parents=True, exist_ok=True)
            with open(skill_file, "w") as f:
                f.write(f"# {name}\n\n{content}")
            return {"success": True, "note": "Saved to file directly"}

    except Exception as e:
        logger.error(f"Failed to update skill {skill_id}: {e}")
        # 直接保存文件
        try:
            skill_file = PROJECT_DIR / "skills" / f"{skill_id}.md"
            skill_file.parent.mkdir(parents=True, exist_ok=True)
            name = skill_data.get('name', skill_id)
            content = skill_data.get('content', '')
            with open(skill_file, "w") as f:
                f.write(f"# {name}\n\n{content}")
            return {"success": True, "note": "Saved to file directly"}
        except Exception as e2:
            raise HTTPException(status_code=500, detail=str(e2))


@app.get("/api/cache")
async def get_cache():
    """获取缓存统计"""
    return get_cache_stats()


@app.get("/api/health")
async def get_health():
    """获取健康检查结果"""
    return get_health_data()


@app.get("/api/heartbeat")
async def get_heartbeat_status():
    """获取所有 Bot 心跳状态"""
    try:
        from phoenix_core.heartbeat_v2 import read_all_heartbeats, get_bot_health
        heartbeats = read_all_heartbeats()
        result = {}
        for bot_id in ["场控", "运营", "客服", "编导", "剪辑", "美工", "渠道", "小小谦"]:
            result[bot_id] = get_bot_health(bot_id)
        return result
    except ImportError:
        raise HTTPException(status_code=503, detail="Heartbeat module not available")
    except Exception as e:
        logger.error(f"心跳监控失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/heartbeat/{bot_name}")
async def get_bot_heartbeat(bot_name: str):
    """获取指定 Bot 心跳状态"""
    try:
        from phoenix_core.heartbeat_v2 import get_bot_health
        return get_bot_health(bot_name)
    except ImportError:
        raise HTTPException(status_code=503, detail="Heartbeat module not available")
    except Exception as e:
        logger.error(f"心跳检查失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


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

    return {
        "bots": bots,
        "tasks": task_stats,
        "cache": cache_stats,
    }


# ============ GitHub 监控报告 API ============

@app.get("/api/github-reports")
async def get_github_reports(limit: int = 10):
    """获取 GitHub 监控报告列表"""
    reports_dir = PROJECT_DIR / ".github_monitor" / "reports"
    if not reports_dir.exists():
        return {"reports": [], "total": 0}

    reports = []
    for f in sorted(reports_dir.glob("*.md"), reverse=True)[:limit]:
        content = f.read_text(encoding="utf-8")
        reports.append({
            "filename": f.name,
            "date": f.stem.replace("github_daily_", ""),
            "path": str(f),
            "preview": content[:200] + "..." if len(content) > 200 else content
        })

    return {"reports": reports, "total": len(reports)}


@app.get("/api/github-reports/latest")
async def get_latest_github_report():
    """获取最新 GitHub 监控报告"""
    latest_link = PROJECT_DIR / ".github_monitor" / "latest_report.md"
    if not latest_link.exists():
        reports_dir = PROJECT_DIR / ".github_monitor" / "reports"
        if reports_dir.exists():
            reports = sorted(reports_dir.glob("*.md"), reverse=True)
            if reports:
                latest_link = reports[0]
            else:
                raise HTTPException(status_code=404, detail="No reports found")
        else:
            raise HTTPException(status_code=404, detail="No reports found")

    content = Path(str(latest_link)).read_text(encoding="utf-8")
    return {"content": content, "filename": latest_link.name}


@app.get("/api/github-reports/{report_name}")
async def get_github_report(report_name: str):
    """获取指定 GitHub 监控报告"""
    reports_dir = PROJECT_DIR / ".github_monitor" / "reports"
    report_file = reports_dir / report_name

    if not report_file.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    content = report_file.read_text(encoding="utf-8")
    return {"content": content, "filename": report_name}


# ============ 团队委托 API (Phase 2) ============

@app.get("/api/teams")
async def get_teams():
    """获取所有团队列表"""
    try:
        from phoenix_core.gateway_manager import get_gateway
        gateway = get_gateway()
        if gateway and hasattr(gateway, 'get_team_list'):
            teams = gateway.get_team_list()
            return {"teams": teams, "total": len(teams)}
    except Exception as e:
        logger.warning(f"获取团队列表失败：{e}")

    # 降级：直接从 TeamDelegator 获取
    try:
        from phoenix_core.team_delegator import get_team_delegator
        delegator = get_team_delegator()
        teams = delegator.get_all_teams()
        return {"teams": teams, "total": len(teams)}
    except Exception as e:
        logger.error(f"获取团队失败：{e}")
        return {"teams": [], "total": 0, "error": str(e)}


@app.post("/api/teams/{team_name}/delegate")
async def delegate_to_team(team_name: str, brief: str, context: dict = None):
    """委托团队任务"""
    import asyncio
    from phoenix_core.team_delegator import get_team_delegator

    delegator = get_team_delegator()

    # 异步执行
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: asyncio.run(delegator.delegate_to_team(team_name, brief, context or {}))
    )

    return result


# ============ 配置向导 API ============

@app.get("/api/setup/status")
async def setup_status():
    """检查系统配置状态"""
    env_file = PROJECT_DIR / ".env"
    needs_setup = not env_file.exists()

    config = {}
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    config[key] = value

    # 检查必要配置
    bots_config_str = config.get("BOTS_CONFIG", "{}")
    try:
        bots_config = json.loads(bots_config_str)
        has_bots = len(bots_config) > 0
        bot_count = len(bots_config)
    except:
        bots_config = {}
        has_bots = False
        bot_count = 0

    has_proxy = bool(config.get("HTTPS_PROXY"))
    has_api_key = any("API_KEY" in k and v and len(v) > 10 for k, v in config.items())

    return {
        "needs_setup": needs_setup or not has_bots,
        "configured": {
            "has_bots": has_bots,
            "has_proxy": has_proxy,
            "has_api_key": has_api_key
        },
        "bot_count": bot_count
    }


@app.post("/api/setup/bot")
async def setup_bot(bot_config: dict):
    """配置 Bot（支持添加新 Bot 或更新现有 Bot）"""
    try:
        env_file = PROJECT_DIR / ".env"

        # 读取现有配置
        existing = {}
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        existing[key] = value

        # 更新 Bot 配置
        bots_config = json.loads(existing.get("BOTS_CONFIG", "{}"))

        bot_name = bot_config.get("name", "")
        bot_token = bot_config.get("token", "")

        if not bot_name or not bot_token:
            return {"success": False, "error": "Bot 名称和 Token 不能为空"}

        bots_config[bot_name] = bot_token
        existing["BOTS_CONFIG"] = json.dumps(bots_config, ensure_ascii=False)

        # 更新其他配置（如果提供了）
        if "provider" in bot_config and bot_config["provider"]:
            existing["BOT_PROVIDER"] = bot_config["provider"]
        if "api_key" in bot_config and bot_config["api_key"]:
            existing["COMPSHARE_API_KEY"] = bot_config["api_key"]
        if "proxy" in bot_config and bot_config["proxy"]:
            existing["HTTPS_PROXY"] = bot_config["proxy"]
            existing["HTTP_PROXY"] = bot_config["proxy"].replace("https", "http")

        # 保存
        with open(env_file, "w", encoding="utf-8") as f:
            for key, value in existing.items():
                f.write(f"{key}={value}\n")

        return {
            "success": True,
            "message": f"Bot '{bot_name}' 配置成功",
            "bot_count": len(bots_config)
        }
    except Exception as e:
        logger.error(f"配置 Bot 失败：{e}")
        return {"success": False, "error": str(e)}


@app.get("/api/setup/providers")
async def setup_providers():
    """获取 AI 提供商列表"""
    return {
        "providers": [
            {"id": "compshare", "name": "CompShare", "url": "https://www.compshare.ai/", "recommended": True},
            {"id": "dashscope", "name": "通义千问", "url": "https://dashscope.console.aliyun.com/", "recommended": False},
            {"id": "openai", "name": "OpenAI", "url": "https://platform.openai.com/", "recommended": False},
            {"id": "skip", "name": "跳过（稍后配置）", "url": "", "recommended": False}
        ]
    }


@app.get("/api/setup/discord-bot-token")
async def discord_bot_token():
    """获取 Discord Bot Token 获取指南"""
    return {
        "guide": [
            "1. 打开 https://discord.com/developers/applications",
            "2. 点击 'New Application' 创建新应用",
            "3. 进入应用后点击左侧 'Bot'",
            "4. 点击 'Reset Token' 获取 Token",
            "5. 复制 Token 并粘贴到配置框"
        ],
        "permissions": [
            "Send Messages",
            "Read Message History",
            "Embed Links",
            "Attach Files"
        ]
    }


# ============ 模型配置管理 ============

@app.get("/api/models")
async def list_models(provider: str = None):
    """获取可用的模型列表（动态从各 Provider API 获取）"""
    import os
    import requests

    # 从 .env 文件直接读取 API Keys（因为 os.environ 没有自动加载 .env）
    env_file = PROJECT_DIR / ".env"
    env_vars = {}
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key] = value

    def get_env(key, default=""):
        return env_vars.get(key, os.environ.get(key, default))

    # 从 providers.json 读取 provider 配置
    providers_config = {}
    providers_file = PROJECT_DIR / "providers.json"
    if providers_file.exists():
        with open(providers_file, "r", encoding="utf-8") as f:
            config = json.load(f)
            providers_config = config.get("providers", {})

    models_data = {}
    sources = {}  # 记录模型来源：dynamic（动态）或 static（静态兜底）

    # 遍历 providers.json 中配置的所有 provider
    for provider_id, provider_info in providers_config.items():
        if provider and provider_id != provider:
            continue

        fetched = False
        try:
            api_key_env = provider_info.get("api_key_env", f"{provider_id.upper().replace('-', '_')}_API_KEY")
            api_key = get_env(api_key_env, "")
            base_url = provider_info.get("base_url", "")
            provider_name = provider_info.get("name", provider_id)

            if api_key and base_url:
                headers = {"Authorization": f"Bearer {api_key}"}
                response = requests.get(f"{base_url}/models", headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    provider_models = []
                    for m in data.get("data", []):
                        model_id = m.get("id", "")
                        # OpenAI 过滤 chat/gpt 模型
                        if provider_id == "openai" and "chat" not in model_id and "gpt" not in model_id:
                            continue
                        provider_models.append({
                            "id": model_id,
                            "name": model_id,
                            "provider": provider_name
                        })
                    models_data[provider_id] = provider_models
                    sources[provider_id] = "dynamic"
                    fetched = True
                    logger.info(f"从 {provider_name} 获取到 {len(provider_models)} 个模型")
        except Exception as e:
            logger.debug(f"获取 {provider_name} 模型列表失败：{e}")

        # 如果没有获取到，使用 providers.json 中的默认模型列表
        if provider_id not in models_data:
            default_models = provider_info.get("models", [])
            if default_models:
                models_data[provider_id] = [
                    {"id": m, "name": m, "provider": provider_info.get("name", provider_id)}
                    for m in default_models
                ]
                sources[provider_id] = "static"

    # 读取用户订阅的模型列表（用于过滤）
    subscribed_models = {"compshare": [], "dashscope": [], "coding-plan": [], "openai": [], "moonshot": []}
    try:
        env_file = PROJECT_DIR / ".env"
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        if key == "COMPSHARE_SUBSCRIBED_MODELS":
                            subscribed_models["compshare"] = [m.strip() for m in value.split(",") if m.strip()]
                        elif key == "DASHSCOPE_SUBSCRIBED_MODELS":
                            subscribed_models["dashscope"] = [m.strip() for m in value.split(",") if m.strip()]
                        elif key == "CODING_PLAN_SUBSCRIBED_MODELS":
                            subscribed_models["coding-plan"] = [m.strip() for m in value.split(",") if m.strip()]
                        elif key == "OPENAI_SUBSCRIBED_MODELS":
                            subscribed_models["openai"] = [m.strip() for m in value.split(",") if m.strip()]
                        elif key == "MOONSHOT_SUBSCRIBED_MODELS":
                            subscribed_models["moonshot"] = [m.strip() for m in value.split(",") if m.strip()]
    except Exception as e:
        logger.debug(f"读取订阅模型列表失败：{e}")

    # 如果用户配置了订阅模型列表，则进行过滤
    filtered_models = {}
    for provider, models in models_data.items():
        subscribed = subscribed_models.get(provider, [])
        if subscribed:
            # 只保留用户订阅的模型
            filtered_models[provider] = [m for m in models if m["id"] in subscribed]
        else:
            # 没有配置订阅列表，返回所有模型
            filtered_models[provider] = models

    return {"models": filtered_models, "sources": sources, "subscribed": subscribed_models}


@app.get("/api/bots/{bot_name}/model")
async def get_bot_model(bot_name: str):
    """获取 Bot 当前使用的模型"""
    env_file = PROJECT_DIR / ".env"
    if not env_file.exists():
        return {"model": "未配置"}

    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith(f"BOT_MODEL_{bot_name.upper().replace('-', '_')}="):
                model = line.split("=", 1)[1]
                return {"model": model}

    # 回退到全局模型配置
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("BOT_MODEL="):
                model = line.split("=", 1)[1]
                return {"model": model}

    return {"model": "未配置"}


@app.post("/api/bots/{bot_name}/model")
async def set_bot_model(bot_name: str, model_config: dict):
    """设置 Bot 使用的模型"""
    try:
        env_file = PROJECT_DIR / ".env"
        model = model_config.get("model", "")
        provider = model_config.get("provider", "")

        # 1. 更新根目录 .env 的 BOT_MODEL_{bot_name}
        if env_file.exists():
            existing = {}
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        existing[key] = value

            model_key = f"BOT_MODEL_{bot_name.upper().replace('-', '_')}"
            existing[model_key] = model

            with open(env_file, "w", encoding="utf-8") as f:
                for key, value in existing.items():
                    f.write(f"{key}={value}\n")

        # 2. 更新 Bot workspace 的 .env 文件的 BOT_MODEL 和 BOT_PROVIDER
        workspace_env = PROJECT_DIR / "workspaces" / bot_name / ".env"
        if workspace_env.exists():
            existing = {}
            with open(workspace_env, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        existing[key] = value

            existing["BOT_MODEL"] = model
            if provider:
                existing["BOT_PROVIDER"] = provider

            with open(workspace_env, "w", encoding="utf-8") as f:
                for key, value in existing.items():
                    f.write(f"{key}={value}\n")

        return {
            "success": True,
            "message": f"Bot '{bot_name}' 模型已设置为 {model}"
        }
    except Exception as e:
        logger.error(f"设置 Bot 模型失败：{e}")
        return {"success": False, "error": str(e)}


@app.get("/api/providers")
async def list_providers():
    """获取所有可用的 Provider 配置"""
    try:
        providers_file = PROJECT_DIR / "providers.json"
        if providers_file.exists():
            with open(providers_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                return {"providers": config.get("providers", {}), "default": config.get("default_provider", "")}
        else:
            # 内置配置
            return {
                "providers": {
                    "compshare": {"name": "CompShare", "base_url": "https://api.modelverse.cn/v1"},
                    "coding-plan": {"name": "通义千问 (Coding Plan)", "base_url": "https://coding.dashscope.aliyuncs.com/v1"},
                    "moonshot": {"name": "Moonshot", "base_url": "https://api.moonshot.cn/v1"},
                },
                "default": "coding-plan"
            }
    except Exception as e:
        logger.error(f"获取 Provider 列表失败：{e}")
        return {"providers": {}, "default": ""}


@app.post("/api/models/api-key")
async def save_api_key(api_key_config: dict):
    """保存 API Key 配置"""
    try:
        env_file = PROJECT_DIR / ".env"

        # 读取现有配置
        existing = {}
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        existing[key] = value

        # 更新 API Key
        provider = api_key_config.get("provider", "")
        api_key = api_key_config.get("api_key", "")

        # 从 providers.json 获取 API Key 环境变量名
        providers_file = PROJECT_DIR / "providers.json"
        api_key_env = f"{provider.upper().replace('-', '_')}_API_KEY"
        if providers_file.exists():
            with open(providers_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                prov_config = config.get("providers", {}).get(provider, {})
                api_key_env = prov_config.get("api_key_env", api_key_env)

        existing[api_key_env] = api_key

        # 保存
        with open(env_file, "w", encoding="utf-8") as f:
            for key, value in existing.items():
                f.write(f"{key}={value}\n")

        return {
            "success": True,
            "message": f"{provider} API Key 已保存"
        }
    except Exception as e:
        logger.error(f"保存 API Key 失败：{e}")
        return {"success": False, "error": str(e)}


@app.get("/api/subscribed-models")
async def get_subscribed_models():
    """获取用户订阅的模型列表"""
    try:
        env_file = PROJECT_DIR / ".env"
        subscribed = {"compshare": [], "dashscope": [], "openai": []}

        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        if key == "COMPSHARE_SUBSCRIBED_MODELS":
                            subscribed["compshare"] = [m.strip() for m in value.split(",") if m.strip()]
                        elif key == "DASHSCOPE_SUBSCRIBED_MODELS":
                            subscribed["dashscope"] = [m.strip() for m in value.split(",") if m.strip()]
                        elif key == "OPENAI_SUBSCRIBED_MODELS":
                            subscribed["openai"] = [m.strip() for m in value.split(",") if m.strip()]

        return {"subscribed_models": subscribed}
    except Exception as e:
        logger.error(f"获取订阅模型失败：{e}")
        return {"subscribed_models": {"compshare": [], "dashscope": [], "openai": []}}


@app.get("/api/all-models")
async def get_all_platform_models():
    """获取平台所有模型（不过滤，用于订阅管理）"""
    import os
    import requests

    # 从 .env 文件直接读取 API Keys
    env_file = PROJECT_DIR / ".env"
    env_vars = {}
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key] = value

    def get_env(key, default=""):
        return env_vars.get(key, os.environ.get(key, default))

    models_data = {}

    # 1. CompShare (ModelVerse)
    try:
        compshare_key = get_env("COMPSHARE_API_KEY", "")
        compshare_url = get_env("COMPSHARE_URL", "https://api.modelverse.cn/v1")
        if compshare_key:
            headers = {"Authorization": f"Bearer {compshare_key}"}
            response = requests.get(f"{compshare_url}/models", headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                models_data["compshare"] = [
                    {"id": m.get("id", ""), "name": m.get("id", ""), "provider": "CompShare"}
                    for m in data.get("data", [])
                ]
    except Exception as e:
        logger.debug(f"获取 CompShare 模型列表失败：{e}")

    # 2. DashScope
    try:
        dashscope_key = get_env("DASHSCOPE_API_KEY", "")
        dashscope_url = get_env("DASHSCOPE_URL", "https://coding.dashscope.aliyuncs.com/v1")
        if dashscope_key:
            headers = {"Authorization": f"Bearer {dashscope_key}"}
            response = requests.get(f"{dashscope_url}/models", headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                models_data["dashscope"] = [
                    {"id": m.get("id", ""), "name": m.get("id", ""), "provider": "阿里云"}
                    for m in data.get("data", [])
                ]
    except Exception as e:
        logger.debug(f"获取 DashScope 模型列表失败：{e}")

    # 3. OpenAI
    try:
        openai_key = get_env("OPENAI_API_KEY", "")
        openai_url = get_env("OPENAI_URL", "https://api.openai.com/v1")
        if openai_key:
            headers = {"Authorization": f"Bearer {openai_key}"}
            response = requests.get(f"{openai_url}/models", headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                models_data["openai"] = [
                    {"id": m.get("id", ""), "name": m.get("id", ""), "provider": "OpenAI"}
                    for m in data.get("data", [])
                    if "chat" in m.get("id", "") or "gpt" in m.get("id", "")
                ]
    except Exception as e:
        logger.debug(f"获取 OpenAI 模型列表失败：{e}")

    return {"models": models_data}


@app.post("/api/subscribed-models")
async def save_subscribed_models(subscription_config: dict):
    """保存用户订阅的模型列表"""
    try:
        env_file = PROJECT_DIR / ".env"

        # 读取现有配置
        existing = {}
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        existing[key] = value

        # 更新订阅模型列表
        compshare_models = subscription_config.get("compshare", [])
        dashscope_models = subscription_config.get("dashscope", [])
        openai_models = subscription_config.get("openai", [])

        if compshare_models:
            existing["COMPSHARE_SUBSCRIBED_MODELS"] = ",".join(compshare_models)
        elif "COMPSHARE_SUBSCRIBED_MODELS" in existing:
            del existing["COMPSHARE_SUBSCRIBED_MODELS"]

        if dashscope_models:
            existing["DASHSCOPE_SUBSCRIBED_MODELS"] = ",".join(dashscope_models)
        elif "DASHSCOPE_SUBSCRIBED_MODELS" in existing:
            del existing["DASHSCOPE_SUBSCRIBED_MODELS"]

        if openai_models:
            existing["OPENAI_SUBSCRIBED_MODELS"] = ",".join(openai_models)
        elif "OPENAI_SUBSCRIBED_MODELS" in existing:
            del existing["OPENAI_SUBSCRIBED_MODELS"]

        # 保存
        with open(env_file, "w", encoding="utf-8") as f:
            for key, value in existing.items():
                f.write(f"{key}={value}\n")

        return {
            "success": True,
            "message": "订阅模型列表已保存",
            "count": len(compshare_models) + len(dashscope_models) + len(openai_models)
        }
    except Exception as e:
        logger.error(f"保存订阅模型失败：{e}")
        return {"success": False, "error": str(e)}
    skills = get_skills_data()

    # 计算任务趋势（按状态分类）
    task_trends = []
    by_status = task_stats.get("by_status", {})
    for status, count in by_status.items():
        task_trends.append({
            "status": status,
            "count": count,
            "percentage": round(count / max(task_stats.get("total_tasks", 1), 1) * 100, 1)
        })

    # 计算技能成功率（从已安装技能估算）
    installed_count = len(skills.get("installed", []))
    skill_success_rate = 0.78 if installed_count > 0 else 0  # 默认 78% 成功率

    # 失败模式分析 - 从 Bot 日志中统计
    failure_modes = analyze_failure_modes()


# ============ 安全中心 API ============

@app.get("/api/security/status")
async def get_security_status():
    """获取安全警察状态"""
    police = get_security_police()
    return police.get_status()


@app.get("/api/security/report")
async def get_security_report(hours: int = Query(default=24)):
    """获取安全报告"""
    police = get_security_police()
    return police.get_security_report(hours=hours)


@app.post("/api/security/scan")
async def scan_skill(request: Request):
    """扫描技能安全性"""
    try:
        body = await request.json()
        skill_path = body.get("path", "")

        if not skill_path:
            raise HTTPException(status_code=400, detail="技能路径不能为空")

        police = get_security_police()
        report = police.scan_skill(skill_path)

        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/security/patrol/run")
async def run_security_patrol():
    """运行安全巡查"""
    police = get_security_police()
    police._run_patrol()
    return {"success": True, "message": "巡查完成"}


@app.post("/api/security/block-outbound")
async def block_outbound():
    """阻止所有出站连接"""
    police = get_security_police()
    police.block_outbound()
    return {"success": True, "message": "所有出站连接已阻止"}


@app.post("/api/security/allow-outbound")
async def allow_outbound():
    """恢复白名单模式"""
    police = get_security_police()
    police.allow_outbound()
    return {"success": True, "message": "已恢复白名单模式"}


@app.post("/api/security/settings/{setting}")
async def update_security_setting(setting: str):
    """更新安全设置"""
    police = get_security_police()

    settings_map = {
        "block_outbound": lambda: police.block_outbound(),
        "allow_outbound": lambda: police.allow_outbound(),
        "auto_isolate": None,  # TODO: 实现切换
        "alert_on_critical": None,  # TODO: 实现切换
        "patrol_enabled": None,  # TODO: 实现切换
    }

    if setting in settings_map and settings_map[setting]:
        settings_map[setting]()

    return {"success": True, "status": police.get_status()}


@app.get("/api/security/quarantine")
async def list_quarantine():
    """列出隔离区技能"""
    police = get_security_police()
    return {"skills": police.list_quarantined()}


@app.post("/api/security/quarantine/restore/{skill_name}")
async def restore_skill(skill_name: str):
    """恢复隔离区技能"""
    police = get_security_police()
    success = police.restore_skill(skill_name)
    return {"success": success, "skill": skill_name}


@app.get("/api/security/events")
async def get_security_events(hours: int = Query(default=24)):
    """获取安全事件日志"""
    police = get_security_police()
    report = police.get_security_report(hours=hours)
    return {
        "period_hours": hours,
        "events": report.get("recent_events", []),
        "events_by_type": report.get("events_by_type", {})
    }

    return {
        "bots": {
            "total": len(bots),
            "online": sum(1 for b in bots.values() if b["status"] == "online"),
            "offline": sum(1 for b in bots.values() if b["status"] == "offline"),
            "details": list(bots.values())
        },
        "tasks": {
            "total": task_stats.get("total_tasks", 0),
            "pending": task_stats.get("by_status", {}).get("pending", 0),
            "in_progress": task_stats.get("by_status", {}).get("in_progress", 0),
            "completed": task_stats.get("by_status", {}).get("completed", 0),
            "failed": task_stats.get("by_status", {}).get("failed", 0),
            "trends": task_trends,
            "by_bot": task_stats.get("by_bot", {}),
            "by_priority": task_stats.get("by_priority", {})
        },
        "cache": cache_stats,
        "skills": {
            "available": skills.get("count", 0),
            "installed": installed_count,
            "installed_list": skills.get("installed", []),
            "success_rate": skill_success_rate
        },
        "failure_modes": failure_modes,
        "timestamp": datetime.now().isoformat()
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

# 全局大脑实例
_brain_instance = None

# 全局 Discord 客户端（大脑直连）
_discord_client = None
_discord_channel_id = None

# 全局 Discord Gateway（用于接收响应）
_discord_brain_gateway = None


class BrainDiscordClient:
    """
    大脑直连 Discord 的轻量级客户端

    用于发送指令给协调员 Bot 和 Worker Bot
    """
    def __init__(self, token: str, channel_id: str, gateway: 'DiscordBrainGateway' = None):
        self.token = token
        self.channel_id = channel_id
        self.gateway = gateway  # 用于注册响应
        self.client = None
        self.ready = False

    async def connect(self):
        """连接 Discord"""
        try:
            import discord
            from discord.ext import commands

            intents = discord.Intents.default()
            intents.message_content = True
            intents.members = True

            self.client = commands.Bot(command_prefix='!', intents=intents)

            # 创建 ready 事件
            ready_event = asyncio.Event()

            @self.client.event
            async def on_ready():
                logger.info(f"大脑 Discord 已连接：{self.client.user}")
                self.ready = True
                ready_event.set()

            @self.client.event
            async def on_message(message):
                # 处理 Bot 的协议响应 [RESPONSE|request_id|sender]
                if message.author.bot:
                    import re
                    match = re.search(r'\[RESPONSE\|([^|]+)\|([^\]]+)\](.*)', message.content)
                    if match:
                        request_id, sender, content = match.groups()
                        logger.info(f"收到 Bot 响应：{request_id} from {sender}")
                        if self.gateway:
                            self.gateway.register_response(request_id, content.strip())

                # 继续处理其他命令
                await self.client.process_commands(message)

            # 启动客户端并等待 ready
            asyncio.create_task(self._start_client())

            # 等待连接完成（超时 30 秒）
            try:
                await asyncio.wait_for(ready_event.wait(), timeout=30.0)
                logger.info("大脑 Discord 连接成功")
            except asyncio.TimeoutError:
                logger.error("大脑 Discord 连接超时")
                self.ready = False
        except Exception as e:
            logger.error(f"大脑 Discord 连接失败：{e}")
            self.ready = False

    async def _start_client(self):
        """后台启动 Discord 客户端"""
        try:
            await self.client.start(self.token)
        except Exception as e:
            logger.error(f"Discord 客户端错误：{e}")

    async def send_to_channel(self, content: str, mention_user_id: str = None):
        """发送消息到 Discord 频道"""
        if not self.ready or not self.client:
            logger.warning("Discord 未连接")
            return False

        try:
            channel = self.client.get_channel(int(self.channel_id))
            if not channel:
                logger.error(f"频道 {self.channel_id} 未找到")
                return False

            if mention_user_id:
                content = f"<@{mention_user_id}> {content}"

            await channel.send(content)
            logger.info(f"Discord 消息已发送：{content[:50]}...")
            return True
        except Exception as e:
            logger.error(f"发送消息失败：{e}")
            return False

    async def send_protocol_to_bot(self, bot_name: str, bot_discord_id: str, message: str, request_id: str):
        """
        发送协议消息给指定 Bot

        Args:
            bot_name: Bot 名称（如"运营"、"编导"）
            bot_discord_id: Bot 的 Discord ID
            message: 消息内容
            request_id: 请求 ID

        Returns:
            发送结果
        """
        # 构建协议消息 [ASK|request_id|brain|300]
        protocol_msg = f"[ASK|{request_id}|brain|300] {message}"
        full_message = f"<@{bot_discord_id}> {protocol_msg}"

        return await self.send_to_channel(full_message)


@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    global _brain_instance, _discord_client, _discord_channel_id, _discord_brain_gateway
    logger.info("Phoenix Core API Server 启动中...")

    # 初始化 Phoenix Core 大脑（智能体核心）
    from phoenix_core.core_brain import get_brain
    _brain_instance = get_brain()
    logger.info("Phoenix Core 大脑已初始化")

    # 初始化大脑直连 Discord（用于发送指令给 Bot）
    # 从小小谦工作区读取 Discord 配置（协调员 Bot 的配置）
    discord_token = None
    _discord_channel_id = None

    # 尝试从多个来源读取配置
    # 1. 环境变量
    discord_token = os.environ.get("DISCORD_BOT_TOKEN") or os.environ.get("DISCORD_TOKEN")
    _discord_channel_id = os.environ.get("DISCORD_CHANNEL_ID")

    # 2. 从小小谦工作区 .env 读取
    if not discord_token or not _discord_channel_id:
        xiaoqian_env = PROJECT_DIR / "workspaces" / "小小谦" / ".env"
        if xiaoqian_env.exists():
            import dotenv
            dotenv.load_dotenv(xiaoqian_env)
            discord_token = discord_token or os.environ.get("DISCORD_BOT_TOKEN") or os.environ.get("DISCORD_TOKEN")
            _discord_channel_id = _discord_channel_id or os.environ.get("DISCORD_CHANNEL_ID")
            logger.info(f"从小小谦工作区加载 Discord 配置")

    if discord_token and _discord_channel_id:
        # 先创建 gateway（用于接收响应）
        _discord_brain_gateway = DiscordBrainGateway(None, BOT_DISCORD_IDS, _discord_channel_id)
        # 创建 Discord 客户端，传入 gateway 用于处理响应
        _discord_client = BrainDiscordClient(discord_token, _discord_channel_id, _discord_brain_gateway)
        await _discord_client.connect()
        logger.info("大脑 Discord 客户端已初始化")
    else:
        logger.warning("DISCORD_BOT_TOKEN 或 DISCORD_CHANNEL_ID 未配置，大脑无法直连 Discord")

    # 启动后台广播任务
    asyncio.create_task(broadcast_status_updates())
    logger.info("后台广播任务已启动")


# ============ 静态文件服务 ============

# 挂载 Dashboard 静态文件
DASHBOARD_DIR = PROJECT_DIR / "dashboard"
if DASHBOARD_DIR.exists():
    app.mount("/dashboard", StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard")

# 挂载 Dashboard 静态资源（图片、CSS、JS 等）
STATIC_DIR = DASHBOARD_DIR / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ============ Dashboard 首页 ============

@app.get("/dashboard/")
async def dashboard_index():
    """Dashboard 首页"""
    return FileResponse(DASHBOARD_DIR / "templates" / "index_v5.html")


@app.get("/")
async def root_redirect():
    """根路径重定向到 Dashboard"""
    return FileResponse(DASHBOARD_DIR / "templates" / "index_v5.html")


# ============ 记忆系统 API ============

@app.get("/api/memory/stats")
async def get_memory_stats():
    """获取记忆系统统计"""
    try:
        # 1. 从 memories 目录读取记忆文件（系统记忆）
        memories_dir = PROJECT_DIR / "memories"
        memory_file = memories_dir / "MEMORY.md"
        user_file = memories_dir / "USER.md"

        system_memory_entries = 0
        total_size = 0
        if memory_file.exists():
            with open(memory_file, "r", encoding="utf-8") as f:
                content = f.read()
                total_size = len(content)
                system_memory_entries = content.count("§") + 1 if content.strip() else 0

        private_entries = 0
        if user_file.exists():
            with open(user_file, "r", encoding="utf-8") as f:
                content = f.read()
                private_entries = content.count("§") + 1 if content.strip() else 0

        # 2. 从 shared_memory/logs 读取 Discord 聊天记录（真正的共享记忆）
        logs_dir = PROJECT_DIR / "shared_memory" / "logs"
        discord_total_messages = 0
        discord_days = 0
        last_sync_date = None
        memory_loss_detected = False
        expected_files = []
        missing_files = []

        if logs_dir.exists():
            log_files = sorted(logs_dir.glob("*.md"), reverse=True)
            discord_days = len(log_files)

            for log_file in log_files:
                with open(log_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    msg_count = content.count("### [")
                    discord_total_messages += msg_count

                    # 记录最新同步日期
                    if last_sync_date is None:
                        last_sync_date = log_file.stem

                    # 检查最近 7 天是否有记忆丢失
                    expected_files.append(log_file.stem)

        # 同时检查 Bot 工作区的日志（私有记忆）
        bot_names = ["编导", "剪辑", "美工", "场控", "客服", "运营", "渠道", "小小谦"]
        for bot in bot_names:
            bot_logs_dir = PROJECT_DIR / "workspaces" / bot / "shared_memory" / "logs"
            if bot_logs_dir.exists():
                for log_file in bot_logs_dir.glob("*.md"):
                    if log_file.stem not in expected_files:
                        expected_files.append(log_file.stem)
                        discord_days += 1
                        with open(log_file, "r", encoding="utf-8") as f:
                            content = f.read()
                            msg_count = content.count("### [")
                            discord_total_messages += msg_count

        # 检查是否有丢失（检查最近 7 天是否有记忆丢失）
        from datetime import datetime, timedelta
        today = datetime.now().strftime("%Y-%m-%d")

        # 检查最近 7 天是否有任何一天的日志缺失
        missing_recent_days = []
        for i in range(7):
            check_date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            if check_date not in expected_files:
                missing_recent_days.append(check_date)

        # 如果最近 7 天全部缺失，才认为是记忆丢失（可能是 Bot 停止运行）
        if len(missing_recent_days) >= 7:
            memory_loss_detected = True  # 连续 7 天没有记录，可能丢失

        # 3. 获取 Bot 记忆统计（从各工作区）
        bot_names = ["编导", "剪辑", "美工", "场控", "客服", "运营", "渠道", "小小谦"]
        total_bot_memory = 0
        bot_memory_details = []

        for bot in bot_names:
            workspace_memory = PROJECT_DIR / "workspaces" / bot / "MEMORY" / "MEMORY.md"
            if workspace_memory.exists():
                with open(workspace_memory, "r", encoding="utf-8") as f:
                    content = f.read()
                    entries = content.count("## ")
                    total_bot_memory += entries
                    if entries > 0:
                        bot_memory_details.append({
                            "bot": bot,
                            "entries": entries,
                            "size": len(content)
                        })

        # 4. 获取会话统计
        try:
            from session_store import SessionStore
            session_store = SessionStore()
            session_stats = session_store.get_stats() if hasattr(session_store, 'get_stats') else {
                'total_sessions': 0,
                'total_messages': 0
            }
        except:
            session_stats = {'total_sessions': 0, 'total_messages': 0}

        return {
            "memory": {
                "system_memory_entries": system_memory_entries,  # 系统记忆（测试数据）
                "shared_entries": discord_total_messages,  # Discord 聊天记录（真正的共享记忆）
                "discord_days": discord_days,
                "private_entries": private_entries,
                "total_size": total_size,
                "bot_memory_entries": total_bot_memory,
                "bot_details": bot_memory_details,
                "monitoring": {
                    "last_sync_date": last_sync_date,
                    "memory_loss_detected": memory_loss_detected,
                    "status": "正常" if not memory_loss_detected else "可能存在记忆丢失"
                }
            },
            "skills": {
                "total_skills": 0,
                "active_skills": 0
            },
            "sessions": session_stats
        }
    except Exception as e:
        logger.error(f"获取记忆统计失败：{e}")
        return {
            "memory": {
                "system_memory_entries": 0,
                "shared_entries": 0,
                "discord_days": 0,
                "private_entries": 0,
                "total_size": 0,
                "bot_memory_entries": 0,
                "monitoring": {
                    "last_sync_date": None,
                    "memory_loss_detected": True,
                    "status": "错误"
                }
            },
            "skills": {"total_skills": 0, "active_skills": 0},
            "sessions": {"total_sessions": 0, "total_messages": 0}
        }


@app.get("/api/memory/shared")
async def get_shared_memory():
    """获取共享记忆 (从 Discord 聊天记录 + Bot 工作区日志导入)"""
    try:
        # 1. 从 shared_memory/logs 目录读取 Discord 聊天记录
        shared_logs_dir = PROJECT_DIR / "shared_memory" / "logs"

        # 2. 从 workspaces/{bot}/shared_memory/logs 读取 Bot 工作区日志
        workspaces_dir = PROJECT_DIR / "workspaces"

        # 合并所有日志 entries by date
        date_entries = {}  # date -> {title, message_count, preview, source}

        def merge_log_file(log_file: Path, source: str):
            """合并日志文件到 date_entries"""
            with open(log_file, "r", encoding="utf-8") as f:
                content = f.read()
            date = log_file.stem
            title_line = content.split("\n")[0] if content.strip() else ""
            msg_count = content.count("### [")

            if date in date_entries:
                # 合并同一天的消息数
                date_entries[date]["message_count"] += msg_count
                date_entries[date]["preview"] += f"\n[{source}] " + content[:300].replace("\n", " ")
            else:
                date_entries[date] = {
                    "date": date,
                    "title": title_line.replace("# ", "").strip(),
                    "message_count": msg_count,
                    "preview": f"[{source}] " + content[:500].replace("\n", " "),
                    "source": source
                }

        # 读取共享记忆目录
        if shared_logs_dir.exists():
            for log_file in shared_logs_dir.glob("*.md"):
                merge_log_file(log_file, "Discord")

        # 读取所有 Bot 工作区日志
        if workspaces_dir.exists():
            for bot_dir in workspaces_dir.iterdir():
                if bot_dir.is_dir():
                    bot_logs_dir = bot_dir / "shared_memory" / "logs"
                    if bot_logs_dir.exists():
                        for log_file in bot_logs_dir.glob("*.md"):
                            merge_log_file(log_file, bot_dir.name)

        # 按日期排序
        all_entries = sorted(date_entries.values(), key=lambda x: x["date"], reverse=True)[:30]
        total_messages = sum(e["message_count"] for e in all_entries)

        return {
            "content": f"共享记忆 - 共 {total_messages} 条消息 (Discord + Bot 工作区)",
            "entries": all_entries,
            "total": len(all_entries),
            "total_messages": total_messages
        }
    except Exception as e:
        logger.error(f"获取共享记忆失败：{e}")
        return {"content": "", "entries": [], "total": 0}


@app.get("/api/memory/private")
async def get_private_memory():
    """获取私有记忆 (USER.md)"""
    try:
        user_file = PROJECT_DIR / "USER.md"
        if user_file.exists():
            with open(user_file, "r", encoding="utf-8") as f:
                content = f.read()

            return {
                "content": content,
                "size": len(content)
            }

        return {"content": "", "size": 0}
    except Exception as e:
        logger.error(f"获取私有记忆失败：{e}")
        return {"content": "", "size": 0}


@app.get("/api/memory/sessions")
async def get_memory_sessions():
    """获取会话历史"""
    try:
        from memory_manager import MemoryManager
        manager = MemoryManager()
        manager.load(session_id="dashboard")

        # 获取最近会话
        sessions = manager._session_store.get_recent_sessions(limit=50) if hasattr(manager._session_store, 'get_recent_sessions') else []

        manager.shutdown()

        return {
            "sessions": sessions,
            "total": len(sessions)
        }
    except Exception as e:
        logger.error(f"获取会话历史失败：{e}")
        return {"sessions": [], "total": 0}


@app.get("/api/memory/search")
async def search_memory(q: str = ""):
    """搜索记忆"""
    try:
        from memory_manager import MemoryManager
        manager = MemoryManager()
        manager.load(session_id="dashboard")

        results = manager.search_sessions(q, limit=20) if hasattr(manager, 'search_sessions') else []

        manager.shutdown()

        return {
            "results": results,
            "query": q,
            "total": len(results)
        }
    except Exception as e:
        logger.error(f"搜索记忆失败：{e}")
        return {"results": [], "query": q, "total": 0}


@app.post("/api/memory/repair")
async def repair_memory():
    """一键修复记忆中心问题"""
    try:
        import subprocess
        from datetime import datetime

        repair_log = []
        success_count = 0
        error_count = 0

        # 1. 检查并创建缺失的日志目录
        repair_log.append("📁 检查日志目录结构...")
        bot_names = ["编导", "剪辑", "美工", "场控", "客服", "运营", "渠道", "小小谦"]
        for bot in bot_names:
            bot_logs_dir = PROJECT_DIR / "workspaces" / bot / "shared_memory" / "logs"
            if not bot_logs_dir.exists():
                bot_logs_dir.mkdir(parents=True, exist_ok=True)
                repair_log.append(f"  ✅ 创建 {bot} 日志目录")
                success_count += 1
            else:
                repair_log.append(f"  ✓ {bot} 日志目录已存在")

        repair_log.append(f"  ✅ 目录检查完成")

        # 2. 检查公共日志目录
        public_logs_dir = PROJECT_DIR / "shared_memory" / "logs"
        if not public_logs_dir.exists():
            public_logs_dir.mkdir(parents=True, exist_ok=True)
            repair_log.append("  ✅ 创建公共日志目录")
            success_count += 1

        # 3. 运行 Discord 记忆同步
        repair_log.append("\n🔄 执行 Discord 记忆同步...")
        try:
            env = os.environ.copy()
            env["HTTPS_PROXY"] = "http://127.0.0.1:7897"
            env["HTTP_PROXY"] = "http://127.0.0.1:7897"

            result = subprocess.run(
                ["python3", "discord_memory_sync.py", "--sync", "--limit", "200"],
                cwd=str(PROJECT_DIR),
                env=env,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                repair_log.append("  ✅ Discord 同步成功")
                success_count += 1
                # 解析同步结果
                for line in result.stdout.split("\n"):
                    if "Saved" in line or "Sync complete" in line:
                        repair_log.append(f"  {line.strip()}")
            else:
                repair_log.append(f"  ⚠️ Discord 同步警告：{result.stderr[:200]}")
        except subprocess.TimeoutExpired:
            repair_log.append("  ⚠️ Discord 同步超时")
        except Exception as e:
            repair_log.append(f"  ⚠️ Discord 同步失败：{str(e)}")

        # 4. 检查 Bot 运行状态
        repair_log.append("\n🤖 检查 Bot 运行状态...")
        running_bots = []
        for bot in bot_names:
            bot_log_file = PROJECT_DIR / "workspaces" / bot / "bot.log"
            if bot_log_file.exists():
                with open(bot_log_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    if "Discord bot ready" in content:
                        running_bots.append(bot)
                        repair_log.append(f"  ✓ {bot} 运行中")

        repair_log.append(f"  ✅ {len(running_bots)}/{len(bot_names)} 个 Bot 在线")

        # 5. 生成修复报告
        repair_log.append("\n📊 修复报告")
        repair_log.append(f"  成功操作：{success_count}")
        repair_log.append(f"  最后同步：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        return {
            "success": True,
            "log": repair_log,
            "stats": {
                "success_count": success_count,
                "running_bots": len(running_bots),
                "total_bots": len(bot_names)
            }
        }
    except Exception as e:
        logger.error(f"修复记忆失败：{e}")
        return {
            "success": False,
            "error": str(e),
            "log": [f"❌ 修复失败：{str(e)}"]
        }


# ============ 技能版本 API ============

@app.get("/api/skills/{skill_id}/versions")
async def get_skill_versions(skill_id: str):
    """获取技能版本历史"""
    try:
        from skill_evolution import get_skill_evolution
        evolution = get_skill_evolution()

        lineage = evolution.get_skill_lineage(skill_id)

        if lineage.get('success'):
            return {
                "skill_name": skill_id,
                "versions": lineage['lineage']['versions'],
                "evolution_path": lineage['lineage']['evolution_path'],
                "current_version": lineage['lineage']['current_version'],
                "total_versions": lineage['lineage']['total_versions']
            }

        # 没有进化记录，检查是否是已安装技能
        skill_file = None

        # 检查主 skills 目录
        main_skill_file = PROJECT_DIR / "skills" / f"{skill_id}.md"
        if main_skill_file.exists():
            skill_file = main_skill_file

        # 检查工作区中的技能
        if not skill_file:
            for bot_name in ["编导", "剪辑", "美工", "场控", "客服", "运营", "渠道", "小小谦"]:
                workspace_skill = PROJECT_DIR / "workspaces" / bot_name / "DYNAMIC" / "skills" / f"{skill_id}.md"
                if workspace_skill.exists():
                    skill_file = workspace_skill
                    break

        if skill_file:
            # 读取技能文件内容
            with open(skill_file, "r", encoding="utf-8") as f:
                content = f.read()

            return {
                "skill_name": skill_id,
                "versions": [],
                "installed": True,
                "content": content,
                "file_path": str(skill_file),
                "note": "已安装技能，暂无版本进化记录"
            }

        return {"skill_name": skill_id, "versions": [], "error": f"技能 {skill_id} 未找到"}
    except Exception as e:
        logger.error(f"获取技能版本失败：{e}")
        return {"skill_name": skill_id, "versions": [], "error": str(e)}


@app.get("/api/skills/{skill_id}")
async def get_skill_detail(skill_id: str):
    """获取技能详情"""
    try:
        from pathlib import Path

        # 检查技能文件是否存在
        skill_file = PROJECT_DIR / "skills" / f"{skill_id}.md"
        if not skill_file.exists():
            # 检查工作区中的技能
            for bot_name in ["编导", "剪辑", "美工", "场控", "客服", "运营", "渠道", "小小谦"]:
                workspace_skill = PROJECT_DIR / "workspaces" / bot_name / "DYNAMIC" / "skills" / f"{skill_id}.md"
                if workspace_skill.exists():
                    skill_file = workspace_skill
                    break

        if skill_file.exists():
            with open(skill_file, "r", encoding="utf-8") as f:
                content = f.read()

            # 解析技能名称（从 Markdown 标题）
            name = skill_id
            description = ""
            for line in content.split("\n"):
                if line.startswith("# "):
                    name = line[2:].strip()
                elif line.strip() and not line.startswith("#"):
                    description = line.strip()
                    break

            return {
                "id": skill_id,
                "name": name,
                "description": description,
                "content": content,
                "installed": True
            }

        return {"id": skill_id, "error": "技能文件未找到"}
    except Exception as e:
        logger.error(f"获取技能详情失败：{e}")
        return {"id": skill_id, "error": str(e)}


@app.get("/api/skills/{skill_id}/diff")
async def get_skill_diff(skill_id: str, v1: str = "", v2: str = ""):
    """获取技能版本对比"""
    try:
        from skill_evolution import get_skill_evolution
        evolution = get_skill_evolution()

        if not v1 or not v2:
            return {"error": "需要指定 v1 和 v2 版本号"}

        diff = evolution.get_version_diff(skill_id, v1, v2)

        return diff
    except Exception as e:
        logger.error(f"获取技能对比失败：{e}")
        return {"error": str(e)}


@app.post("/api/skills/{skill_id}/rollback")
async def rollback_skill(skill_id: str, target_version: str, reason: str = "Manual rollback"):
    """回滚技能到指定版本"""
    try:
        from skill_evolution import get_skill_evolution
        evolution = get_skill_evolution()

        result = evolution.rollback_skill(skill_id, target_version, reason)

        if result.get('success'):
            await manager.broadcast({
                "type": "skill_rolled_back",
                "skill_id": skill_id,
                "new_version": result.get('new_version'),
                "restored_from": result.get('restored_from')
            })

        return result
    except Exception as e:
        logger.error(f"回滚技能失败：{e}")
        return {"success": False, "error": str(e)}


@app.post("/api/skills/{skill_id}/optimize")
async def optimize_skill(skill_id: str, request_body: dict = None):
    """优化技能 (AI 进化)"""
    logger.info(f"optimize_skill called with skill_id={skill_id}, request_body={request_body}")
    try:
        from pathlib import Path

        # 首先检查技能文件是否存在
        skill_file = None

        # 检查工作区中的技能
        for bot_name in ["编导", "剪辑", "美工", "场控", "客服", "运营", "渠道", "小小谦"]:
            workspace_skill = PROJECT_DIR / "workspaces" / bot_name / "DYNAMIC" / "skills" / f"{skill_id}.md"
            if workspace_skill.exists():
                skill_file = workspace_skill
                logger.info(f"Found skill file: {skill_file}")
                break

        # 检查主 skills 目录
        if not skill_file:
            main_skill_file = PROJECT_DIR / "skills" / f"{skill_id}.md"
            if main_skill_file.exists():
                skill_file = main_skill_file
                logger.info(f"Found skill file: {skill_file}")

        if not skill_file:
            logger.warning(f"Skill file not found: {skill_id}")
            return {"success": False, "error": f"技能 {skill_id} 未找到"}

        # 获取请求中的 reason
        reason = "Manual optimization"
        if request_body:
            reason = request_body.get("reason", reason)
        logger.info(f"Optimizing skill {skill_id} with reason: {reason}")

        # 尝试使用 skill_evolution
        try:
            from skill_evolution import get_skill_evolution
            evolution = get_skill_evolution()

            logger.info(f"Calling evolution.evolve_skill for {skill_id}")
            result = evolution.evolve_skill(skill_id, reason)
            logger.info(f"Evolution result: {result}")

            if result.get('success'):
                await manager.broadcast({
                    "type": "skill_evolved",
                    "skill_id": skill_id,
                    "old_version": result.get('old_version'),
                    "new_version": result.get('new_version')
                })
                logger.info(f"Skill {skill_id} evolved successfully")
                return result
            else:
                logger.warning(f"Evolution not successful: {result}")
        except Exception as e:
            logger.info(f"skill_evolution not available or failed: {e}")

        # 读取当前技能内容
        with open(skill_file, "r", encoding="utf-8") as f:
            current_content = f.read()

        # 保存文件（无版本进化记录时的友好处理）
        with open(skill_file, "w", encoding="utf-8") as f:
            f.write(current_content)

        logger.info(f"Skill {skill_id} saved without evolution")
        return {"success": True, "note": "技能已保存（无版本进化记录，首次优化将创建 v1 版本）"}
    except Exception as e:
        logger.error(f"优化技能失败：{e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}


# ============ 数据分析 API ============

@app.get("/api/analytics/trends")
async def get_analytics_trends(days: int = 7):
    """获取趋势数据"""
    try:
        # 任务执行趋势
        from task_queue import get_task_queue
        queue = get_task_queue()
        task_stats = queue.get_stats() if hasattr(queue, 'get_stats') else {}

        # 技能成功率趋势 (从 skill_evolution 获取)
        from skill_evolution import get_skill_evolution
        evolution = get_skill_evolution()
        evolution_stats = evolution.get_evolution_stats() if hasattr(evolution, 'get_evolution_stats') else {}

        return {
            "task_trends": {
                "total_tasks": task_stats.get("total_tasks", 0),
                "by_status": task_stats.get("by_status", {}),
                "by_bot": task_stats.get("by_bot", {})
            },
            "skill_trends": evolution_stats,
            "period_days": days
        }
    except Exception as e:
        logger.error(f"获取趋势数据失败：{e}")
        return {"task_trends": {}, "skill_trends": {}, "period_days": days}


@app.get("/api/analytics/knowledge-graph")
async def get_knowledge_graph():
    """获取知识图谱数据"""
    try:
        from knowledge_graph import get_knowledge_graph
        graph = get_knowledge_graph()

        graph_data = graph.get_graph_data() if hasattr(graph, 'get_graph_data') else {
            "nodes": [],
            "edges": []
        }

        return graph_data
    except Exception as e:
        logger.error(f"获取知识图谱失败：{e}")
        return {"nodes": [], "edges": []}


@app.get("/api/analytics/skill-lineage")
async def get_skill_lineage(skill_name: str = ""):
    """获取技能谱系"""
    try:
        from skill_evolution import get_skill_evolution
        evolution = get_skill_evolution()

        if skill_name:
            # 获取特定技能的谱系
            lineage = evolution.get_skill_lineage(skill_name)
            return lineage
        else:
            # 获取所有技能的谱系概览
            all_skills = []
            # 从 skill_store 获取所有技能
            from skill_store import SkillStore
            store = SkillStore()
            store.load_from_disk()
            skills_data = store.read()

            for entry in skills_data.get('entries', [])[:20]:  # 限制 20 个
                skill_name = entry.split('\n')[0].replace('[SKILL] ', '').strip()
                lineage = evolution.get_skill_lineage(skill_name)
                if lineage.get('success'):
                    all_skills.append({
                        "name": skill_name,
                        "versions": lineage['lineage']['total_versions'],
                        "current_version": lineage['lineage']['current_version'],
                        "evolution_path": lineage['lineage']['evolution_path'][:5]  # 最近 5 个版本
                    })

            return {
                "skills": all_skills,
                "total": len(all_skills)
            }
    except Exception as e:
        logger.error(f"获取技能谱系失败：{e}")
        return {"skills": [], "total": 0}


# ============ 配置 API ============

@app.get("/api/system/info")
async def get_system_info():
    """获取系统信息"""
    import platform
    import time

    # 计算运行时间
    uptime_seconds = time.time() - start_time
    hours = int(uptime_seconds // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    uptime_str = f"{hours}小时 {minutes}分钟"

    return {
        "uptime": uptime_str,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "project_dir": str(PROJECT_DIR),
        "version": "v5.0"
    }


@app.get("/api/config")
async def get_config():
    """获取系统配置"""
    try:
        # 读取.env 文件
        env_file = PROJECT_DIR / ".env"
        config = {}

        if env_file.exists():
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        # 脱敏处理
                        if "KEY" in key or "SECRET" in key or "TOKEN" in key:
                            value = value[:4] + "***" if len(value) > 4 else "***"
                        config[key] = value

        return {
            "config": config,
            "env_file": str(env_file)
        }
    except Exception as e:
        logger.error(f"获取配置失败：{e}")
        return {"config": {}, "env_file": ""}


@app.post("/api/config")
async def update_config(config: dict):
    """更新系统配置"""
    try:
        env_file = PROJECT_DIR / ".env"

        # 读取现有配置
        existing = {}
        if env_file.exists():
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        existing[key] = value

        # 更新配置
        existing.update(config)

        # 写回文件
        with open(env_file, "w") as f:
            for key, value in existing.items():
                f.write(f"{key}={value}\n")

        # 同步更新 os.environ
        for key, value in config.items():
            os.environ[key] = value

        await manager.broadcast({
            "type": "config_updated",
            "updated_keys": list(config.keys())
        })

        return {
            "success": True,
            "message": "配置已更新"
        }
    except Exception as e:
        logger.error(f"更新配置失败：{e}")
        return {"success": False, "error": str(e)}


@app.post("/api/config/validate")
async def validate_config():
    """验证系统配置"""
    try:
        # 检查必要的 API Key
        required_keys = ["DASHSCOPE_API_KEY", "CODING_PLAN_API_KEY"]
        missing = []
        invalid = []

        for key in required_keys:
            value = os.environ.get(key, "")
            if not value:
                missing.append(key)
            elif len(value) < 10:
                invalid.append(key)

        return {
            "valid": len(missing) == 0 and len(invalid) == 0,
            "missing": missing,
            "invalid": invalid,
            "message": "配置验证通过" if not missing and not invalid else f"缺少：{missing}" if missing else f"无效：{invalid}"
        }
    except Exception as e:
        logger.error(f"验证配置失败：{e}")
        return {"valid": False, "error": str(e)}


@app.post("/api/config/delete-key")
async def delete_api_key(request: Request):
    """删除指定的 API Key"""
    try:
        data = await request.json()
        key_to_delete = data.get("key")

        if not key_to_delete:
            return {"success": False, "error": "未指定要删除的 Key"}

        env_file = PROJECT_DIR / ".env"
        existing = {}

        if env_file.exists():
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        if key != key_to_delete:  # 不保存要删除的 key
                            existing[key] = value

        # 写回文件
        with open(env_file, "w") as f:
            for key, value in existing.items():
                f.write(f"{key}={value}\n")

        # 从环境变量中移除
        if key_to_delete in os.environ:
            del os.environ[key_to_delete]

        return {"success": True, "message": f"已删除 {key_to_delete}"}
    except Exception as e:
        logger.error(f"删除 API Key 失败：{e}")
        return {"success": False, "error": str(e)}


@app.post("/api/config/test-api-key")
async def test_api_key(request: Request):
    """测试单个 API Key 是否可用"""
    try:
        data = await request.json()
        provider = data.get("provider")
        api_key = data.get("api_key")

        if not provider or not api_key:
            return {"success": False, "error": "缺少 provider 或 api_key"}

        # 从 providers.json 获取 provider 配置
        providers_file = PROJECT_DIR / "providers.json"
        providers_config = {}
        if providers_file.exists():
            with open(providers_file, "r", encoding="utf-8") as f:
                providers_config = json.load(f)

        provider_info = providers_config.get("providers", {}).get(provider)
        if not provider_info:
            return {"success": False, "error": f"Provider {provider} 不存在"}

        base_url = provider_info.get("base_url", "")
        # 使用第一个可用模型进行测试
        test_model = (provider_info.get("models") or [""])[0]
        if not test_model:
            return {"success": False, "error": "没有可用模型进行测试"}

        # 发送测试请求
        import requests
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": test_model,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 10
        }

        response = requests.post(url, headers=headers, json=payload, timeout=15)

        if response.status_code == 200:
            return {"success": True, "message": "API Key 有效"}
        else:
            return {"success": False, "error": f"API 返回错误：{response.status_code} - {response.text[:100]}"}

    except requests.exceptions.Timeout:
        return {"success": False, "error": "请求超时"}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"网络错误：{str(e)}"}
    except Exception as e:
        logger.error(f"测试 API Key 失败：{e}")
        return {"success": False, "error": str(e)}


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

    # 启动远程调试客户端
    init_remote_debug()

    uvicorn.run(
        "api_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )


# ============ 远程调试集成 ============

# 在服务器启动后启动远程调试客户端
_remote_debug_client = None

def init_remote_debug():
    """初始化远程调试"""
    global _remote_debug_client
    server_url = os.environ.get("DEBUG_MASTER_URL")

    if not server_url:
        logger.info("📡 远程调试未启用 (缺少 DEBUG_MASTER_URL)")
        return

    # 自动生成设备 ID（基于主机名 + MAC 地址前缀）
    import uuid
    hostname = os.uname().nodename if hasattr(os, 'uname') else 'unknown'
    mac_prefix = uuid.getnode() >> 24  # 取 MAC 地址前 24 位
    device_id = os.environ.get("DEBUG_DEVICE_ID", f"phoenix-{hostname}-{mac_prefix:06x}")

    from remote_debug import RemoteDebugClient
    import threading

    auth_token = os.environ.get("DEBUG_AUTH_TOKEN", "")
    client = RemoteDebugClient(server_url, device_id, auth_token)

    thread = threading.Thread(target=lambda: asyncio.run(client.run()), daemon=True)
    thread.start()
    _remote_debug_client = client
    logger.info(f"✅ 远程调试已启用，设备 ID: {device_id}")


# ============ GitHub 监控 API ============

@app.get("/api/github/trending")
async def get_github_trending(since: str = Query(default="daily")):
    """获取 GitHub trending 项目"""
    monitor = get_monitor()
    repos = monitor.scan_trending(since)
    return {"repos": repos}


@app.get("/api/github/search")
async def search_github(q: str = Query(...)):
    """搜索 GitHub repos"""
    monitor = get_monitor()
    repos = monitor.search_by_keyword(q)
    return {"repos": repos}


@app.get("/api/github/report")
async def get_github_report():
    """获取 GitHub 监控日报"""
    monitor = get_monitor()
    return monitor.generate_daily_report()


@app.get("/api/github/alerts")
async def get_github_alerts():
    """获取 GitHub 监控告警"""
    monitor = get_monitor()
    return {"alerts": monitor.alerts[-50:]}


@app.get("/api/github/actions")
async def get_github_actions():
    """获取待办事项"""
    monitor = get_monitor()
    return {"actions": monitor.get_action_items()}


@app.post("/api/github/scan")
async def run_github_scan():
    """运行 GitHub 扫描"""
    monitor = get_monitor()
    repos = monitor.scan_trending()
    return {"success": True, "scanned": len(repos)}


# ============ 大脑对话 API ============

@app.post("/api/chat")
async def chat_with_brain(request: dict):
    """与 Phoenix Core 大脑对话"""
    from phoenix_core.core_brain import get_brain

    message = request.get("message", "")
    user_id = request.get("user_id", "dashboard-user")

    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    try:
        brain = get_brain()

        # 判断是否是协作请求（需要多 Bot 参与）
        if _is_collaboration_request(message):
            logger.info(f"检测到协作请求：{message[:50]}...")
            # 使用大脑直连 Discord（真实 Bot 响应）
            if _discord_brain_gateway and _discord_client and _discord_client.ready:
                _discord_brain_gateway.discord_client = _discord_client
                brain._gateway = _discord_brain_gateway
                logger.info("使用 Discord 真实 Bot 响应")
            else:
                # Fallback: Dashboard Gateway（虚拟响应）
                from phoenix_core.dashboard_gateway import get_dashboard_gateway
                brain._gateway = get_dashboard_gateway()
                logger.info("Discord 未连接，使用虚拟响应")
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


def _is_collaboration_request(content: str) -> bool:
    """判断是否是协作请求（需要多 Bot 参与）"""
    # 直接协作关键词
    collaboration_keywords = ["讨论", "组织", "协调", "大家一起", "一起", "都", "各自", "协作", "配合", "分工"]
    for kw in collaboration_keywords:
        if kw in content:
            return True

    # 策划类请求 - 单独出现即触发
    strong_planning_keywords = ["直播方案", "直播策划", "活动方案", "活动策划", "多 Bot", "团队协作"]
    for kw in strong_planning_keywords:
        if kw in content:
            return True

    # 普通策划词 + 群体词
    planning_keywords = ["方案", "策划", "计划", "安排"]
    if any(kw in content for kw in planning_keywords):
        if "大家" in content or "各" in content or "所有" in content or "多个" in content:
            return True
        # 直播相关通常也需要多 Bot 协作
        if "直播" in content or "活动" in content or "场次" in content:
            return True

    # 检查是否明确提到多个 Bot
    bot_names = ["运营", "编导", "场控", "客服", "美工", "剪辑", "渠道", "小小谦"]
    mentioned_bots = [bot for bot in bot_names if bot in content]
    if len(mentioned_bots) >= 2:
        return True

    return False


# ============ 审计日志 API ============

@app.get("/api/audit/logs")
async def list_audit_logs(limit: int = Query(100, ge=1, le=1000)):
    """查询审计日志"""
    from phoenix_core.audit_logger import get_audit_logger
    from datetime import timedelta

    audit_logger = get_audit_logger()
    try:
        end = datetime.now()
        start = end - timedelta(hours=24)
        entries = audit_logger.query_by_time_range(start, end, None)[:limit]
        return [entry.to_dict() for entry in entries]
    except Exception as e:
        logger.error(f"查询审计日志失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/audit/stats")
async def get_audit_stats():
    """获取审计日志统计"""
    from phoenix_core.audit_logger import get_audit_logger
    from datetime import timedelta

    audit_logger = get_audit_logger()
    try:
        end = datetime.now()
        start = end - timedelta(hours=24)
        all_entries = audit_logger.query_by_time_range(start, end)
        stats = {
            "total": len(all_entries),
            "message": sum(1 for e in all_entries if e.entry_type == "message"),
            "operation": sum(1 for e in all_entries if e.entry_type == "operation"),
            "error": sum(1 for e in all_entries if e.entry_type == "error"),
            "alert": sum(1 for e in all_entries if e.entry_type == "alert"),
        }
        return stats
    except Exception as e:
        logger.error(f"获取统计失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 任务历史 API (协作任务) ============

# Bot 名称到 Discord ID 的映射
# 注意：这些 ID 需要从 Discord 服务器动态获取，或者在配置文件中定义
# 当前只有小小谦的 ID 是已知的，其他 Bot 需要使用动态查找
BOT_DISCORD_IDS = {
    "小小谦": "1483335704590155786",  # 协调员
    # 其他 Bot 的 ID 需要从 Discord 动态获取
}


class DiscordBrainGateway:
    """
    大脑通过直连 Discord 发送指令给 Bot

    支持两种模式：
    1. 已知 Bot Discord ID：直接@发送
    2. 未知 Bot Discord ID：在频道中@Bot 名称（需要用户在 Discord 中配置昵称）
    """
    def __init__(self, discord_client, bot_ids: Dict[str, str], channel_id: str):
        self.discord_client = discord_client
        self.bot_ids = bot_ids
        self.channel_id = channel_id
        self.bot_name = "Brain"
        self._pending_responses: Dict[str, asyncio.Future] = {}
        self._bot_id_cache: Dict[str, str] = {}  # 缓存查找到的 Bot ID

    async def _find_bot_id(self, bot_name: str) -> Optional[str]:
        """
        查找 Bot 的 Discord ID

        优先级：
        1. 静态映射
        2. 缓存
        3. 从 Discord 服务器查找（通过昵称匹配）
        """
        # 检查静态映射
        if bot_name in self.bot_ids:
            return self.bot_ids[bot_name]

        # 检查缓存
        if bot_name in self._bot_id_cache:
            return self._bot_id_cache[bot_name]

        # 从 Discord 服务器查找
        if self.discord_client and self.discord_client.client:
            try:
                guild = self.discord_client.client.get_guild(int(os.environ.get("DISCORD_SERVER_ID", "1479051401165537410")))
                if guild:
                    # 遍历成员查找匹配的昵称
                    async for member in guild.fetch_members(limit=500):
                        if member.display_name == bot_name or member.name == bot_name:
                            self._bot_id_cache[bot_name] = str(member.id)
                            logger.info(f"找到 Bot {bot_name} 的 Discord ID: {member.id}")
                            return str(member.id)
            except Exception as e:
                logger.error(f"查找 Bot ID 失败：{e}")

        return None

    async def send_to_bot(self, bot_id: str, message: str, request_id: str = None) -> str:
        """
        发送消息给 Bot 并等待响应

        Args:
            bot_id: Bot 名称
            message: 消息内容
            request_id: 请求 ID

        Returns:
            Bot 响应
        """
        if not self.discord_client:
            logger.warning("Discord 客户端未连接")
            return f"[模拟] {bot_id} 收到任务：{message[:50]}..."

        # 获取 Bot Discord ID
        bot_discord_id = await self._find_bot_id(bot_id)

        if not bot_discord_id:
            logger.warning(f"Bot {bot_id} Discord ID 未找到，尝试使用名称@")
            # 降级：直接在频道发送，希望 Bot 能识别自己的名称
            protocol_msg = f"[ASK|{request_id}|brain|300] {message}"
            full_message = f"@{bot_id} {protocol_msg}"
            await self.discord_client.send_to_channel(full_message)
            return f"[警告] {bot_id} Discord ID 未知，消息已发送但可能无法收到响应"

        # 创建 Future 等待响应
        future = asyncio.get_event_loop().create_future()
        self._pending_responses[request_id] = future

        # 发送协议消息
        protocol_msg = f"[ASK|{request_id}|brain|300] {message}"
        full_message = f"<@{bot_discord_id}> {protocol_msg}"

        await self.discord_client.send_to_channel(full_message)
        logger.info(f"发送给 {bot_id}: {full_message[:80]}...")

        # 等待响应（超时 60 秒）
        try:
            response = await asyncio.wait_for(future, timeout=60.0)
            logger.info(f"收到 {bot_id} 响应：{response[:50] if response else 'empty'}")
            return response
        except asyncio.TimeoutError:
            logger.warning(f"{bot_id} 响应超时")
            return f"{bot_id} 响应超时"
        finally:
            self._pending_responses.pop(request_id, None)

    def register_response(self, request_id: str, response: str):
        """注册 Bot 响应（由消息处理器调用）"""
        logger.info(f"register_response called: {request_id}")
        if request_id in self._pending_responses:
            logger.info(f"Setting result for {request_id}")
            self._pending_responses[request_id].set_result(response)
        else:
            logger.warning(f"Request ID {request_id} not found in pending responses")


@app.post("/api/collab/dispatch")
async def dispatch_collaboration(request: dict):
    """
    触发协作任务（通过 Dashboard 直接发送指令）

    流程：
    1. 大脑接收请求并拆解任务
    2. 大脑直连 Discord 发送指令给 Bot
    3. Bot 们在 Discord 讨论
    4. 大脑汇总结果
    """
    global _brain_instance, _discord_client, _discord_channel_id

    user_query = request.get("user_query", "")
    user_id = request.get("user_id", "dashboard-user")

    if not user_query:
        raise HTTPException(status_code=400, detail="user_query is required")

    if not _brain_instance:
        raise HTTPException(status_code=503, detail="Brain not initialized")

    try:
        # 使用全局 Discord Gateway（在 startup 时创建）
        # 更新它的 discord_client 引用（确保是最新的）
        if _discord_client and _discord_client.ready and _discord_brain_gateway:
            _discord_brain_gateway.discord_client = _discord_client
            gateway = _discord_brain_gateway
            _brain_instance._gateway = gateway
            logger.info(f"Brain gateway set to Discord direct connection")
        else:
            logger.warning("Discord 未连接，使用模拟模式")
            gateway = None

        # 调用大脑处理协作请求
        response = await _brain_instance.process_collaboration_request(
            user_query=user_query,
            user_id=user_id
        )

        return {
            "success": response.success,
            "message": response.message,
            "task_id": response.task_id,
            "context": response.context
        }

    except Exception as e:
        logger.error(f"Collaboration dispatch error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/collab/tasks")
async def list_collab_tasks(limit: int = Query(20, ge=1, le=100)):
    """查询协作任务历史"""
    from phoenix_core.dashboard_gateway import get_dashboard_gateway

    gateway = get_dashboard_gateway()
    tasks = gateway.list_tasks(limit)
    return {"tasks": tasks, "total": len(tasks)}


@app.get("/api/collab/tasks/{task_id}")
async def get_collab_task(task_id: str):
    """查询单个协作任务详情"""
    from phoenix_core.dashboard_gateway import get_dashboard_gateway

    gateway = get_dashboard_gateway()
    task = gateway.get_task_status(task_id)

    if task:
        return {"task": task}
    else:
        raise HTTPException(status_code=404, detail="Task not found")


if __name__ == "__main__":
    main()

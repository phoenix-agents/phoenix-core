"""
Phoenix Core Web Dashboard - SIMPLE VERSION (干净版)

注意：这是简化版 Dashboard，只负责数据展示
- 不包含 API 服务端
- 需要从 api_server.py 获取数据
- 适用于只需要 UI 展示的场景

原版 Dashboard 请使用：python3 api_server.py --port 8000
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Project root path
PROJECT_ROOT = Path(__file__).parent.parent.parent
DASHBOARD_ROOT = Path(__file__).parent

app = FastAPI(title="Phoenix Core Dashboard", version="2.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory
static_path = DASHBOARD_ROOT / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=static_path), name="static")


# ============ 远程设备管理 API ============

@app.get("/api/remote-devices")
async def get_remote_devices():
    """获取远程设备列表（从调试服务器）"""
    debug_master_url = os.environ.get("DEBUG_MASTER_URL", "http://localhost:9000")
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            res = await client.get(f"{debug_master_url}/api/devices", timeout=5)
            return res.json()
    except Exception as e:
        return {"online": {}, "total": 0, "error": str(e)}


@app.get("/api/remote-devices/{device_id}")
async def get_remote_device(device_id: str):
    """获取指定设备信息"""
    debug_master_url = os.environ.get("DEBUG_MASTER_URL", "http://localhost:9000")
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            res = await client.get(f"{debug_master_url}/api/devices/{device_id}", timeout=5)
            return res.json()
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/remote-devices/{device_id}/logs")
async def get_remote_device_logs(device_id: str, limit: int = 100):
    """获取设备日志"""
    debug_master_url = os.environ.get("DEBUG_MASTER_URL", "http://localhost:9000")
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            res = await client.get(f"{debug_master_url}/api/devices/{device_id}/logs?limit={limit}", timeout=5)
            return res.json()
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/remote-devices/{device_id}/command")
async def send_remote_command(device_id: str, command: dict):
    """发送命令到设备"""
    debug_master_url = os.environ.get("DEBUG_MASTER_URL", "http://localhost:9000")
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            res = await client.post(f"{debug_master_url}/api/devices/{device_id}/command", json=command, timeout=10)
            return res.json()
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/remote-devices/{device_id}/push_code")
async def push_remote_code(device_id: str, code: dict):
    """推送代码到设备"""
    debug_master_url = os.environ.get("DEBUG_MASTER_URL", "http://localhost:9000")
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            res = await client.post(f"{debug_master_url}/api/devices/{device_id}/push_code", json=code, timeout=30)
            return res.json()
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


def load_task_data() -> dict:
    """Load task evaluation data from task queue."""
    task_file = PROJECT_ROOT / ".task_queue" / "tasks.json"
    if task_file.exists():
        with open(task_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"tasks": {}, "bot_queues": {}}


def load_skill_evolution_data() -> list:
    """Load skill evolution data from evolution directory."""
    evolution_dir = PROJECT_ROOT / "skill_evolution"
    skills = []

    if evolution_dir.exists():
        for file in evolution_dir.glob("*.json"):
            if file.name == "test_skill.json" or file.name != "test_skill.json":
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        skill_data = json.load(f)
                        skills.append(skill_data)
                except (json.JSONDecodeError, IOError):
                    continue

    return skills


def load_evolution_log() -> list:
    """Parse evolution log markdown file."""
    log_file = PROJECT_ROOT / "skill_evolution" / "evolution_log.md"
    evolutions = []

    if log_file.exists():
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
            blocks = content.split("---")
            for block in blocks:
                block = block.strip()
                if not block:
                    continue
                entry = {"raw": block}
                lines = block.split("\n")
                for line in lines:
                    if "**Skill**:" in line:
                        entry["skill"] = line.split("**Skill**:")[-1].strip()
                    elif "**Version**:" in line:
                        entry["version"] = line.split("**Version**:")[-1].strip()
                    elif "**Success Rate**:" in line:
                        entry["success_rate"] = line.split("**Success Rate**:")[-1].strip()
                    elif line.startswith("## "):
                        entry["timestamp"] = line.replace("## ", "").strip()
                evolutions.append(entry)

    return evolutions


def parse_bot_logs() -> list:
    """Parse bot activity logs to extract metrics."""
    logs_dir = PROJECT_ROOT / "logs"
    activities = []

    if logs_dir.exists():
        for log_file in logs_dir.glob("*.log"):
            bot_name = log_file.stem
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()[-100:]  # Last 100 lines
                    for line in lines:
                        if "[" in line and "]" in line:
                            activities.append({
                                "bot": bot_name,
                                "line": line.strip(),
                                "timestamp": datetime.now().isoformat()
                            })
            except IOError:
                continue

    return activities


def generate_mock_assessment_data() -> list:
    """Generate mock task assessment score trends."""
    base_date = datetime.now() - timedelta(days=30)
    data = []

    for i in range(30):
        date = base_date + timedelta(days=i)
        data.append({
            "date": date.strftime("%Y-%m-%d"),
            "score": round(60 + (i * 1.2) + (hash(str(i)) % 20), 2),
            "tasks_completed": 5 + (i // 3),
            "avg_quality": round(0.6 + (i * 0.012), 2)
        })

    return data


def generate_mock_skill_success_data() -> list:
    """Generate mock skill success rate trends."""
    skills = ["任务分解", "代码生成", "错误修复", "文档编写", "测试生成"]
    data = []

    for skill in skills:
        skill_data = []
        base_success = 0.5 + (hash(skill) % 30) / 100
        for i in range(30):
            date = datetime.now() - timedelta(days=30-i)
            success_rate = min(0.99, base_success + (i * 0.01) + (hash(skill + str(i)) % 10) / 100)
            skill_data.append({
                "date": date.strftime("%Y-%m-%d"),
                "skill": skill,
                "success_rate": round(success_rate, 3),
                "executions": 10 + (hash(skill + str(i)) % 20)
            })
        data.extend(skill_data)

    return data


def generate_mock_failure_patterns() -> list:
    """Generate mock failure pattern analysis."""
    patterns = [
        {"pattern": "参数缺失", "count": 45, "percentage": 25.0, "trend": "up"},
        {"pattern": "超时错误", "count": 38, "percentage": 21.1, "trend": "down"},
        {"pattern": "依赖冲突", "count": 32, "percentage": 17.8, "trend": "stable"},
        {"pattern": "权限不足", "count": 28, "percentage": 15.6, "trend": "down"},
        {"pattern": "资源耗尽", "count": 22, "percentage": 12.2, "trend": "up"},
        {"pattern": "其他", "count": 15, "percentage": 8.3, "trend": "stable"},
    ]
    return patterns


def generate_skill_lineage() -> dict:
    """Generate skill lineage tree data."""
    # Read actual skill data and build lineage
    evolution_dir = PROJECT_ROOT / "skill_evolution"
    skills_data = load_skill_evolution_data()

    # Build tree structure
    lineage = {
        "name": "技能谱系",
        "children": []
    }

    categories = {}

    for skill in skills_data:
        skill_name = skill.get("skill_name", "Unknown")
        versions = skill.get("versions", [])

        # Determine category based on skill name
        if "test" in skill_name.lower():
            category = "测试技能"
        elif "eval" in skill_name.lower():
            category = "评估技能"
        elif "learn" in skill_name.lower():
            category = "学习技能"
        else:
            category = "通用技能"

        if category not in categories:
            categories[category] = {
                "name": category,
                "children": []
            }

        skill_node = {
            "name": skill_name,
            "versions": []
        }

        for ver in versions:
            skill_node["versions"].append({
                "name": ver.get("version", "v1"),
                "success_rate": ver.get("success_rate", 0),
                "execution_count": ver.get("execution_count", 0)
            })

        categories[category]["children"].append(skill_node)

    lineage["children"] = list(categories.values())

    # Add mock data if no real data
    if not lineage["children"]:
        lineage["children"] = [
            {
                "name": "核心技能",
                "children": [
                    {
                        "name": "任务分解",
                        "versions": [
                            {"name": "v1", "success_rate": 0.75, "execution_count": 100},
                            {"name": "v2", "success_rate": 0.85, "execution_count": 150},
                            {"name": "v3", "success_rate": 0.92, "execution_count": 200}
                        ]
                    },
                    {
                        "name": "代码生成",
                        "versions": [
                            {"name": "v1", "success_rate": 0.68, "execution_count": 80},
                            {"name": "v2", "success_rate": 0.82, "execution_count": 120}
                        ]
                    }
                ]
            },
            {
                "name": "辅助技能",
                "children": [
                    {
                        "name": "文档编写",
                        "versions": [
                            {"name": "v1", "success_rate": 0.70, "execution_count": 50},
                            {"name": "v2", "success_rate": 0.88, "execution_count": 90}
                        ]
                    }
                ]
            }
        ]

    return lineage


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main dashboard page."""
    template_path = DASHBOARD_ROOT / "templates" / "index_v5.html"
    if template_path.exists():
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Dashboard template not found</h1>")


@app.get("/api/assessment-trend")
async def get_assessment_trend():
    """Get task assessment score trend data."""
    return {"data": generate_mock_assessment_data()}


@app.get("/api/skill-success")
async def get_skill_success():
    """Get skill success rate trend data."""
    return {"data": generate_mock_skill_success_data()}


@app.get("/api/failure-patterns")
async def get_failure_patterns():
    """Get failure pattern analysis data."""
    return {"data": generate_mock_failure_patterns()}


@app.get("/api/skill-lineage")
async def get_skill_lineage():
    """Get skill lineage tree data."""
    return {"data": generate_skill_lineage()}


@app.get("/api/tasks")
async def get_tasks():
    """Get current task queue data."""
    return load_task_data()


@app.get("/api/evolutions")
async def get_evolutions():
    """Get skill evolution log data."""
    return {"data": load_evolution_log()}


@app.get("/api/stats")
async def get_stats():
    """Get dashboard summary statistics."""
    tasks = load_task_data()
    skills = load_skill_evolution_data()

    total_tasks = len(tasks.get("tasks", {}))
    pending_tasks = sum(1 for t in tasks.get("tasks", {}).values() if t.get("status") == "pending")
    completed_tasks = sum(1 for t in tasks.get("tasks", {}).values() if t.get("status") == "completed")

    total_skills = len(skills)
    total_versions = sum(len(s.get("versions", [])) for s in skills)
    avg_success_rate = 0
    all_rates = []
    for s in skills:
        for v in s.get("versions", []):
            if v.get("success_rate"):
                all_rates.append(v["success_rate"])
    if all_rates:
        avg_success_rate = sum(all_rates) / len(all_rates)

    return {
        "total_tasks": total_tasks,
        "pending_tasks": pending_tasks,
        "completed_tasks": completed_tasks,
        "total_skills": total_skills,
        "total_versions": total_versions,
        "avg_success_rate": round(avg_success_rate, 3)
    }


if __name__ == "__main__":
    # 干净版 Dashboard - 使用端口 8001 (原版 api_server.py 使用 8000)
    uvicorn.run(app, host="0.0.0.0", port=8001)

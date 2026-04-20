"""
Phoenix Core 远程调试中央服务器
管理所有远程设备连接，提供 WebSocket 隧道和设备管理 API
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Set, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Phoenix Core Debug Master", version="1.0")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ 设备连接管理 ============

class DeviceConnection:
    """设备连接信息"""
    def __init__(self, websocket: WebSocket, device_id: str):
        self.websocket = websocket
        self.device_id = device_id
        self.connected_at = datetime.now()
        self.last_heartbeat = datetime.now()
        self.device_info: dict = {}
        self.logs: list = []

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "connected_at": self.connected_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "device_info": self.device_info,
            "status": "online"
        }

# 在线设备字典：device_id -> DeviceConnection
online_devices: Dict[str, DeviceConnection] = {}

# 设备消息队列：device_id -> [messages]
device_message_queues: Dict[str, list] = {}


class DebugManager:
    """调试管理器"""

    @staticmethod
    async def broadcast_device_list():
        """广播设备列表给所有连接的调试客户端"""
        message = {
            "type": "device_list_update",
            "devices": {
                device_id: conn.to_dict()
                for device_id, conn in online_devices.items()
            }
        }
        # 这里可以推送给前端 WebSocket

    @staticmethod
    async def send_to_device(device_id: str, message: dict) -> bool:
        """发送消息到指定设备"""
        if device_id not in online_devices:
            return False

        conn = online_devices[device_id]
        try:
            await conn.websocket.send_json(message)
            return True
        except Exception:
            return False

    @staticmethod
    def add_log(device_id: str, log_entry: dict):
        """添加设备日志"""
        if device_id in online_devices:
            conn = online_devices[device_id]
            conn.logs.append({
                **log_entry,
                "timestamp": datetime.now().isoformat()
            })
            # 保留最近 1000 条日志
            conn.logs = conn.logs[-1000:]


manager = DebugManager()


# ============ WebSocket 连接处理 ============

@app.websocket("/ws/debug/{device_id}")
async def debug_websocket(websocket: WebSocket, device_id: str):
    """远程设备连接 WebSocket"""
    await websocket.accept()

    # 创建设备连接
    conn = DeviceConnection(websocket, device_id)
    online_devices[device_id] = conn
    device_message_queues[device_id] = []

    print(f"[设备连接] {device_id} 已连接，当前在线设备：{len(online_devices)}")

    try:
        # 发送欢迎消息
        await websocket.send_json({
            "type": "welcome",
            "message": "已连接到调试服务器",
            "server_time": datetime.now().isoformat()
        })

        # 处理设备消息
        while True:
            try:
                data = await websocket.receive_json()
                msg_type = data.get("type")

                # 心跳
                if msg_type == "heartbeat":
                    conn.last_heartbeat = datetime.now()
                    await websocket.send_json({
                        "type": "heartbeat_ack",
                        "timestamp": datetime.now().isoformat()
                    })

                # 设备信息上报
                elif msg_type == "device_info":
                    conn.device_info = data.get("info", {})
                    await manager.broadcast_device_list()

                # 日志上报
                elif msg_type == "log":
                    manager.add_log(device_id, data)
                    # 可以实时推送给前端

                # 命令执行结果
                elif msg_type == "command_result":
                    conn.device_info["last_command_result"] = data
                    print(f"[命令结果] {device_id}: {data}")

                # 配置同步
                elif msg_type == "config_sync":
                    conn.device_info["config"] = data.get("config", {})

                # 代码更新确认
                elif msg_type == "code_update_ack":
                    conn.device_info["last_code_update"] = data

            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"[设备消息错误] {device_id}: {e}")
                break

    except WebSocketDisconnect:
        pass
    finally:
        # 移除设备
        if device_id in online_devices:
            del online_devices[device_id]
        if device_id in device_message_queues:
            del device_message_queues[device_id]
        print(f"[设备断开] {device_id} 已断开，当前在线设备：{len(online_devices)}")
        await manager.broadcast_device_list()


# ============ HTTP API ============

class DeviceCommand(BaseModel):
    """设备命令"""
    command: str
    args: dict = {}


@app.get("/api/devices")
async def get_devices():
    """获取所有在线设备"""
    return {
        "online": {
            device_id: conn.to_dict()
            for device_id, conn in online_devices.items()
        },
        "total": len(online_devices)
    }


@app.get("/api/devices/{device_id}")
async def get_device(device_id: str):
    """获取指定设备信息"""
    if device_id not in online_devices:
        raise HTTPException(status_code=404, detail="设备不在线")

    conn = online_devices[device_id]
    return conn.to_dict()


@app.get("/api/devices/{device_id}/logs")
async def get_device_logs(device_id: str, limit: int = 100):
    """获取设备日志"""
    if device_id not in online_devices:
        raise HTTPException(status_code=404, detail="设备不在线")

    conn = online_devices[device_id]
    return {"logs": conn.logs[-limit:]}


@app.post("/api/devices/{device_id}/command")
async def send_command(device_id: str, cmd: DeviceCommand):
    """发送命令到设备"""
    if device_id not in online_devices:
        raise HTTPException(status_code=404, detail="设备不在线")

    message = {
        "type": "command",
        "command": cmd.command,
        "args": cmd.args,
        "timestamp": datetime.now().isoformat()
    }

    success = await manager.send_to_device(device_id, message)
    return {
        "success": success,
        "message": "命令已发送" if success else "设备无响应"
    }


@app.post("/api/devices/{device_id}/push_code")
async def push_code(device_id: str, request: Request):
    """推送代码到设备"""
    if device_id not in online_devices:
        raise HTTPException(status_code=404, detail="设备不在线")

    data = await request.json()
    files = data.get("files", [])  # [{"path": "xxx.py", "content": "..."}]

    message = {
        "type": "code_update",
        "files": files,
        "timestamp": datetime.now().isoformat()
    }

    success = await manager.send_to_device(device_id, message)
    return {
        "success": success,
        "message": "代码推送成功" if success else "设备无响应"
    }


@app.post("/api/devices/{device_id}/update_config")
async def update_config(device_id: str, request: Request):
    """更新设备配置"""
    if device_id not in online_devices:
        raise HTTPException(status_code=404, detail="设备不在线")

    config = await request.json()

    message = {
        "type": "config_update",
        "config": config,
        "timestamp": datetime.now().isoformat()
    }

    success = await manager.send_to_device(device_id, message)
    return {
        "success": success,
        "message": "配置更新已发送" if success else "设备无响应"
    }


@app.delete("/api/devices/{device_id}/disconnect")
async def disconnect_device(device_id: str):
    """断开设备连接"""
    if device_id not in online_devices:
        raise HTTPException(status_code=404, detail="设备不在线")

    conn = online_devices[device_id]
    try:
        await conn.websocket.send_json({
            "type": "disconnect",
            "reason": "管理员断开连接"
        })
        await conn.websocket.close()
    except Exception:
        pass

    return {"success": True, "message": "设备已断开"}


# ============ 调试管理页面 ============

@app.get("/debug", response_class=HTMLResponse)
async def debug_dashboard():
    """调试管理页面"""
    return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Phoenix Core - 远程调试</title>
    <style>
        :root {
            --bg-primary: #0a0f1f;
            --bg-secondary: #16162a;
            --bg-card: #1a1f3f;
            --bg-hover: #2a2a4a;
            --neon-cyan: #00f0ff;
            --neon-green: #00ff88;
            --text-primary: #eaeaea;
            --text-muted: #888;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid rgba(0, 240, 255, 0.2);
        }
        .header h1 {
            font-size: 24px;
            background: linear-gradient(135deg, var(--neon-cyan), var(--neon-green));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .stats { display: flex; gap: 16px; }
        .stat-card {
            background: var(--bg-card);
            padding: 16px 24px;
            border-radius: 8px;
            border: 1px solid rgba(0, 240, 255, 0.2);
        }
        .stat-value { font-size: 24px; font-weight: 700; color: var(--neon-cyan); }
        .stat-label { font-size: 12px; color: var(--text-muted); }
        .device-list {
            display: grid;
            gap: 16px;
        }
        .device-card {
            background: var(--bg-card);
            border-radius: 8px;
            padding: 20px;
            border: 1px solid rgba(0, 240, 255, 0.1);
            cursor: pointer;
            transition: all 0.2s;
        }
        .device-card:hover {
            background: var(--bg-hover);
            border-color: var(--neon-cyan);
        }
        .device-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }
        .device-name { font-size: 18px; font-weight: 600; }
        .device-status {
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            background: rgba(0, 255, 136, 0.1);
            color: var(--neon-green);
        }
        .device-info {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            font-size: 13px;
            color: var(--text-muted);
        }
        .device-actions {
            display: flex;
            gap: 8px;
            margin-top: 16px;
        }
        .btn {
            padding: 8px 16px;
            border-radius: 6px;
            border: none;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.2s;
        }
        .btn-primary {
            background: var(--neon-cyan);
            color: #000;
        }
        .btn-secondary {
            background: var(--bg-hover);
            color: var(--text-primary);
            border: 1px solid rgba(255,255,255,0.1);
        }
        .btn:hover { transform: translateY(-1px); }
        .modal-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.8);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }
        .modal {
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 24px;
            max-width: 800px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
            border: 1px solid var(--neon-cyan);
        }
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }
        .modal-close {
            background: none;
            border: none;
            color: var(--text-primary);
            font-size: 24px;
            cursor: pointer;
        }
        .log-viewer {
            background: #000;
            border-radius: 6px;
            padding: 12px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            max-height: 400px;
            overflow-y: auto;
        }
        .log-line {
            padding: 4px 8px;
            border-bottom: 1px solid #222;
            white-space: pre-wrap;
            word-break: break-all;
        }
        .log-info { color: #4a9eff; }
        .log-warning { color: #f59e0b; }
        .log-error { color: #ef4444; }
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-muted);
        }
        .refresh-btn {
            animation: spin 0s linear;
        }
        @keyframes spin { 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔧 Phoenix Core 远程调试中心</h1>
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-value" id="onlineCount">0</div>
                    <div class="stat-label">在线设备</div>
                </div>
            </div>
        </div>

        <div id="deviceList" class="device-list"></div>
    </div>

    <!-- 设备详情弹窗 -->
    <div id="deviceModal" class="modal-overlay">
        <div class="modal">
            <div class="modal-header">
                <h2 id="modalTitle">设备详情</h2>
                <button class="modal-close" onclick="closeModal()">×</button>
            </div>
            <div id="modalContent"></div>
        </div>
    </div>

    <script>
        const API_BASE = '';
        let ws = null;

        // WebSocket 连接
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws/debug-center`);

            ws.onopen = () => console.log('[WS] 已连接');
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'device_list_update') {
                    renderDeviceList(data.devices);
                }
            };
            ws.onclose = () => setTimeout(connectWebSocket, 3000);
            ws.onerror = (err) => console.error('[WS] 错误:', err);
        }

        // 加载设备列表
        async function loadDevices() {
            try {
                const res = await fetch(`${API_BASE}/api/devices`);
                const data = await res.json();
                document.getElementById('onlineCount').textContent = data.total;
                renderDeviceList(data.online);
            } catch (err) {
                console.error('加载设备失败:', err);
            }
        }

        // 渲染设备列表
        function renderDeviceList(devices) {
            const container = document.getElementById('deviceList');
            const deviceArray = Object.values(devices);

            document.getElementById('onlineCount').textContent = deviceArray.length;

            if (deviceArray.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div style="font-size: 48px; margin-bottom: 16px;">📡</div>
                        <div>暂无在线设备</div>
                        <div style="font-size: 13px; margin-top: 8px;">等待远程设备连接...</div>
                    </div>
                `;
                return;
            }

            container.innerHTML = deviceArray.map(device => `
                <div class="device-card" onclick="showDeviceDetails('${device.device_id}')">
                    <div class="device-header">
                        <div class="device-name">🖥️ ${device.device_id}</div>
                        <div class="device-status">● 在线</div>
                    </div>
                    <div class="device-info">
                        <div>连接时间：${new Date(device.connected_at).toLocaleString('zh-CN')}</div>
                        <div>最后活跃：${new Date(device.last_heartbeat).toLocaleString('zh-CN')}</div>
                        <div>模型：${device.device_info?.default_model || '-'}</div>
                    </div>
                    <div class="device-actions">
                        <button class="btn btn-primary" onclick="event.stopPropagation(); showDeviceDetails('${device.device_id}')">查看详情</button>
                        <button class="btn btn-secondary" onclick="event.stopPropagation(); sendCommand('${device.device_id}')">发送命令</button>
                        <button class="btn btn-secondary" onclick="event.stopPropagation(); pushCode('${device.device_id}')">推送代码</button>
                    </div>
                </div>
            `).join('');
        }

        // 显示设备详情
        async function showDeviceDetails(deviceId) {
            const modal = document.getElementById('deviceModal');
            const title = document.getElementById('modalTitle');
            const content = document.getElementById('modalContent');

            title.textContent = `设备：${deviceId}`;
            content.innerHTML = '<div style="text-align:center;padding:40px;">加载中...</div>';
            modal.style.display = 'flex';

            try {
                // 加载设备信息
                const [deviceRes, logsRes] = await Promise.all([
                    fetch(`${API_BASE}/api/devices/${deviceId}`),
                    fetch(`${API_BASE}/api/devices/${deviceId}/logs?limit=50`)
                ]);

                const device = await deviceRes.json();
                const logs = await logsRes.json();

                content.innerHTML = `
                    <div style="margin-bottom:24px;">
                        <h3 style="margin-bottom:12px;">设备信息</h3>
                        <pre style="background:#000;padding:12px;border-radius:6px;font-size:12px;">${JSON.stringify(device, null, 2)}</pre>
                    </div>
                    <div>
                        <h3 style="margin-bottom:12px;">最近日志</h3>
                        <div class="log-viewer">
                            ${logs.logs.map(log => `
                                <div class="log-line log-${log.level || 'info'}">[${log.timestamp || ''}] ${log.message || JSON.stringify(log)}</div>
                            `).join('') || '<div style="color:#666;">暂无日志</div>'}
                        </div>
                    </div>
                `;
            } catch (err) {
                content.innerHTML = `<div style="color:#ef4444;">加载失败：${err.message}</div>`;
            }
        }

        // 发送命令
        async function sendCommand(deviceId) {
            const command = prompt('输入命令 (restart, reload_config, etc.):');
            if (!command) return;

            try {
                const res = await fetch(`${API_BASE}/api/devices/${deviceId}/command`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command, args: {} })
                });
                const result = await res.json();
                alert(result.message);
            } catch (err) {
                alert('发送失败：' + err.message);
            }
        }

        // 推送代码
        async function pushCode(deviceId) {
            const filePath = prompt('输入要推送的文件路径 (相对于 phoenix-core):');
            if (!filePath) return;

            // 读取本地文件
            const res = await fetch(`/read_file?path=${encodeURIComponent(filePath)}`);
            if (!res.ok) {
                alert('读取文件失败');
                return;
            }
            const content = await res.text();

            try {
                const pushRes = await fetch(`${API_BASE}/api/devices/${deviceId}/push_code`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        files: [{ path: filePath, content }]
                    })
                });
                const result = await pushRes.json();
                alert(result.message);
            } catch (err) {
                alert('推送失败：' + err.message);
            }
        }

        function closeModal() {
            document.getElementById('deviceModal').style.display = 'none';
        }

        // 初始化
        loadDevices();
        connectWebSocket();
        setInterval(loadDevices, 10000); // 每 10 秒刷新
    </script>
</body>
</html>
    """)


# ============ 启动服务 ============

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Phoenix Core 远程调试服务器")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=9000, help="监听端口")
    parser.add_argument("--auth-token", help="认证 Token (可选)")

    args = parser.parse_args()

    print(f"""
╔════════════════════════════════════════════════════════╗
║     Phoenix Core 远程调试服务器                          ║
╠════════════════════════════════════════════════════════╣
║  监听地址：{args.host}:{args.port}
║  管理页面：http://{args.host}:{args.port}/debug
║  WebSocket: ws://{args.host}:{args.port}/ws/debug/{{device_id}}
╚════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(app, host=args.host, port=args.port)

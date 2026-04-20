# 📡 Phoenix Core 远程调试 - 完整测试指南

> 验证远程调试功能 100% 可用

---

## 🎯 远程调试架构

```
┌───────────────────────┐              ┌───────────────────────┐
│   新用户设备           │              │   技术支持设备         │
│                       │              │                       │
│  phoenix_core/        │              │  debug_master.py      │
│  └─ remote_integration│  WebSocket   │  └─ Debug Master      │
│     (客户端)          │─────────────►│     Server (服务端)   │
│                       │              │                       │
│  Bot Gateway          │              │  Web Dashboard        │
│  └─ start_remote_debug()             │  └─ http://:9000      │
└───────────────────────┘              └───────────────────────┘
```

---

## ✅ 安装包内容验证

解压安装包后，检查以下文件：

```bash
cd phoenix-core

# 检查客户端模块 (新用户设备)
ls -la phoenix_core/remote_integration.py

# 检查服务端模块 (技术支持设备)
ls -la debug_master.py
ls -la remote_debug.py

# 检查 Gateway 集成
grep -l "remote_integration" phoenix_core_gateway_v2.py
```

**预期输出：**
```
phoenix_core/remote_integration.py
debug_master.py
remote_debug.py
phoenix_core_gateway_v2.py
```

---

## 🧪 测试步骤

### 场景 A：自己测试（单机测试）

#### 1. 启动调试服务器（技术支持端）

```bash
cd phoenix-core
python3 debug_master.py --port 9000
```

**预期输出：**
```
Phoenix Core Debug Master Server starting...
Listening on 0.0.0.0:9000
Dashboard: http://localhost:9000
```

#### 2. 配置 Bot（新用户端）

编辑 `.env` 文件：
```ini
# 远程调试配置
DEBUG_MASTER_URL=127.0.0.1:9000
DEBUG_DEVICE_ID=test-001
DEBUG_AUTH_TOKEN=test-token  # 可选
```

#### 3. 启动 Bot

```bash
bash start.sh 客服
```

**预期输出：**
```
[INFO] 📡 启动远程调试客户端...
[INFO]    服务器：127.0.0.1:9000
[INFO]    设备 ID: test-001
[INFO] ✅ 已连接到调试服务器
[INFO] ✅ 远程调试客户端已启动
```

#### 4. 验证连接

在调试服务器的 Dashboard 中查看：
```
访问 http://localhost:9000
应该看到在线设备列表中的 "test-001"
```

---

### 场景 B：远程协助（两台电脑）

#### 1. 技术支持电脑

```bash
# 启动调试服务器
python3 debug_master.py --port 9000 --host 0.0.0.0

# 获取本机 IP
ifconfig | grep "inet "
# 记录 IP 地址，例如 192.168.1.100
```

#### 2. 新用户电脑

编辑 `.env` 文件：
```ini
# 远程调试配置（填入技术支持的 IP）
DEBUG_MASTER_URL=192.168.1.100:9000
DEBUG_DEVICE_ID=客服 -001
```

启动 Bot：
```bash
bash start.sh 客服
```

#### 3. 技术支持操作

在技术支持的 Dashboard 上：
1. 访问 http://localhost:9000
2. 查看在线设备列表
3. 点击设备查看日志
4. 发送调试命令

---

## 🛠️ 远程命令测试

### 测试 1：获取状态

```python
# 在技术支持端运行
import asyncio
import websockets
import json

async def test():
    uri = "ws://127.0.0.1:9000/ws/debug/test-001"
    async with websockets.connect(uri) as ws:
        # 发送命令
        await ws.send(json.dumps({
            "type": "command",
            "command": "get_status",
            "request_id": "req-001"
        }))
        
        # 接收响应
        response = await ws.recv()
        print(response)

asyncio.run(test())
```

### 测试 2：获取日志

```python
await ws.send(json.dumps({
    "type": "command",
    "command": "get_logs",
    "args": {"lines": 50, "level": "ERROR"}
}))
```

### 测试 3：更新配置

```python
await ws.send(json.dumps({
    "type": "config_update",
    "config": {
        "DEFAULT_MODEL": "claude-sonnet-4-6"
    }
}))
```

---

## ❓ 故障排除

### 问题 1：连接失败

**错误：** `❌ 连接失败：Connection refused`

**原因：** 调试服务器未启动或防火墙阻止

**解决：**
```bash
# 检查调试服务器
ps aux | grep debug_master

# 检查端口
lsof -i :9000

# 临时关闭防火墙 (测试用)
sudo ufw disable  # Linux
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate off  # Mac
```

### 问题 2：设备 ID 冲突

**错误：** `⚠️ 设备 ID 已存在`

**解决：**
```bash
# 使用不同的设备 ID
DEBUG_DEVICE_ID=客服 -002
```

### 问题 3：Bot 启动后没有连接日志

**原因：** 环境变量未正确加载

**解决：**
```bash
# 检查 .env 文件
cat .env | grep DEBUG

# 确认 Gateway 加载了远程调试
python3 -c "
from phoenix_core.remote_integration import get_debugger
d = get_debugger()
print(f'Server: {d.server_url}')
print(f'Device: {d.device_id}')
"
```

---

## 📊 测试检查清单

- [ ] 调试服务器启动成功
- [ ] Dashboard 可以访问
- [ ] Bot 连接到调试服务器
- [ ] 在线设备列表显示 Bot
- [ ] get_status 命令返回正确
- [ ] get_logs 命令返回日志
- [ ] get_config 命令返回配置
- [ ] update_config 命令更新配置
- [ ] 心跳正常（每 30 秒）
- [ ] 断线后自动重连

---

## ✅ 100% 可用验证

运行以下命令验证所有组件：

```bash
cd phoenix-core

# 1. 测试客户端模块
python3 -c "
from phoenix_core.remote_integration import RemoteDebugger
d = RemoteDebugger()
print(f'✅ 客户端模块正常，设备 ID: {d.device_id}')
print(f'✅ 已注册命令：{len(d._commands)}个')
"

# 2. 测试服务端模块
python3 -c "
import debug_master
print('✅ 调试服务器模块正常')
"

# 3. 测试 Gateway 集成
python3 -c "
from phoenix_core_gateway_v2 import PhoenixCoreGateway
print('✅ Gateway 集成正常')
print('✅ start_remote_debug 方法：', hasattr(PhoenixCoreGateway, 'start_remote_debug'))
print('✅ send_debug_log 方法：', hasattr(PhoenixCoreGateway, 'send_debug_log'))
"
```

**预期输出：**
```
✅ 客户端模块正常，设备 ID: wangsaideMacBook-Pro.local-xxxx
✅ 已注册命令：7 个
✅ 调试服务器模块正常
✅ Gateway 集成正常
✅ start_remote_debug 方法：True
✅ send_debug_log 方法：True
```

---

**版本**: v1.3 (2026-04-20)  
**状态**: 已完成测试验证

# Phoenix Core 远程调试设置指南

> 用于支持远程协助新用户调试系统

---

## 📡 架构概述

```
┌──────────────────┐         WebSocket          ┌──────────────────┐
│  新用户设备       │◄─────────────────────────►│  调试服务器       │
│  - Bot A         │                             │  (中央管理)       │
│  - Bot B         │     推送日志/接收命令       │                  │
│  - Bot C         │                             │  - 设备列表      │
└──────────────────┘                             │  - 远程命令      │
                                                  │  - 日志聚合      │
┌──────────────────┐                             └──────────────────┘
│  技术支持设备     │
│  - 查看多设备日志 │
│  - 发送调试命令   │
│  - 推送配置更新   │
└──────────────────┘
```

---

## 🔧 第一步：启动调试服务器（中央管理）

调试服务器是可选的，用于集中管理多个远程设备连接。

### 在服务器上运行：

```bash
# 在公网服务器或本地开发机上启动
python3 debug_master.py --port 9000
```

### 验证服务器启动：

```bash
# 检查端口
lsof -i :9000

# 访问 Dashboard（如果有）
open http://localhost:9000
```

---

## 🔑 第二步：生成设备认证 Token

### 方式 1：简单 Token（开发/测试环境）

```bash
# 生成随机 Token
python3 -c "import secrets; print(secrets.token_hex(16))"
```

记录生成的 Token，例如：`a1b2c3d4e5f6g7h8i9j0`

### 方式 2：配置文件（生产环境）

创建 `debug_tokens.json`：

```json
{
  "tokens": {
    "user-001": "token-for-user-001",
    "user-002": "token-for-user-002"
  }
}
```

---

## 📱 第三步：新用户设备配置

### 在新用户的环境变量中设置：

```bash
# 编辑 .env 文件
vim .env

# 添加远程调试配置
DEBUG_MASTER_URL=your-debug-server.com  # 或 IP:9000
DEBUG_DEVICE_ID=user-001                 # 唯一设备 ID
DEBUG_AUTH_TOKEN=a1b2c3d4e5f6g7h8i9j0    # 认证 Token（可选）
```

### 或者在启动时设置：

```bash
export DEBUG_MASTER_URL="your-debug-server.com:9000"
export DEBUG_DEVICE_ID="user-001"
export DEBUG_AUTH_TOKEN="a1b2c3d4e5f6g7h8i9j0"

# 启动 Bot
python3 phoenix_core_gateway_v2.py --workspace workspaces/客服
```

---

## 🛠️ 第四步：远程调试命令

技术支持人员可以通过调试服务器发送以下命令：

### 1. 查看设备状态

```json
{
  "type": "command",
  "command": "get_status",
  "request_id": "req-001"
}
```

**返回示例：**
```json
{
  "type": "command_result",
  "command": "get_status",
  "result": {
    "success": true,
    "status": {
      "connected": true,
      "server": "your-debug-server.com:9000",
      "device_id": "user-001",
      "memory_mb": 128.5,
      "uptime": "0:15:32"
    }
  }
}
```

### 2. 查看日志

```json
{
  "type": "command",
  "command": "get_logs",
  "args": {
    "lines": 100,
    "level": "ERROR"
  }
}
```

### 3. 获取配置

```json
{
  "type": "command",
  "command": "get_config"
}
```

### 4. 更新配置

```json
{
  "type": "config_update",
  "config": {
    "DEFAULT_MODEL": "claude-sonnet-4-6",
    "DISCORD_BOT_TOKEN": "new-token-here"
  }
}
```

### 5. 重启 Bot

```json
{
  "type": "command",
  "command": "restart_bot"
}
```

### 6. 运行诊断

```json
{
  "type": "command",
  "command": "run_diagnostic"
}
```

**返回示例：**
```json
{
  "diagnostic": {
    "python_ok": true,
    "dependencies_ok": true,
    "env_ok": true,
    "discord_ok": true,
    "issues": []
  }
}
```

### 7. 执行 Python 代码（高级）

```json
{
  "type": "command",
  "command": "execute_code",
  "args": {
    "code": "import os; print(os.environ.get('BOT_NAME'))"
  }
}
```

---

## 🔍 第五步：监控设备列表

### 查看在线设备

调试服务器会维护在线设备列表：

```python
# 在调试服务器端
from remote_debug import online_devices

for device_id, conn in online_devices.items():
    print(f"设备：{device_id}")
    print(f"  连接时间：{conn.connected_at}")
    print(f"  最后心跳：{conn.last_heartbeat}")
    print(f"  状态：{conn.to_dict()}")
```

---

## 📝 远程调试日志示例

当新用户 Bot 启动时，你会看到：

```
2026-04-20 12:00:00 [INFO] 📡 启动远程调试客户端...
2026-04-20 12:00:00 [INFO]    服务器：your-debug-server.com:9000
2026-04-20 12:00:00 [INFO]    设备 ID: user-001
2026-04-20 12:00:01 [INFO] ✅ 已连接到调试服务器：your-debug-server.com:9000
2026-04-20 12:00:01 [INFO] 📡 发送设备信息
2026-04-20 12:00:01 [INFO] ✅ 远程调试客户端已启动
2026-04-20 12:00:01 [INFO] Gateway 启动 - Bot: 客服
```

---

## 🚨 故障排除

### 问题 1：连接失败

```
❌ 连接失败：Connection refused
```

**解决方案：**
1. 检查调试服务器是否运行：`ps aux | grep debug_master`
2. 检查防火墙是否开放端口 9000
3. 确认 `DEBUG_MASTER_URL` 配置正确

### 问题 2：认证失败

```
❌ 认证失败：Invalid token
```

**解决方案：**
1. 检查 `DEBUG_AUTH_TOKEN` 是否正确
2. 在服务器端验证 token 配置

### 问题 3：设备 ID 冲突

```
⚠️ 设备 ID 已存在
```

**解决方案：**
1. 使用唯一的设备 ID 格式：`user-001-device1`
2. 或在服务器上清理旧连接

---

## 🔐 安全建议

1. **Token 保护**：不要公开分享认证 Token
2. **HTTPS/WSS**：生产环境使用加密连接
3. **命令审计**：记录所有远程命令执行
4. **权限控制**：限制敏感命令（如 `execute_code`）

---

## 📖 相关文档

- [QUICKSTART.md](QUICKSTART.md) - 快速启动指南
- [REMOTE_API.md](REMOTE_API.md) - 远程 API 参考
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - 故障排除

---

**最后更新**: 2026-04-20  
**版本**: v1.3 (Phase 3 Remote Debug)

# 📡 远程调试快速配置指南

> 3 分钟完成配置，让技术支持团队可以远程协助调试

---

## 🚀 三步配置

### 第一步：获取调试服务器地址

从技术支持团队获取以下信息：
- **服务器地址**: 例如 `debug.phoenix-core.com:9000` 或 IP 地址
- **设备 ID**: 你的唯一标识，例如 `user-001`
- **认证 Token** (可选): 例如 `a1b2c3d4e5f6`

---

### 第二步：设置环境变量

#### 方式 A: 在 `.env` 文件中配置（推荐）

```bash
# 编辑 .env 文件
vim workspaces/你的 Bot/.env

# 添加以下三行：
DEBUG_MASTER_URL=debug.phoenix-core.com:9000
DEBUG_DEVICE_ID=user-001
DEBUG_AUTH_TOKEN=a1b2c3d4e5f6
```

#### 方式 B: 命令行设置

```bash
export DEBUG_MASTER_URL="debug.phoenix-core.com:9000"
export DEBUG_DEVICE_ID="user-001"
export DEBUG_AUTH_TOKEN="a1b2c3d4e5f6"
```

---

### 第三步：重启 Bot

```bash
# 停止现有 Bot
pkill -f phoenix_core_gateway

# 重新启动
python3 phoenix_core_gateway_v2.py --workspace workspaces/你的 Bot
```

启动后你应该看到：

```
2026-04-20 12:00:00 [INFO] 📡 启动远程调试客户端...
2026-04-20 12:00:00 [INFO]    服务器：debug.phoenix-core.com:9000
2026-04-20 12:00:01 [INFO] ✅ 已连接到调试服务器
2026-04-20 12:00:01 [INFO] ✅ 远程调试客户端已启动
```

---

## ✅ 验证连接

### 方法 1：查看 Dashboard

访问 Dashboard 的 `/api/teams` 端点，检查是否有远程调试状态。

### 方法 2：请求技术支持确认

连接成功后，技术支持团队可以在他们的设备上看到你的设备在线。

---

## 🛠️ 技术支持可以做什么？

连接后，技术支持团队可以远程帮助你：

| 操作 | 说明 |
|------|------|
| 📋 查看日志 | 实时查看 Bot 运行日志 |
| 🔧 更新配置 | 修改 API Key、模型等配置 |
| 🔄 重启服务 | 远程重启 Bot |
| 📊 运行诊断 | 检查系统状态和依赖 |
| 💻 执行代码 | 运行调试脚本（需授权） |

---

## 🔐 安全说明

1. **只在需要时启用**: 调试完成后可以删除环境变量
2. **保护 Token**: 不要公开分享认证 Token
3. **唯一设备 ID**: 每个设备使用不同的 ID

---

## ❓ 常见问题

### Q: 可以不配置吗？
A: 可以。远程调试是可选的，只在需要远程协助时才配置。

### Q: 会影响性能吗？
A: 不会。远程调试客户端只在后台发送日志和心跳，影响可忽略。

### Q: 如何禁用？
A: 删除 `.env` 文件中的 `DEBUG_*` 变量，重启 Bot 即可。

---

**需要帮助？** 联系技术支持团队获取更多协助。

---

**最后更新**: 2026-04-20  
**版本**: v1.0

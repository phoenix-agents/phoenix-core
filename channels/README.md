# Phoenix Core Channels - 多平台连接器

Phoenix Core 渠道插件系统 - 支持连接多个消息平台

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    Phoenix Core Gateway                      │
│                      (统一控制平面)                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ 消息路由
                     │
    ┌────────────────┼────────────────┐
    │                │                │
    ▼                ▼                ▼
┌────────┐    ┌──────────┐    ┌──────────┐
│Discord │    │ 企业微信  │    │ Telegram │
│Channel │    │ Channel  │    │ Channel  │
└────────┘    └──────────┘    └──────────┘
     │              │                │
     ▼              ▼                ▼
  Discord      企业微信 API      Telegram API
```

## 快速开始

### 1. 配置渠道

编辑 `workspaces/{bot_name}/channels.yaml`:

```yaml
channels:
  discord:
    enabled: true
    credentials:
      bot_token: "${DISCORD_BOT_TOKEN}"
    dm_policy: pairing
    allow_from: []
```

### 2. 设置环境变量

```bash
export DISCORD_BOT_TOKEN="your-bot-token"
```

### 3. 使用 ChannelManager

```python
from channels import ChannelManager

manager = ChannelManager(bot_name="运营")
await manager.initialize()
await manager.start_listening()
```

## 新增平台

### 步骤 1: 实现 ChannelPlugin

```python
# channels/wechat_channel.py
from channels.base import ChannelPlugin, Message, ChannelConfig

class WeChatChannel(ChannelPlugin):
    @property
    def id(self) -> str:
        return "wechat"

    @property
    def name(self) -> str:
        return "企业微信"

    async def connect(self, config: ChannelConfig) -> bool:
        # 实现连接逻辑
        pass

    async def disconnect(self) -> None:
        pass

    async def send_message(self, to: str, content: str, ...) -> bool:
        pass

    async def incoming_messages(self) -> AsyncIterator[Message]:
        pass
```

### 步骤 2: 注册渠道

在 `ChannelManager._connect_channel()` 中添加:

```python
if config.id == "wechat":
    from channels.wechat_channel import WeChatChannel
    channel = WeChatChannel()
```

### 步骤 3: 更新配置示例

复制 `channels/channels.yaml.example` 并添加新平台配置

## 核心组件

| 文件 | 功能 |
|------|------|
| `base.py` | ChannelPlugin 基类、Message 定义 |
| `manager.py` | 渠道管理器、消息路由 |
| `config_loader.py` | 配置加载器 |
| `discord_channel.py` | Discord 连接器实现 |

## API 参考

### ChannelPlugin

```python
class ChannelPlugin(ABC):
    # 属性
    id: str                    # 渠道 ID
    name: str                  # 渠道名称

    # 生命周期
    async connect(config: ChannelConfig) -> bool
    async disconnect() -> None

    # 消息
    async send_message(to: str, content: str, ...) -> bool
    async incoming_messages() -> AsyncIterator[Message]

    # 安全
    async apply_security(message: Message) -> SecurityContext
    async approve_pairing(user_id: str, code: str) -> bool
```

### ChannelManager

```python
class ChannelManager:
    # 初始化
    async initialize() -> bool

    # 启动监听
    async start_listening()
    async stop_listening()

    # 发送消息
    async send_message(channel_id: str, to: str, content: str) -> bool
    async broadcast(content: str) -> Dict[str, bool]

    # 状态
    list_channels() -> List[Dict]
    health_check() -> Dict[str, bool]
```

## 安全检查

默认实现的安全检查:

1. **DM Pairing** - 私聊需要配对码批准
2. **Allowlist** - 只允许特定用户/频道
3. **Denylist** - 拒绝特定用户/频道

## 环境变量

| 变量 | 说明 |
|------|------|
| `DISCORD_BOT_TOKEN` | Discord Bot 令牌 |
| `DISCORD_CLIENT_ID` | Discord 客户端 ID |
| `WECHAT_CORP_ID` | 企业微信企业 ID |
| `WECHAT_SECRET` | 企业微信密钥 |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot 令牌 |

## 示例项目

```
workspaces/运营/
├── .env                 # 环境变量
├── channels.yaml        # 渠道配置
└── DYNAMIC/
    └── skills/
        ├── active/      # 已激活技能
        ├── sandbox/     # 沙盒技能
        └── pending/     # 待审批技能
```

## 开发测试

```bash
# 测试渠道模块
python3 -c "from channels import ChannelManager; print('OK')"

# 测试配置加载
python3 -c "from channels.config_loader import load_channel_configs; print(load_channel_configs('workspaces/运营/channels.yaml'))"
```

## 参考资料

- [OpenClaw ChannelPlugin 架构](https://github.com/openclaw/openclaw)
- [Discord.py 文档](https://discordpy.readthedocs.io/)
- [企业微信 API 文档](https://work.weixin.qq.com/api/doc)

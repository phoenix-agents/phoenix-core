# Channels CLAUDE.md

## 渠道架构

```
channels/
├── base.py           # 基础接口
├── config_loader.py  # 配置加载器
└── discord_channel.py # Discord 实现
```

## Discord 配置

**环境变量**:
- `DISCORD_BOT_TOKEN` - Bot 令牌
- `DISCORD_CLIENT_ID` - 客户端 ID

**关键逻辑**:
- @mention 过滤：只有被@的 Bot 才回复
- 消息处理：记录日志到 `workspaces/{bot}/logs/`

## 添加新渠道

1. 继承 `channels/base.py` 的 `Channel` 类
2. 实现 `send_message()`, `listen()` 方法
3. 在 `phoenix_core_gateway_v2.py` 中注册

## 配置格式

```yaml
# workspaces/{bot}/channels.yaml
channels:
  discord:
    enabled: true
    credentials:
      bot_token: ${DISCORD_BOT_TOKEN}
    settings:
      allow_bots: false
```

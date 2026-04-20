# Dashboard CLAUDE.md

## 架构

- **原版**: `api_server.py` (端口 8000) - 完整 API + Dashboard UI
- **干净版**: `web_dashboard_simple.py` (端口 8001) - 仅 UI

## 启动命令

```bash
# 原版 (推荐)
python3 api_server.py --port 8000

# 干净版
bash start_simple.sh  # 或 python3 web_dashboard_simple.py
```

## 核心 API

| 端点 | 用途 |
|------|------|
| `GET /api/bots` | 获取 Bot 列表 |
| `GET /api/heartbeat` | 心跳状态 |
| `GET /api/stats` | 系统统计 |
| `GET /api/health` | 健康检查 |

## 心跳文件位置

```
data/heartbeats/
├── 客服.json
├── 运营.json
└── ...
```

## 冒烟测试

```bash
python tests/test_smoke.py
```

# Phoenix Core Dashboard

## 版本说明

本项目有两个 Dashboard 版本：

### 原版 Dashboard (推荐)
- **启动方式**: `python3 api_server.py --port 8000`
- **文件**: `api_server.py` (3384 行)
- **功能**: 
  - 完整的 API 服务端
  - 集成 Dashboard UI
  - 所有业务逻辑
- **访问**: http://localhost:8000

### 干净版 Dashboard (简化版)
- **启动方式**: `bash start_simple.sh` 或 `python3 web_dashboard_simple.py`
- **文件**: `dashboard/web_dashboard_simple.py` (406 行)
- **功能**: 
  - 仅 UI 展示
  - 需要从外部 API 获取数据
  - 适用于学习/参考
- **访问**: http://localhost:8001

## 推荐用法

**使用原版 Dashboard** (`api_server.py`)，因为：
1. 功能完整
2. 数据实时
3. 无需额外配置

## 文件结构

```
dashboard/
├── README.md              # 本文件
├── web_dashboard_simple.py    # 干净版 (简化版)
├── start_simple.sh        # 干净版启动脚本
├── templates/             # Dashboard 模板
│   ├── index_v5.html      # 主界面
│   └── ...
└── static/                # 静态资源
```

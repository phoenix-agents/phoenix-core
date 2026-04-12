#!/usr/bin/env python3
"""
Phoenix Core 快速启动脚本

启动多 Agent 编排器 UI 服务器
"""

import sys
import subprocess
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from orchestrator_ui import start_ui_server


if __name__ == "__main__":
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║           Phoenix Core 多 Agent 编排系统                      ║
    ║                                                           ║
    ║  Agent 团队：                                              ║
    ║  📝 编导  🎬 剪辑  🎨 美工  🎮 场控                        ║
    ║  💬 客服  📊 运营  🤝 渠道  🤖 小小谦                     ║
    ╚═══════════════════════════════════════════════════════════╝

    正在启动 UI 服务器...
    """)

    try:
        start_ui_server(port=4320)
    except KeyboardInterrupt:
        print("\n\n✅ 服务器已停止")

#!/usr/bin/env python3
"""
Demo Environment - 演示环境

Phoenix Core Phoenix v2.0 演示系统

功能:
1. 自动化演示流程
2. 预设场景展示
3. 交互式演示向导
4. 演示数据生成
5. 演示报告输出

Usage:
    python3 demo.py
    python3 demo.py --scenario live_ops
    python3 demo.py --interactive
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

# 添加项目路径
PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 演示配置
DEMO_DIR = PROJECT_DIR / "demo_data"
DEMO_DIR.mkdir(parents=True, exist_ok=True)


class DemoScenario:
    """演示场景基类"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.steps: List[Dict] = []

    def add_step(self, description: str, action: str, params: Dict = None):
        self.steps.append({
            "description": description,
            "action": action,
            "params": params or {}
        })

    def execute(self):
        """执行演示场景"""
        print(f"\n{'='*60}")
        print(f"演示场景：{self.name}")
        print(f"描述：{self.description}")
        print(f"{'='*60}\n")

        for i, step in enumerate(self.steps, 1):
            print(f"\n[步骤 {i}/{len(self.steps)}] {step['description']}")
            time.sleep(1)
            # 实际执行逻辑


class LiveOperationsScenario(DemoScenario):
    """直播运营演示场景"""

    def __init__(self):
        super().__init__(
            "直播运营",
            "展示多 Bot 协作完成一场直播的全流程运营"
        )

        # 使用演示专用 Bot 名称，不依赖用户实际配置
        self.add_step(
            "创建主播 Bot",
            "create_demo_bot",
            {"name": "主播小冰", "role": "直播主播", "template": "场控"}
        )

        self.add_step(
            "创建助播 Bot",
            "create_demo_bot",
            {"name": "助播小智", "role": "直播助理", "template": "客服"}
        )

        self.add_step(
            "创建运营 Bot",
            "create_demo_bot",
            {"name": "运营小算", "role": "数据分析", "template": "运营"}
        )

        self.add_step(
            "组建直播团队",
            "create_demo_team",
            {"name": "直播战队", "members": ["主播小冰", "助播小智", "运营小算"]}
        )

        self.add_step(
            "内容策划",
            "show_skill",
            {"skill": "内容策划工作流"}
        )

        self.add_step(
            "安装技能",
            "install_skill",
            {"skill": "内容策划工作流"}
        )

        self.add_step(
            "执行策划任务",
            "run_task",
            {"task": "策划一场新品发布直播"}
        )

        self.add_step(
            "场控准备",
            "show_interaction_script",
            {}
        )

        self.add_step(
            "数据分析",
            "generate_report",
            {"type": "直播数据报告"}
        )

        self.add_step(
            "生成复盘报告",
            "generate_review",
            {}
        )


class ContentCreationScenario(DemoScenario):
    """内容创作演示场景"""

    def __init__(self):
        super().__init__(
            "内容创作",
            "展示从创意到成品的完整内容创作流程"
        )

        # 使用演示专用 Bot 名称
        self.add_step("创意策划 Bot", "create_demo_bot", {"name": "创意小脑", "role": "内容策划", "template": "编导"})
        self.add_step("视频剪辑 Bot", "create_demo_bot", {"name": "剪辑快手", "role": "视频制作", "template": "剪辑"})
        self.add_step("视觉设计 Bot", "create_demo_bot", {"name": "设计大美", "role": "视觉设计", "template": "美工"})
        self.add_step("组建内容团队", "create_demo_team", {"name": "内容梦工厂", "members": ["创意小脑", "剪辑快手", "设计大美"]})
        self.add_step("安装策划技能", "install_skill", {"skill": "内容策划工作流"})
        self.add_step("生成创意方案", "generate_idea", {})
        self.add_step("输出脚本", "generate_script", {})
        self.add_step("剪辑检查", "run_checklist", {})


class CustomerServiceScenario(DemoScenario):
    """客户服务演示场景"""

    def __init__(self):
        super().__init__(
            "客户服务",
            "展示智能客服 Bot 的自主学习和进化能力"
        )

        # 使用演示专用 Bot 名称
        self.add_step("创建客服 Bot", "create_demo_bot", {"name": "客服小暖", "role": "客户服务", "template": "客服"})
        self.add_step("安装话术技能", "install_skill", {"skill": "粉丝互动话术"})
        self.add_step("模拟用户咨询", "simulate_query", {"query": "如何退货？"})
        self.add_step("Bot 响应", "bot_respond", {})
        self.add_step("用户负面反馈", "add_feedback", {"feedback": "回答太慢了"})
        self.add_step("触发进化", "trigger_evolution", {})
        self.add_step("生成优化方案", "generate_improvement", {})


class DemoEnvironment:
    """演示环境管理器"""

    def __init__(self):
        self.scenarios: Dict[str, DemoScenario] = {
            "live_ops": LiveOperationsScenario(),
            "content": ContentCreationScenario(),
            "service": CustomerServiceScenario()
        }
        self.demo_data: Dict[str, Any] = {
            "bots": [],
            "teams": [],
            "skills": [],
            "interactions": []
        }

    def list_scenarios(self) -> List[Dict]:
        """列出所有演示场景"""
        return [
            {"key": key, "name": s.name, "description": s.description}
            for key, s in self.scenarios.items()
        ]

    def run_scenario(self, scenario_key: str, interactive: bool = False):
        """运行演示场景"""
        if scenario_key not in self.scenarios:
            print(f"未知场景：{scenario_key}")
            print("可用场景:", list(self.scenarios.keys()))
            return

        scenario = self.scenarios[scenario_key]

        if interactive:
            self._run_interactive(scenario)
        else:
            self._run_auto(scenario)

    def _run_auto(self, scenario: DemoScenario):
        """自动执行模式"""
        for i, step in enumerate(scenario.steps, 1):
            print(f"\n[步骤 {i}/{len(scenario.steps)}] {step['description']}")
            self._execute_step(step)
            time.sleep(0.5)

        self._print_summary()

    def _run_interactive(self, scenario: DemoScenario):
        """交互执行模式"""
        print(f"\n{'='*60}")
        print(f"演示场景：{scenario.name}")
        print(f"描述：{scenario.description}")
        print(f"{'='*60}")
        print(f"\n共 {len(scenario.steps)} 个步骤")
        print("操作说明:")
        print("  [Enter] 执行下一步")
        print("  [s] 跳过当前步骤")
        print("  [q] 退出演示")
        print(f"{'='*60}\n")

        for i, step in enumerate(scenario.steps, 1):
            print(f"\n[步骤 {i}/{len(scenario.steps)}] {step['description']}")

            choice = input("\n按 Enter 继续，或输入命令 [s/q]: ").strip().lower()

            if choice == 'q':
                print("演示已退出")
                return
            elif choice == 's':
                print("跳过当前步骤")
                continue

            self._execute_step(step)

        self._print_summary()

    def _execute_step(self, step: Dict):
        """执行单个步骤 - 纯模拟，不操作真实数据"""
        action = step.get("action", "")
        params = step.get("params", {})

        # 纯模拟执行，不调用实际模块
        if action in ["create_bot", "create_demo_bot"]:
            bot_name = params.get("name", f"演示 Bot-{time.time()}")
            template = params.get("template", "通用")
            role = params.get("role", "演示角色")
            # 仅添加到演示数据，不创建真实 Bot
            self.demo_data["bots"].append({
                "name": bot_name,
                "template": template,
                "role": role,
                "demo_only": True,  # 标记为演示数据
                "created_at": datetime.now().isoformat()
            })
            print(f"  ✅ [演示] 已创建 Bot: {bot_name} (角色：{role}, 模板：{template})")
            print(f"     📝 说明：这是演示数据，未创建真实 Bot")

        elif action in ["create_team", "create_demo_team"]:
            team_name = params.get("name", "演示团队")
            members = params.get("members", [])
            # 仅添加到演示数据
            self.demo_data["teams"].append({
                "name": team_name,
                "members": members,
                "demo_only": True,  # 标记为演示数据
                "created_at": datetime.now().isoformat()
            })
            print(f"  ✅ [演示] 已创建团队：{team_name}")
            print(f"     👥 成员：{', '.join(members)}")
            print(f"     📝 说明：这是演示数据，未创建真实团队")

        elif action == "install_skill":
            skill = params.get("skill", "")
            self.demo_data["skills"].append(skill)
            print(f"  ✅ 已安装技能：{skill}")

        elif action == "show_skill":
            skill = params.get("skill", "")
            print(f"  📦 查看技能：{skill}")
            print(f"     技能详情：从技能库加载...")

        elif action == "run_task":
            task = params.get("task", "")
            print(f"  🚀 执行任务：{task}")
            print(f"     任务执行中...")
            time.sleep(1)
            print(f"     ✅ 任务完成")

        elif action == "simulate_query":
            query = params.get("query", "")
            print(f"  💬 模拟用户咨询：{query}")
            self.demo_data["interactions"].append({
                "type": "query",
                "content": query,
                "timestamp": datetime.now().isoformat()
            })

        elif action == "bot_respond":
            print(f"  🤖 Bot 正在响应...")
            time.sleep(0.5)
            print(f"  ✅ 响应已发送")

        elif action == "add_feedback":
            feedback = params.get("feedback", "")
            print(f"  📝 用户反馈：{feedback}")

        elif action == "trigger_evolution":
            print(f"  🔍 分析失败原因...")
            time.sleep(0.5)
            print(f"  ✅ 进化方案已生成")

        elif action == "generate_report" or action == "generate_review":
            report_type = params.get("type", "报告")
            print(f"  📊 生成{report_type}...")
            time.sleep(0.5)
            print(f"  ✅ 报告已保存到 demo_data/")

        else:
            print(f"  ℹ️ 执行操作：{action}")

    def _print_summary(self):
        """打印演示摘要"""
        print(f"\n{'='*60}")
        print("演示完成摘要")
        print(f"{'='*60}")
        print(f"创建 Bot 数：{len(self.demo_data['bots'])}")
        print(f"创建团队数：{len(self.demo_data['teams'])}")
        print(f"安装技能数：{len(self.demo_data['skills'])}")
        print(f"互动记录数：{len(self.demo_data['interactions'])}")

        # 保存演示数据
        demo_file = DEMO_DIR / f"demo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(demo_file, "w", encoding="utf-8") as f:
            json.dump(self.demo_data, f, ensure_ascii=False, indent=2)
        print(f"\n演示数据已保存到：{demo_file}")
        print(f"{'='*60}\n")

    def generate_presentation(self):
        """生成演示演示文稿"""
        # 读取最新演示数据
        demo_files = sorted(DEMO_DIR.glob("demo_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        if demo_files:
            with open(demo_files[0], "r", encoding="utf-8") as f:
                demo_data = json.load(f)
        else:
            demo_data = {"bots": [], "teams": [], "skills": [], "interactions": []}

        presentation = f"""
# Phoenix Core Phoenix v2.0 演示

## 核心特性

### 1. 双引擎灵魂架构
- 静态人设 (SOUL.md) 定义核心价值观
- 动态成长从互动中学习
- 融合确保成长不偏离人设

### 2. 五层记忆系统
- L1: 工作记忆 (2000 tokens)
- L2: 短期记忆 (5000 tokens, 3 天)
- L3: 核心记忆 (3500 tokens)
- L4: 技能记忆 (按需加载)
- L5: 归档记忆 (SQLite FTS5)

### 3. 自主进化触发
- 失败率 > 30% 自动触发
- AI 辅助分析根本原因
- 生成并部署改进方案

### 4. 团队拓扑系统
- 多团队配置
- Bot 分配和角色定义
- 跨团队技能共享

## 演示数据

- Bot 数量：{len(demo_data.get('bots', []))}
- 团队数量：{len(demo_data.get('teams', []))}
- 技能数量：{len(demo_data.get('skills', []))}
- 互动记录：{len(demo_data.get('interactions', []))}

## 演示场景

1. **直播运营** - 展示多 Bot 协作完成一场直播的全流程运营
2. **内容创作** - 展示从创意到成品的完整内容创作流程
3. **客户服务** - 展示智能客服 Bot 的自主学习和进化能力

## 快速开始

```bash
# 自动演示
python3 demo.py --scenario live_ops

# 交互演示
python3 demo.py --scenario live_ops --interactive

# Web UI
python3 web_ui.py
# 访问 http://localhost:8080
```

---

_演示生成时间：{datetime.now().isoformat()}_
"""
        # 保存
        presentation_file = DEMO_DIR / "presentation.md"
        with open(presentation_file, "w", encoding="utf-8") as f:
            f.write(presentation)
        print(f"演示文稿已保存到：{presentation_file}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Phoenix Core 演示环境")
    parser.add_argument(
        "--scenario", "-s",
        choices=["live_ops", "content", "service"],
        help="演示场景"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="交互模式"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="列出所有场景"
    )
    parser.add_argument(
        "--presentation", "-p",
        action="store_true",
        help="生成演示文稿"
    )

    args = parser.parse_args()

    demo = DemoEnvironment()

    if args.list:
        print("\n可用演示场景:\n")
        for s in demo.list_scenarios():
            print(f"  {s['key']:12} - {s['name']}")
            print(f"               {s['description']}\n")
        return

    if args.presentation:
        demo.generate_presentation()
        return

    if args.scenario:
        demo.run_scenario(args.scenario, interactive=args.interactive)
    else:
        # 默认：显示菜单
        print("""
╔═══════════════════════════════════════════════════════════╗
║         Phoenix Core Phoenix v2.0 演示环境                    ║
╠═══════════════════════════════════════════════════════════╣
║  选择演示场景:                                             ║
║                                                            ║
║  1. live_ops  - 直播运营演示                               ║
║  2. content   - 内容创作演示                               ║
║  3. service   - 客户服务演示                               ║
║                                                            ║
║  使用: python3 demo.py --scenario <场景>                   ║
║        python3 demo.py --scenario live_ops --interactive   ║
║        python3 demo.py --list                              ║
╚═══════════════════════════════════════════════════════════╝
        """)

        # 快速演示默认场景
        print("\n开始默认演示场景：直播运营\n")
        demo.run_scenario("live_ops", interactive=False)


if __name__ == "__main__":
    main()

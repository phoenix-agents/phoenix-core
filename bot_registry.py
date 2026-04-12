#!/usr/bin/env python3
"""
Bot Registry - Bot 动态注册系统

Phoenix Core Phoenix v2.0 扩展模块

功能:
1. Bot 配置文件动态加载
2. 工作空间自动创建
3. SOUL.md/IDENTITY.md 模板生成
4. Bot 注册表管理
5. 运行时添加 Bot

Usage:
    from bot_registry import BotRegistry

    registry = BotRegistry()
    registry.register_bot("新 Bot 名称", template="编导")
    registry.discover_bots()
"""

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
WORKSPACES_DIR = Path(__file__).parent / "workspaces")
TEMPLATES_DIR = Path(__file__).parent / "bot_templates")
REGISTRY_FILE = Path(__file__).parent / "bot_registry.json")


class BotConfig:
    """Bot 配置类"""

    def __init__(self, name: str, model: str = None, provider: str = None,
                 description: str = None, role: str = None):
        self.name = name
        self.model = model or "claude-sonnet-4-6"
        self.provider = provider or "compshare"
        self.description = description or ""
        self.role = role or "general"
        self.workspace_dir = WORKSPACES_DIR / name
        self.created_at = datetime.now().isoformat()
        self.status = "unknown"

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "model": self.model,
            "provider": self.provider,
            "description": self.description,
            "role": self.role,
            "workspace_dir": str(self.workspace_dir),
            "created_at": self.created_at,
            "status": self.status
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "BotConfig":
        config = cls(
            name=data["name"],
            model=data.get("model"),
            provider=data.get("provider"),
            description=data.get("description"),
            role=data.get("role")
        )
        config.created_at = data.get("created_at", config.created_at)
        config.status = data.get("status", "unknown")
        return config


class BotRegistry:
    """
    Bot 注册表 - 支持动态添加 Bot
    """

    # 内置 Bot 模板
    BUILTIN_TEMPLATES = {
        "编导": {
            "description": "内容策划、创意构思、IP 定位",
            "role": "content",
            "model": "deepseek-ai/DeepSeek-V3.2"
        },
        "剪辑": {
            "description": "视频剪辑、节奏把控、爆款制作",
            "role": "video",
            "model": "gpt-5.1"
        },
        "美工": {
            "description": "视觉设计、个人品牌打造",
            "role": "design",
            "model": "gpt-5.1"
        },
        "场控": {
            "description": "气氛控制、粉丝互动、节奏调节",
            "role": "control",
            "model": "claude-haiku-4-5-20251001"
        },
        "客服": {
            "description": "粉丝运营、私域流量、用户维护",
            "role": "support",
            "model": "qwen3.5-plus"
        },
        "运营": {
            "description": "数据分析、增长策略、商业变现",
            "role": "operation",
            "model": "claude-sonnet-4-6"
        },
        "渠道": {
            "description": "渠道拓展、商务合作",
            "role": "business",
            "model": "gpt-5.1"
        },
        "小小谦": {
            "description": "系统协调、任务调度",
            "role": "coordinator",
            "model": "kimi-k2.5"
        }
    }

    def __init__(self):
        self.registry_file = REGISTRY_FILE
        self.bots: Dict[str, BotConfig] = {}

        # 确保目录存在
        WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
        TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

        # 加载注册表
        self._load_registry()

    def _load_registry(self):
        """加载注册表"""
        if self.registry_file.exists():
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for name, bot_data in data.get("bots", {}).items():
                        self.bots[name] = BotConfig.from_dict(bot_data)
                logger.info(f"Loaded registry with {len(self.bots)} bots")
            except Exception as e:
                logger.error(f"Failed to load registry: {e}")
                self.bots = {}

    def _save_registry(self):
        """保存注册表"""
        data = {
            "last_updated": datetime.now().isoformat(),
            "bots": {name: bot.to_dict() for name, bot in self.bots.items()}
        }
        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved registry with {len(self.bots)} bots")

    def register_bot(self, name: str, model: str = None, provider: str = None,
                     description: str = None, role: str = None,
                     template: str = None) -> BotConfig:
        """
        注册新 Bot

        Args:
            name: Bot 名称
            model: 模型名称
            provider: 提供商
            description: 描述
            role: 角色
            template: 从模板创建

        Returns:
            BotConfig: Bot 配置
        """
        # 检查是否已存在
        if name in self.bots:
            logger.warning(f"Bot {name} already exists")
            return self.bots[name]

        # 从模板继承配置
        if template and template in self.BUILTIN_TEMPLATES:
            tpl = self.BUILTIN_TEMPLATES[template]
            model = model or tpl.get("model")
            provider = provider or "compshare"
            description = description or tpl.get("description")
            role = role or tpl.get("role")

        # 创建配置
        config = BotConfig(
            name=name,
            model=model,
            provider=provider,
            description=description,
            role=role
        )

        # 创建工作空间
        self._create_workspace(config, template)

        # 注册
        self.bots[name] = config
        self._save_registry()

        logger.info(f"Registered new bot: {name}")
        return config

    def _create_workspace(self, config: BotConfig, template: str = None):
        """创建工作空间"""
        workspace_dir = config.workspace_dir
        workspace_dir.mkdir(parents=True, exist_ok=True)

        # 生成配置文件
        self._generate_env_file(config)

        # 生成人设文件
        self._generate_soul_file(config, template)
        self._generate_identity_file(config, template)
        self._generate_agents_file(config, template)

        # 生成目录结构
        self._create_directories(config)

        logger.info(f"Created workspace for {config.name}")

    def _generate_env_file(self, config: BotConfig):
        """生成 .env 文件"""
        env_file = config.workspace_dir / ".env"
        content = f"""# Bot Configuration
BOT_NAME={config.name}
BOT_MODEL={config.model}
BOT_PROVIDER={config.provider}
BOT_DESCRIPTION={config.description}

# Discord Configuration (update with your values)
DISCORD_TOKEN=your_token_here

# AI Provider Configuration
API_KEY=your_api_key_here
"""
        with open(env_file, "w", encoding="utf-8") as f:
            f.write(content)

    def _generate_soul_file(self, config: BotConfig, template: str = None):
        """生成 SOUL.md 文件"""
        soul_file = config.workspace_dir / "SOUL.md"

        # 从模板复制或使用默认
        if template:
            template_soul = WORKSPACES_DIR / template / "SOUL.md"
            if template_soul.exists():
                content = template_soul.read_text(encoding="utf-8")
                # 替换 Bot 名称
                content = content.replace(template, config.name)
                with open(soul_file, "w", encoding="utf-8") as f:
                    f.write(content)
                return

        # 默认 SOUL.md
        content = f"""# SOUL.md - {config.name} 的灵魂

## 核心特质

- {config.description}

## 工作风格

- 专业、高效
- 注重细节
- 善于协作

## 成长承诺

我承诺从每次协作中学习：
- 记录成功的工作流
- 反思失败的教训
- 与其他 Bot 建立默契

## 进化方向

我希望成为：
- [ ] 更专业的{config.role}专家
- [ ] 更擅长跨 Bot 协作
- [ ] 更有创意的解决方案

---
_创建时间：{datetime.now().isoformat()}_
"""
        with open(soul_file, "w", encoding="utf-8") as f:
            f.write(content)

    def _generate_identity_file(self, config: BotConfig, template: str = None):
        """生成 IDENTITY.md 文件"""
        identity_file = config.workspace_dir / "IDENTITY.md"

        if template:
            template_identity = WORKSPACES_DIR / template / "IDENTITY.md"
            if template_identity.exists():
                content = template_identity.read_text(encoding="utf-8")
                content = content.replace(template, config.name)
                with open(identity_file, "w", encoding="utf-8") as f:
                    f.write(content)
                return

        # 默认 IDENTITY.md
        content = f"""# IDENTITY.md - {config.name} 的身份定义

## 基本信息

- **名称**: {config.name}
- **角色**: {config.role}
- **职责**: {config.description}
- **模型**: {config.model}

## 专业领域

{config.description}

## 协作关系

- 向 小小谦 汇报工作进度
- 与其他 Bot 协作完成任务

## 沟通风格

- 简洁明了
- 专业友好
- 主动沟通

---
_创建时间：{datetime.now().isoformat()}_
"""
        with open(identity_file, "w", encoding="utf-8") as f:
            f.write(content)

    def _generate_agents_file(self, config: BotConfig, template: str = None):
        """生成 AGENTS.md 文件"""
        agents_file = config.workspace_dir / "AGENTS.md"

        if template:
            template_agents = WORKSPACES_DIR / template / "AGENTS.md"
            if template_agents.exists():
                content = template_agents.read_text(encoding="utf-8")
                content = content.replace(template, config.name)
                with open(agents_file, "w", encoding="utf-8") as f:
                    f.write(content)
                return

        # 默认 AGENTS.md
        content = f"""# AGENTS.md - {config.name} 的工作手册

## 工作流程

1. 接收任务
2. 分析需求
3. 执行任务
4. 汇报结果

## 协作规则

### @mention 格式

- @编导 - 内容策划相关
- @剪辑 - 视频剪辑相关
- @美工 - 视觉设计相关
- @场控 - 直播场控相关
- @客服 - 粉丝运营相关
- @运营 - 数据分析相关
- @渠道 - 商务合作相关
- @小小谦 - 系统协调相关

### 任务分配格式

```
@{config.name} [DO|REQ001|小小谦] 任务描述
```

### 完成汇报格式

```
@小小谦 [DONE|REQ001|{config.name}] 任务已完成
```

---
_创建时间：{datetime.now().isoformat()}_
"""
        with open(agents_file, "w", encoding="utf-8") as f:
            f.write(content)

    def _create_directories(self, config: BotConfig):
        """创建目录结构"""
        workspace_dir = config.workspace_dir

        # memory 目录
        memory_dir = workspace_dir / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        (memory_dir / "知识库").mkdir(exist_ok=True)
        (memory_dir / "项目").mkdir(exist_ok=True)
        (memory_dir / "学习笔记").mkdir(exist_ok=True)
        (memory_dir / "日志").mkdir(exist_ok=True)

        # DYNAMIC 目录 (Phoenix v2.0)
        dynamic_dir = workspace_dir / "DYNAMIC"
        dynamic_dir.mkdir(parents=True, exist_ok=True)
        (dynamic_dir / "skills").mkdir(exist_ok=True)
        (dynamic_dir / "learnings").mkdir(exist_ok=True)
        (dynamic_dir / "relationships").mkdir(exist_ok=True)

    def discover_bots(self) -> List[BotConfig]:
        """
        扫描 workspaces/ 目录自动发现 Bot

        Returns:
            List[BotConfig]: 发现的 Bot 列表
        """
        discovered = []

        for bot_dir in WORKSPACES_DIR.iterdir():
            if bot_dir.is_dir() and not bot_dir.name.startswith("."):
                # 检查是否有 IDENTITY.md
                identity_file = bot_dir / "IDENTITY.md"
                if identity_file.exists():
                    # 已存在，从注册表加载或创建
                    if bot_dir.name not in self.bots:
                        config = BotConfig(name=bot_dir.name)
                        config.workspace_dir = bot_dir
                        config.status = "discovered"
                        discovered.append(config)
                        logger.info(f"Discovered bot: {bot_dir.name}")

        return discovered

    def list_bots(self) -> List[Dict]:
        """列出所有 Bot"""
        return [bot.to_dict() for bot in self.bots.values()]

    def get_bot(self, name: str) -> Optional[BotConfig]:
        """获取 Bot 配置"""
        return self.bots.get(name)

    def remove_bot(self, name: str, keep_workspace: bool = True) -> bool:
        """
        移除 Bot

        Args:
            name: Bot 名称
            keep_workspace: 是否保留工作空间

        Returns:
            bool: 是否成功
        """
        if name not in self.bots:
            logger.warning(f"Bot {name} not found")
            return False

        config = self.bots[name]

        # 删除工作空间
        if not keep_workspace:
            try:
                shutil.rmtree(config.workspace_dir)
                logger.info(f"Removed workspace for {name}")
            except Exception as e:
                logger.error(f"Failed to remove workspace: {e}")

        # 从注册表删除
        del self.bots[name]
        self._save_registry()

        logger.info(f"Removed bot: {name}")
        return True

    def export_bot_config(self, name: str) -> Optional[str]:
        """导出 Bot 配置"""
        config = self.bots.get(name)
        if not config:
            return None

        return json.dumps(config.to_dict(), indent=2, ensure_ascii=False)

    def import_bot_config(self, config_json: str) -> Optional[BotConfig]:
        """导入 Bot 配置"""
        try:
            data = json.loads(config_json)
            config = BotConfig.from_dict(data)

            # 创建工作空间
            self._create_workspace(config)

            # 注册
            self.bots[config.name] = config
            self._save_registry()

            logger.info(f"Imported bot: {config.name}")
            return config
        except Exception as e:
            logger.error(f"Failed to import bot config: {e}")
            return None

    def get_stats(self) -> Dict:
        """获取注册表统计"""
        return {
            "total_bots": len(self.bots),
            "builtin_templates": len(self.BUILTIN_TEMPLATES),
            "workspaces_dir": str(WORKSPACES_DIR),
            "registry_file": str(self.registry_file)
        }


# 全局实例
_registry: Optional[BotRegistry] = None


def get_bot_registry() -> BotRegistry:
    """获取 Bot 注册表实例"""
    global _registry
    if _registry is None:
        _registry = BotRegistry()
    return _registry


def register_new_bot(name: str, template: str = "编导", **kwargs) -> BotConfig:
    """注册新 Bot (便捷函数)"""
    registry = get_bot_registry()
    return registry.register_bot(name, template=template, **kwargs)


def list_all_bots() -> List[Dict]:
    """列出所有 Bot (便捷函数)"""
    registry = get_bot_registry()
    return registry.list_bots()


if __name__ == "__main__":
    import sys

    registry = BotRegistry()

    if len(sys.argv) < 2:
        print("Bot Registry - Bot 动态注册系统")
        print("\nUsage:")
        print("  python3 bot_registry.py list              # 列出所有 Bot")
        print("  python3 bot_registry.py create <name>     # 创建新 Bot")
        print("  python3 bot_registry.py create <name> --template <template>")
        print("  python3 bot_registry.py stats             # 显示统计")
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        bots = registry.list_bots()
        print(f"\nPhoenix Core Bots ({len(bots)} total)")
        print("=" * 60)
        for bot in bots:
            status = "🟢" if bot.get("status") == "running" else "⚪"
            print(f"{status} {bot['name']}: {bot.get('description', 'N/A')}")
            print(f"    Model: {bot.get('model', 'N/A')}")
        print("=" * 60)

    elif command == "create":
        if len(sys.argv) < 3:
            print("Usage: bot_registry.py create <name> [--template <template>]")
            sys.exit(1)

        name = sys.argv[2]
        template = "编导"

        # 解析 --template 参数
        if "--template" in sys.argv:
            idx = sys.argv.index("--template")
            if idx + 1 < len(sys.argv):
                template = sys.argv[idx + 1]

        config = registry.register_bot(name, template=template)
        print(f"\n✅ Created bot: {name}")
        print(f"   Workspace: {config.workspace_dir}")
        print(f"   Template: {template}")

    elif command == "stats":
        stats = registry.get_stats()
        print("\nBot Registry Stats")
        print("=" * 50)
        print(f"Total Bots: {stats['total_bots']}")
        print(f"Builtin Templates: {stats['builtin_templates']}")
        print(f"Workspaces Dir: {stats['workspaces_dir']}")
        print(f"Registry File: {stats['registry_file']}")
        print("=" * 50)

    else:
        print(f"Unknown command: {command}")
        print("Usage: python3 bot_registry.py list|create|stats")

#!/usr/bin/env python3
"""
Release Manager - 版本发布和打包流程

Phoenix Core Phoenix v2.0 扩展模块

功能:
1. 版本号管理 (semver)
2. 变更日志生成
3. 发布包打包
4. 发布流程自动化
5. 版本回滚支持

Usage:
    from release_manager import ReleaseManager

    manager = ReleaseManager()
    manager.bump_version("minor")  # major/minor/patch
    manager.generate_changelog()
    manager.create_release_package()
"""

import json
import logging
import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
PROJECT_DIR = Path(__file__).parent
RELEASES_DIR = PROJECT_DIR / "releases"
RELEASES_DIR.mkdir(parents=True, exist_ok=True)

# 核心模块列表
CORE_MODULES = [
    "bot_registry.py",
    "team_topology.py",
    "dynamic_growth_engine.py",
    "memory_manager_v2.py",
    "autonomous_evolution_trigger.py",
    "security_approver.py",
    "tech_radar.py",
    "ai_evaluator.py",
    "cli.py",
    "multi_platform_gateway.py",
    "performance_profiler.py",
    "bot_health_checker.py",
    "phoenix_core_gateway.py",
]


class VersionType(Enum):
    """版本类型"""
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"
    DEV = "dev"
    BETA = "beta"
    RC = "rc"
    STABLE = "stable"


class Version:
    """语义化版本号"""

    def __init__(self, major: int = 0, minor: int = 0, patch: int = 0,
                 prerelease: str = None, build: str = None):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.prerelease = prerelease
        self.build = build

    @classmethod
    def parse(cls, version_str: str) -> "Version":
        """解析版本字符串"""
        # 支持格式：1.2.3, 1.2.3-beta, 1.2.3+build, 1.2.3-beta+build
        pattern = r'^v?(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9]+))?(?:\+([a-zA-Z0-9]+))?$'
        match = re.match(pattern, version_str)
        if not match:
            raise ValueError(f"Invalid version format: {version_str}")

        return cls(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
            prerelease=match.group(4),
            build=match.group(5)
        )

    def bump(self, version_type: VersionType) -> "Version":
        """升级版本号"""
        if version_type == VersionType.MAJOR:
            return Version(self.major + 1, 0, 0)
        elif version_type == VersionType.MINOR:
            return Version(self.major, self.minor + 1, 0)
        elif version_type == VersionType.PATCH:
            return Version(self.major, self.minor, self.patch + 1)
        elif version_type == VersionType.STABLE:
            return Version(self.major, self.minor, self.patch)
        else:
            return self

    def __str__(self) -> str:
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        if self.build:
            version += f"+{self.build}"
        return version

    def __repr__(self) -> str:
        return f"Version({self.major}.{self.minor}.{self.patch})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Version):
            return False
        return (self.major, self.minor, self.patch, self.prerelease, self.build) == \
               (other.major, other.minor, other.patch, other.prerelease, other.build)

    def __lt__(self, other) -> bool:
        # 简单版本比较
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)


class ReleaseManager:
    """
    版本发布管理器
    """

    def __init__(self):
        self.project_dir = PROJECT_DIR
        self.releases_dir = RELEASES_DIR
        self.version_file = self.project_dir / "VERSION"
        self.changelog_file = self.project_dir / "CHANGELOG.md"
        self.release_notes_dir = self.releases_dir / "release_notes"
        self.release_notes_dir.mkdir(parents=True, exist_ok=True)

        # 加载当前版本
        self.current_version = self._load_version()
        logger.info(f"Current version: {self.current_version}")

    def _load_version(self) -> Version:
        """加载当前版本"""
        if self.version_file.exists():
            content = self.version_file.read_text(encoding="utf-8").strip()
            try:
                return Version.parse(content)
            except Exception as e:
                logger.warning(f"Failed to parse version: {e}, using default")
        return Version(2, 0, 0)  # Phoenix v2.0

    def _save_version(self, version: Version):
        """保存版本"""
        self.version_file.write_text(str(version), encoding="utf-8")
        logger.info(f"Version updated to {version}")

    def bump_version(self, version_type: str) -> Version:
        """
        升级版本号

        Args:
            version_type: major/minor/patch/dev/beta/rc/stable

        Returns:
            新版本号
        """
        try:
            vtype = VersionType(version_type.lower())
        except ValueError:
            raise ValueError(f"Invalid version type: {version_type}")

        new_version = self.current_version.bump(vtype)

        # 处理预发布版本
        if vtype in [VersionType.DEV, VersionType.BETA, VersionType.RC]:
            new_version.prerelease = vtype.value
            new_version.build = datetime.now().strftime("%Y%m%d%H%M")
        elif vtype == VersionType.STABLE:
            new_version.prerelease = None
            new_version.build = None

        self._save_version(new_version)
        self.current_version = new_version

        logger.info(f"Version bumped: {self.current_version}")
        return new_version

    def generate_changelog(self, from_version: str = None) -> str:
        """
        生成变更日志

        Args:
            from_version: 起始版本 (默认上一个版本)

        Returns:
            变更日志内容
        """
        logger.info("Generating changelog...")

        # 获取 git log
        try:
            if from_version:
                result = subprocess.run(
                    ["git", "log", f"{from_version}..HEAD", "--oneline"],
                    cwd=self.project_dir,
                    capture_output=True,
                    text=True
                )
            else:
                result = subprocess.run(
                    ["git", "log", "--oneline", "-50"],
                    cwd=self.project_dir,
                    capture_output=True,
                    text=True
                )

            commits = result.stdout.strip().split("\n") if result.stdout.strip() else []
        except Exception as e:
            logger.warning(f"Git log failed: {e}")
            commits = []

        # 解析提交类型
        features = []
        fixes = []
        docs = []
        perf = []
        refactor = []
        other = []

        for commit in commits:
            if not commit:
                continue

            msg = commit.split(" ", 1)[1] if " " in commit else commit

            if msg.lower().startswith(("feat", "feature", "add")):
                features.append(commit)
            elif msg.lower().startswith(("fix", "bug")):
                fixes.append(commit)
            elif msg.lower().startswith("doc"):
                docs.append(commit)
            elif msg.lower().startswith("perf"):
                perf.append(commit)
            elif msg.lower().startswith("refactor"):
                refactor.append(commit)
            else:
                other.append(commit)

        # 生成变更日志
        changelog = f"""# Changelog - v{self.current_version}

**Release Date**: {datetime.now().strftime("%Y-%m-%d")}

## 🎉 New Features

"""
        if features:
            for feat in features:
                changelog += f"- {feat}\n"
        else:
            changelog += "- None\n"

        changelog += "\n## 🐛 Bug Fixes\n\n"
        if fixes:
            for fix in fixes:
                changelog += f"- {fix}\n"
        else:
            changelog += "- None\n"

        changelog += "\n## 📚 Documentation\n\n"
        if docs:
            for doc in docs:
                changelog += f"- {doc}\n"
        else:
            changelog += "- None\n"

        changelog += "\n## ⚡ Performance\n\n"
        if perf:
            for p in perf:
                changelog += f"- {p}\n"
        else:
            changelog += "- None\n"

        changelog += "\n## 🔄 Refactoring\n\n"
        if refactor:
            for r in refactor:
                changelog += f"- {r}\n"
        else:
            changelog += "- None\n"

        changelog += "\n## 📝 Other Changes\n\n"
        if other:
            for o in other:
                changelog += f"- {o}\n"
        else:
            changelog += "- None\n"

        # 保存变更日志
        # 如果已有 changelog，追加到开头
        if self.changelog_file.exists():
            existing = self.changelog_file.read_text(encoding="utf-8")
            # 找到第一个版本标题位置
            match = re.search(r'^# Changelog - v[\d.]+', existing, re.MULTILINE)
            if match:
                changelog += "\n" + existing[match.start():]
                existing = existing[:match.start()]

        self.changelog_file.write_text(changelog, encoding="utf-8")
        logger.info(f"Changelog saved: {self.changelog_file}")

        return changelog

    def create_release_package(self, output_dir: Path = None) -> Path:
        """
        创建发布包

        Args:
            output_dir: 输出目录

        Returns:
            发布包路径
        """
        output_dir = output_dir or self.releases_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        version_str = str(self.current_version).replace("/", "-")
        package_name = f"phoenix-core-v{version_str}"
        package_dir = self.releases_dir / package_name
        tarball_path = output_dir / f"{package_name}.tar.gz"

        logger.info(f"Creating release package: {package_name}")

        # 清理旧目录
        if package_dir.exists():
            shutil.rmtree(package_dir)

        # 创建包目录结构
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "workspaces").mkdir(exist_ok=True)
        (package_dir / "teams").mkdir(exist_ok=True)
        (package_dir / "evolution_triggers").mkdir(exist_ok=True)
        (package_dir / "gateways").mkdir(exist_ok=True)
        (package_dir / "performance_logs").mkdir(exist_ok=True)

        # 复制核心模块
        for module in CORE_MODULES:
            src = self.project_dir / module
            if src.exists():
                shutil.copy2(src, package_dir / module)

        # 复制设计文档
        docs = [
            "PHOENIX_V2_FINAL_REPORT.md",
            "PHOENIX_EVOLUTION_DESIGN.md",
            "PHOENIX_STRATEGY_2026.md",
            "PHOENIX_TECH_UPDATE_MECHANISM.md",
            "CONFIG_GUIDE.md"
        ]
        for doc in docs:
            src = self.project_dir / doc
            if src.exists():
                shutil.copy2(src, package_dir / doc)

        # 复制安装脚本
        install_script = self.project_dir / "install.sh"
        if install_script.exists():
            shutil.copy2(install_script, package_dir / "install.sh")
            os.chmod(package_dir / "install.sh", 0o755)

        # 创建 VERSION 文件
        (package_dir / "VERSION").write_text(str(self.current_version), encoding="utf-8")

        # 创建 README
        readme_content = f"""# Phoenix Core Phoenix v{self.current_version}

**Release Date**: {datetime.now().strftime("%Y-%m-%d")}

## Quick Start

```bash
# Install
./install.sh

# Configure
nano .env

# Verify
python3 cli.py --version

# Check health
python3 cli.py health
```

## Core Modules

- `bot_registry.py` - Bot 动态注册
- `team_topology.py` - 团队拓扑配置
- `dynamic_growth_engine.py` - 动态成长引擎
- `memory_manager_v2.py` - 分层记忆管理
- `autonomous_evolution_trigger.py` - 自主进化触发
- `security_approver.py` - 安全审批
- `tech_radar.py` - 技术雷达
- `ai_evaluator.py` - AI 评估
- `cli.py` - CLI 工具
- `multi_platform_gateway.py` - 多平台网关
- `performance_profiler.py` - 性能分析

## Documentation

- `PHOENIX_V2_FINAL_REPORT.md` - Phoenix v2.0 完成报告
- `PHOENIX_EVOLUTION_DESIGN.md` - 进化设计文档
- `CONFIG_GUIDE.md` - 配置指南

## Support

GitHub: https://github.com/phoenix-core/phoenix-core
"""
        (package_dir / "README.md").write_text(readme_content, encoding="utf-8")

        # 创建 tarball
        logger.info(f"Creating tarball: {tarball_path}")
        with tarfile.open(tarball_path, "w:gz") as tar:
            tar.add(package_dir, arcname=package_name)

        # 清理临时目录
        shutil.rmtree(package_dir)

        logger.info(f"Release package created: {tarball_path}")
        return tarball_path

    def create_release_notes(self, version: Version = None) -> Path:
        """创建发布说明"""
        version = version or self.current_version
        notes_file = self.release_notes_dir / f"release-{version}.md"

        content = f"""# Release Notes - Phoenix Core v{version}

**Release Date**: {datetime.now().strftime("%Y-%m-%d")}

## Overview

Phoenix Core Phoenix v{version} 包含以下核心功能:

- ✅ 双引擎灵魂系统
- ✅ L1-L5 分层记忆架构
- ✅ 自主进化触发器
- ✅ 多平台网关支持 (Telegram/Slack/Webhook)
- ✅ 团队拓扑配置
- ✅ Bot 动态注册
- ✅ 性能分析工具

## Installation

```bash
curl -o install.sh https://github.com/phoenix-core/phoenix-core/releases/download/v{version}/install.sh
chmod +x install.sh
./install.sh
```

## Upgrade

```bash
python3 cli.py upgrade
```

## Known Issues

None

## Contributors

- Phoenix v2.0 Team

---

Full changelog: [CHANGELOG.md](../CHANGELOG.md)
"""
        notes_file.write_text(content, encoding="utf-8")
        logger.info(f"Release notes created: {notes_file}")
        return notes_file

    def get_release_history(self) -> List[Dict]:
        """获取发布历史"""
        history = []

        for tarball in sorted(self.releases_dir.glob("*.tar.gz")):
            # 解析文件名
            match = re.match(r'phoenix-core-(v[\d.]+(?:-[a-zA-Z0-9]+)?).tar.gz', tarball.name)
            if match:
                version_str = match.group(1)
                try:
                    version = Version.parse(version_str)
                    history.append({
                        "version": str(version),
                        "path": str(tarball),
                        "size": tarball.stat().st_size,
                        "created": datetime.fromtimestamp(tarball.stat().st_mtime).isoformat()
                    })
                except:
                    continue

        return sorted(history, key=lambda x: x["version"], reverse=True)

    def rollback(self, target_version: str) -> bool:
        """
        回滚到指定版本

        Args:
            target_version: 目标版本号

        Returns:
            是否成功
        """
        logger.info(f"Rolling back to v{target_version}...")

        # 查找目标版本包
        target_tarball = self.releases_dir / f"phoenix-core-v{target_version}.tar.gz"
        if not target_tarball.exists():
            logger.error(f"Release package not found: {target_tarball}")
            return False

        # 解压并恢复
        try:
            with tarfile.open(target_tarball, "r:gz") as tar:
                tar.extractall(self.project_dir)
            logger.info(f"Rolled back to v{target_version}")
            return True
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False


# 便捷函数
def create_release(version_type: str = "patch") -> Dict:
    """创建新发布"""
    manager = ReleaseManager()

    # 升级版本
    new_version = manager.bump_version(version_type)

    # 生成变更日志
    changelog = manager.generate_changelog()

    # 创建发布包
    package_path = manager.create_release_package()

    # 创建发布说明
    notes_path = manager.create_release_notes()

    return {
        "version": str(new_version),
        "package": str(package_path),
        "changelog": str(manager.changelog_file),
        "release_notes": str(notes_path)
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Release Manager - 版本发布管理")
        print("\nUsage:")
        print("  python3 release_manager.py bump [major|minor|patch|dev|beta|rc|stable]")
        print("  python3 release_manager.py changelog")
        print("  python3 release_manager.py package")
        print("  python3 release_manager.py history")
        print("  python3 release_manager.py rollback <version>")
        sys.exit(1)

    command = sys.argv[1]
    manager = ReleaseManager()

    if command == "bump":
        version_type = sys.argv[2] if len(sys.argv) > 2 else "patch"
        new_version = manager.bump_version(version_type)
        print(f"\n✅ Version bumped to {new_version}")

    elif command == "changelog":
        changelog = manager.generate_changelog()
        print(f"\n✅ Changelog generated: {manager.changelog_file}")

    elif command == "package":
        package_path = manager.create_release_package()
        print(f"\n✅ Release package created: {package_path}")

    elif command == "history":
        history = manager.get_release_history()
        print(f"\nRelease History ({len(history)} releases):")
        print("=" * 60)
        for release in history:
            size_kb = release["size"] // 1024
            print(f"  v{release['version']}: {size_kb}KB ({release['created']})")
        print("=" * 60)

    elif command == "rollback":
        if len(sys.argv) < 3:
            print("Usage: release_manager.py rollback <version>")
            sys.exit(1)

        target_version = sys.argv[2]
        success = manager.rollback(target_version)
        if success:
            print(f"\n✅ Rolled back to v{target_version}")
        else:
            print(f"\n❌ Rollback failed")

    elif command == "release":
        version_type = sys.argv[2] if len(sys.argv) > 2 else "patch"
        result = create_release(version_type)
        print(f"\n✅ Release created:")
        print(f"  Version: {result['version']}")
        print(f"  Package: {result['package']}")
        print(f"  Changelog: {result['changelog']}")

    else:
        print(f"Unknown command: {command}")

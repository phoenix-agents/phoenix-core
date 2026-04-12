#!/usr/bin/env python3
"""
Skill Market - 技能市场系统

Phoenix Core Phoenix v2.0 扩展模块

功能:
1. 技能发布与分享
2. 技能安装与卸载
3. 技能版本管理
4. 技能评分与评论
5. 技能依赖管理

Usage:
    from skill_market import SkillMarket

    market = SkillMarket()
    market.publish_skill("技能名称", "技能描述", skill_md_path)
    market.install_skill("技能名称")
    market.list_available_skills()
"""

import json
import logging
import os
import shutil
import tarfile
import urllib.request
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
MARKET_DIR = Path(__file__).parent / "skill_market")
MARKET_DIR.mkdir(parents=True, exist_ok=True)

PUBLISHED_SKILLS_FILE = MARKET_DIR / "published_skills.json"
INSTALLED_SKILLS_FILE = MARKET_DIR / "installed_skills.json"
SKILL_PACKAGES_DIR = MARKET_DIR / "packages"
SKILL_PACKAGES_DIR.mkdir(parents=True, exist_ok=True)

# 内置技能模板
BUILTIN_SKILLS = {
    "内容策划工作流": {
        "version": "1.0.0",
        "author": "编导",
        "description": "完整的直播内容策划流程",
        "tags": ["策划", "直播", "工作流"],
        "dependencies": []
    },
    "视频剪辑检查单": {
        "version": "1.0.0",
        "author": "剪辑",
        "description": "视频剪辑质量检查清单",
        "tags": ["剪辑", "质检", "清单"],
        "dependencies": []
    },
    "数据分析报告": {
        "version": "1.0.0",
        "author": "运营",
        "description": "自动生成数据分析报告",
        "tags": ["数据分析", "报告", "自动化"],
        "dependencies": []
    },
    "粉丝互动话术": {
        "version": "1.0.0",
        "author": "场控",
        "description": "直播粉丝互动话术库",
        "tags": ["场控", "话术", "互动"],
        "dependencies": []
    }
}


class SkillStatus(Enum):
    """技能状态"""
    AVAILABLE = "available"
    INSTALLED = "installed"
    DISABLED = "disabled"
    OUTDATED = "outdated"


class SkillMarket:
    """
    技能市场管理器

    支持技能发布、安装、卸载、更新
    """

    def __init__(self, bot_name: str = None):
        self.bot_name = bot_name
        self.market_dir = MARKET_DIR
        self.packages_dir = SKILL_PACKAGES_DIR

        # 加载已发布技能
        self.published_skills: Dict[str, Dict] = {}
        self._load_published_skills()

        # 加载已安装技能
        self.installed_skills: Dict[str, Dict] = {}
        self._load_installed_skills()

        # 初始化内置技能
        self._init_builtin_skills()

        logger.info(f"Skill Market initialized: {len(self.published_skills)} published, {len(self.installed_skills)} installed")

    def _load_published_skills(self):
        """加载已发布技能"""
        if PUBLISHED_SKILLS_FILE.exists():
            try:
                with open(PUBLISHED_SKILLS_FILE, "r", encoding="utf-8") as f:
                    self.published_skills = json.load(f)
                logger.info(f"Loaded {len(self.published_skills)} published skills")
            except Exception as e:
                logger.error(f"Failed to load published skills: {e}")
                self.published_skills = {}

    def _save_published_skills(self):
        """保存已发布技能"""
        with open(PUBLISHED_SKILLS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.published_skills, f, indent=2, ensure_ascii=False)

    def _load_installed_skills(self):
        """加载已安装技能"""
        if INSTALLED_SKILLS_FILE.exists():
            try:
                with open(INSTALLED_SKILLS_FILE, "r", encoding="utf-8") as f:
                    self.installed_skills = json.load(f)
                logger.info(f"Loaded {len(self.installed_skills)} installed skills")
            except Exception as e:
                logger.error(f"Failed to load installed skills: {e}")
                self.installed_skills = {}

    def _save_installed_skills(self):
        """保存已安装技能"""
        with open(INSTALLED_SKILLS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.installed_skills, f, indent=2, ensure_ascii=False)

    def _init_builtin_skills(self):
        """初始化内置技能"""
        for skill_name, info in BUILTIN_SKILLS.items():
            if skill_name not in self.published_skills:
                self.published_skills[skill_name] = {
                    "name": skill_name,
                    "version": info.get("version", "1.0.0"),
                    "description": info.get("description", ""),
                    "tags": info.get("tags", []),
                    "dependencies": info.get("dependencies", []),
                    "author": info.get("author", "system"),
                    "status": SkillStatus.AVAILABLE.value,
                    "published_at": datetime.now().isoformat(),
                    "downloads": 0,
                    "rating": 5.0,
                    "reviews": []
                }
        self._save_published_skills()

    def publish_skill(self, skill_name: str, description: str,
                      skill_md_path: str, version: str = "1.0.0",
                      tags: List[str] = None, dependencies: List[str] = None) -> bool:
        """
        发布技能

        Args:
            skill_name: 技能名称
            description: 技能描述
            skill_md_path: 技能 Markdown 文件路径
            version: 版本号
            tags: 标签列表
            dependencies: 依赖技能列表

        Returns:
            bool: 是否成功
        """
        skill_path = Path(skill_md_path)
        if not skill_path.exists():
            logger.error(f"Skill file not found: {skill_path}")
            return False

        # 读取技能内容
        skill_content = skill_path.read_text(encoding="utf-8")

        # 创建技能包
        package_name = f"{skill_name.replace(' ', '_')}-{version}"
        package_dir = self.packages_dir / package_name
        package_dir.mkdir(parents=True, exist_ok=True)

        # 复制技能文件
        shutil.copy2(skill_path, package_dir / f"{skill_name}.md")

        # 创建元数据
        metadata = {
            "name": skill_name,
            "version": version,
            "description": description,
            "tags": tags or [],
            "dependencies": dependencies or [],
            "author": self.bot_name or "unknown",
            "created_at": datetime.now().isoformat(),
            "package_dir": str(package_dir)
        }

        # 保存元数据
        with open(package_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # 创建 tarball
        tarball_path = self.packages_dir / f"{package_name}.tar.gz"
        with tarfile.open(tarball_path, "w:gz") as tar:
            tar.add(package_dir, arcname=package_name)

        # 清理临时目录
        shutil.rmtree(package_dir)

        # 注册技能
        self.published_skills[skill_name] = {
            "name": skill_name,
            "version": version,
            "description": description,
            "tags": tags or [],
            "dependencies": dependencies or [],
            "author": self.bot_name or "unknown",
            "status": SkillStatus.AVAILABLE.value,
            "package_file": str(tarball_path),
            "published_at": datetime.now().isoformat(),
            "downloads": 0,
            "rating": 5.0,
            "reviews": []
        }

        self._save_published_skills()
        logger.info(f"Published skill: {skill_name} v{version}")
        return True

    def install_skill(self, skill_name: str, version: str = None) -> bool:
        """
        安装技能

        Args:
            skill_name: 技能名称
            version: 版本号 (默认最新版)

        Returns:
            bool: 是否成功
        """
        if skill_name not in self.published_skills:
            logger.error(f"Skill not found: {skill_name}")
            return False

        skill_info = self.published_skills[skill_name]

        # 检查依赖
        for dep in skill_info.get("dependencies", []):
            if dep not in self.installed_skills:
                logger.warning(f"Installing dependency: {dep}")
                self.install_skill(dep)

        # 获取技能包路径
        package_file = skill_info.get("package_file")
        if not package_file or not Path(package_file).exists():
            # 内置技能，需要创建
            logger.info(f"Creating built-in skill package: {skill_name}")
            self._create_builtin_package(skill_name, skill_info)
            package_file = skill_info.get("package_file")

        if not package_file:
            logger.error(f"No package file for skill: {skill_name}")
            return False

        # 解压技能包
        with tarfile.open(package_file, "r:gz") as tar:
            tar.extractall(self.packages_dir)

        # 确定安装目录
        bot_skills_dir = None
        if self.bot_name:
            bot_skills_dir = Path(f"workspaces/{self.bot_name}/DYNAMIC/skills")
            bot_skills_dir.mkdir(parents=True, exist_ok=True)
        else:
            # 系统级安装
            bot_skills_dir = self.market_dir / "global_skills"
            bot_skills_dir.mkdir(parents=True, exist_ok=True)

        # 复制技能文件
        package_name = f"{skill_name.replace(' ', '_')}-{skill_info['version']}"
        skill_package_dir = self.packages_dir / package_name

        for skill_file in skill_package_dir.glob("*.md"):
            shutil.copy2(skill_file, bot_skills_dir / skill_file.name)

        # 记录已安装技能
        self.installed_skills[skill_name] = {
            **skill_info,
            "installed_at": datetime.now().isoformat(),
            "status": SkillStatus.INSTALLED.value,
            "install_path": str(bot_skills_dir)
        }

        # 更新下载计数
        skill_info["downloads"] = skill_info.get("downloads", 0) + 1

        self._save_installed_skills()
        self._save_published_skills()

        logger.info(f"Installed skill: {skill_name} to {bot_skills_dir}")
        return True

    def _create_builtin_package(self, skill_name: str, skill_info: Dict):
        """创建内置技能包"""
        package_name = f"{skill_name.replace(' ', '_')}-{skill_info['version']}"
        package_dir = self.packages_dir / package_name
        package_dir.mkdir(parents=True, exist_ok=True)

        # 创建技能内容
        skill_content = self._generate_builtin_skill_content(skill_name, skill_info)
        skill_file = package_dir / f"{skill_name}.md"
        skill_file.write_text(skill_content, encoding="utf-8")

        # 保存元数据
        metadata = {
            **skill_info,
            "package_dir": str(package_dir)
        }
        with open(package_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # 创建 tarball
        tarball_path = self.packages_dir / f"{package_name}.tar.gz"
        with tarfile.open(tarball_path, "w:gz") as tar:
            tar.add(package_dir, arcname=package_name)

        # 清理临时目录
        shutil.rmtree(package_dir)

        # 更新技能信息
        skill_info["package_file"] = str(tarball_path)

    def _generate_builtin_skill_content(self, skill_name: str, skill_info: Dict) -> str:
        """生成内置技能内容"""
        templates = {
            "内容策划工作流": self._create_content_planning_skill(),
            "视频剪辑检查单": self._create_video_checklist_skill(),
            "数据分析报告": self._create_data_analysis_skill(),
            "粉丝互动话术": self._create_fan_interaction_skill()
        }
        return templates.get(skill_name, f"# {skill_name}\n\n{skill_info['description']}")

    def _create_content_planning_skill(self) -> str:
        """创建内容策划技能"""
        return """# 内容策划工作流

## 技能说明

完整的直播内容策划流程

## 步骤

### 1. 确定主题
- 分析目标受众
- 研究热点话题
- 确定核心信息

### 2. 内容结构
- 开场 (3-5 分钟): 吸引注意
- 主体 (15-20 分钟): 核心内容
- 互动 (5-10 分钟): 问答环节
- 结尾 (3-5 分钟): 总结 + CTA

### 3. 脚本撰写
- 关键话术准备
- 过渡语设计
- 互动点预设

### 4. 审核优化
- 内容合规检查
- 流程时间把控
- 风险点评估

## 输出

- 内容策划文档
- 直播脚本
- 互动题库
"""

    def _create_video_checklist_skill(self) -> str:
        """创建视频剪辑检查单技能"""
        return """# 视频剪辑检查单

## 技能说明

视频剪辑质量检查清单

## 检查项目

### 画面质量
- [ ] 分辨率符合要求 (1080p/4K)
- [ ] 帧率稳定 (30fps/60fps)
- [ ] 无明显噪点/闪烁
- [ ] 色彩校正完成

### 音频质量
- [ ] 音量平衡 (-6dB ~ -3dB)
- [ ] 无爆音/杂音
- [ ] BGM 音量适中
- [ ] 音效同步

### 剪辑节奏
- [ ] 转场自然流畅
- [ ] 节奏符合内容
- [ ] 无冗余片段
- [ ] 高潮点突出

### 包装元素
- [ ] 片头/片尾完整
- [ ] 字幕准确无误
- [ ] 贴纸/特效适当
- [ ] 品牌元素一致

## 输出

- 检查报告
- 修改建议
"""

    def _create_data_analysis_skill(self) -> str:
        """创建数据分析技能"""
        return """# 数据分析报告

## 技能说明

自动生成数据分析报告

## 分析维度

### 流量数据
- 观看人数/峰值
- 平均观看时长
- 流量来源分布

### 互动数据
- 评论数/点赞数/分享数
- 粉丝增长数
- 互动率计算

### 转化数据
- 点击率 (CTR)
- 转化率 (CVR)
- GMV/ROI

## 报告结构

1. 核心指标概览
2. 趋势分析
3. 对比分析
4. 问题诊断
5. 优化建议

## 输出

- 数据可视化图表
- 分析报告文档
- 优化行动清单
"""

    def _create_fan_interaction_skill(self) -> str:
        """创建粉丝互动技能"""
        return """# 粉丝互动话术

## 技能说明

直播粉丝互动话术库

## 话术分类

### 欢迎话术
- 欢迎新进直播间的朋友
- 欢迎老粉丝回归
- 欢迎特定等级/牌子粉丝

### 互动话术
- 提问引导
- 投票引导
- 评论引导

### 感谢话术
- 感谢礼物
- 感谢分享
- 感谢关注

### 促单话术
- 产品亮点强调
- 限时优惠提醒
- 库存紧张提示

## 使用原则

1. 真诚自然
2. 及时响应
3. 个性化称呼
4. 正向引导

## 输出

- 场景化话术列表
- 应对策略
"""

    def uninstall_skill(self, skill_name: str) -> bool:
        """
        卸载技能

        Args:
            skill_name: 技能名称

        Returns:
            bool: 是否成功
        """
        if skill_name not in self.installed_skills:
            logger.error(f"Skill not installed: {skill_name}")
            return False

        skill_info = self.installed_skills[skill_name]

        # 删除技能文件
        install_path = Path(skill_info.get("install_path", ""))
        skill_file = install_path / f"{skill_name}.md"
        if skill_file.exists():
            skill_file.unlink()

        # 从已安装列表移除
        del self.installed_skills[skill_name]
        self._save_installed_skills()

        logger.info(f"Uninstalled skill: {skill_name}")
        return True

    def update_skill(self, skill_name: str) -> bool:
        """
        更新技能

        Args:
            skill_name: 技能名称

        Returns:
            bool: 是否成功
        """
        if skill_name not in self.installed_skills:
            logger.error(f"Skill not installed: {skill_name}")
            return False

        if skill_name not in self.published_skills:
            logger.error(f"Skill not found in market: {skill_name}")
            return False

        installed_version = self.installed_skills[skill_name].get("version", "0.0.0")
        latest_version = self.published_skills[skill_name].get("version", "0.0.0")

        if installed_version == latest_version:
            logger.info(f"Skill {skill_name} is up to date")
            return True

        # 卸载旧版本
        self.uninstall_skill(skill_name)

        # 安装新版本
        return self.install_skill(skill_name, latest_version)

    def list_available_skills(self) -> List[Dict]:
        """列出可用技能"""
        return [
            {
                "name": skill["name"],
                "version": skill["version"],
                "description": skill["description"],
                "tags": skill["tags"],
                "author": skill["author"],
                "rating": skill["rating"],
                "downloads": skill["downloads"]
            }
            for skill in self.published_skills.values()
        ]

    def list_installed_skills(self) -> List[Dict]:
        """列出已安装技能"""
        return [
            {
                "name": skill["name"],
                "version": skill["version"],
                "installed_at": skill["installed_at"],
                "status": skill["status"]
            }
            for skill in self.installed_skills.values()
        ]

    def search_skills(self, query: str) -> List[Dict]:
        """搜索技能"""
        results = []
        query_lower = query.lower()

        for skill in self.published_skills.values():
            # 搜索名称、描述、标签
            if (query_lower in skill["name"].lower() or
                query_lower in skill["description"].lower() or
                any(query_lower in tag.lower() for tag in skill.get("tags", []))):
                results.append({
                    "name": skill["name"],
                    "version": skill["version"],
                    "description": skill["description"],
                    "tags": skill["tags"],
                    "rating": skill["rating"]
                })

        return results

    def add_review(self, skill_name: str, rating: float, comment: str) -> bool:
        """添加技能评论"""
        if skill_name not in self.published_skills:
            return False

        skill = self.published_skills[skill_name]
        if "reviews" not in skill:
            skill["reviews"] = []

        skill["reviews"].append({
            "rating": rating,
            "comment": comment,
            "created_at": datetime.now().isoformat()
        })

        # 更新平均评分
        ratings = [r["rating"] for r in skill["reviews"]]
        skill["rating"] = sum(ratings) / len(ratings)

        self._save_published_skills()
        return True

    def get_skill_info(self, skill_name: str) -> Optional[Dict]:
        """获取技能详情"""
        return self.published_skills.get(skill_name)

    def export_skills(self, output_path: str) -> bool:
        """导出技能包"""
        skills_to_export = self.list_available_skills()

        export_data = {
            "exported_at": datetime.now().isoformat(),
            "skills": skills_to_export,
            "packages": []
        }

        for skill in skills_to_export:
            skill_info = self.published_skills[skill["name"]]
            if skill_info.get("package_file"):
                export_data["packages"].append(skill_info["package_file"])

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        return True

    def import_skills(self, input_path: str) -> bool:
        """导入技能包"""
        with open(input_path, "r", encoding="utf-8") as f:
            import_data = json.load(f)

        for skill_data in import_data.get("skills", []):
            skill_name = skill_data["name"]
            if skill_name not in self.published_skills:
                self.published_skills[skill_name] = skill_data

        self._save_published_skills()
        return True

    def get_stats(self) -> Dict:
        """获取技能市场统计"""
        total_downloads = sum(s.get("downloads", 0) for s in self.published_skills.values())
        avg_rating = sum(s.get("rating", 0) for s in self.published_skills.values()) / len(self.published_skills) if self.published_skills else 0

        return {
            "total_published": len(self.published_skills),
            "total_installed": len(self.installed_skills),
            "total_downloads": total_downloads,
            "average_rating": round(avg_rating, 1),
            "builtin_skills": len(BUILTIN_SKILLS)
        }


# 全局实例
_markets: Dict[str, SkillMarket] = {}


def get_skill_market(bot_name: str = None) -> SkillMarket:
    """获取技能市场实例"""
    key = bot_name or "global"
    if key not in _markets:
        _markets[key] = SkillMarket(bot_name)
    return _markets[key]


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Skill Market - 技能市场系统")
        print("\nUsage:")
        print("  python3 skill_market.py list              # 列出可用技能")
        print("  python3 skill_market.py installed         # 列出已安装技能")
        print("  python3 skill_market.py search <query>    # 搜索技能")
        print("  python3 skill_market.py install <name>    # 安装技能")
        print("  python3 skill_market.py uninstall <name>  # 卸载技能")
        print("  python3 skill_market.py stats             # 显示统计")
        sys.exit(1)

    command = sys.argv[1]
    market = get_skill_market()

    if command == "list":
        skills = market.list_available_skills()
        print(f"\nAvailable Skills ({len(skills)} total)")
        print("=" * 70)
        for skill in skills:
            stars = "★" * int(skill["rating"]) + "☆" * (5 - int(skill["rating"]))
            print(f"📦 {skill['name']} v{skill['version']}")
            print(f"   {skill['description']}")
            print(f"   Tags: {', '.join(skill['tags'])} | {stars} ({skill['downloads']} downloads)")
        print("=" * 70)

    elif command == "installed":
        skills = market.list_installed_skills()
        print(f"\nInstalled Skills ({len(skills)} total)")
        print("=" * 70)
        for skill in skills:
            print(f"✅ {skill['name']} v{skill['version']}")
            print(f"   Installed: {skill['installed_at']}")
        print("=" * 70)

    elif command == "search":
        query = sys.argv[2] if len(sys.argv) > 2 else ""
        skills = market.search_skills(query)
        print(f"\nSearch Results for '{query}' ({len(skills)} found)")
        print("=" * 70)
        for skill in skills:
            print(f"📦 {skill['name']} - {skill['description']}")
        print("=" * 70)

    elif command == "install":
        if len(sys.argv) < 3:
            print("Usage: skill_market.py install <skill_name>")
            sys.exit(1)

        skill_name = sys.argv[2]
        success = market.install_skill(skill_name)
        if success:
            print(f"\n✅ Installed skill: {skill_name}")
        else:
            print(f"\n❌ Failed to install skill: {skill_name}")

    elif command == "uninstall":
        if len(sys.argv) < 3:
            print("Usage: skill_market.py uninstall <skill_name>")
            sys.exit(1)

        skill_name = sys.argv[2]
        success = market.uninstall_skill(skill_name)
        if success:
            print(f"\n✅ Uninstalled skill: {skill_name}")
        else:
            print(f"\n❌ Failed to uninstall skill: {skill_name}")

    elif command == "stats":
        stats = market.get_stats()
        print("\nSkill Market Stats")
        print("=" * 50)
        print(f"Total Published: {stats['total_published']}")
        print(f"Total Installed: {stats['total_installed']}")
        print(f"Total Downloads: {stats['total_downloads']}")
        print(f"Average Rating: {stats['average_rating']}/5.0")
        print(f"Builtin Skills: {stats['builtin_skills']}")
        print("=" * 50)

    else:
        print(f"Unknown command: {command}")

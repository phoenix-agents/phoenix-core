#!/usr/bin/env python3
"""
Auto Save Learning - 自动保存 Bot 学习总结并提炼精华知识

扫描 workspaces/{Bot}/日志/学习总结-*.md 文件，提取知识点保存到：
1. workspaces/{Bot}/memory/学习笔记/学习笔记.md
2. workspaces/{Bot}/memory/知识库/{分类}-精华.md (高价值内容)

用法：
    python auto_save_learning.py              # 处理所有 Bot
    python auto_save_learning.py 编导         # 只处理指定 Bot
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from memory_store import MemoryStore, get_bot_memory_dir, HIGH_VALUE_KEYWORDS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

WORKSPACES_DIR = Path(__file__).parent / "workspaces"
TIMESTAMP = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
TODAY = datetime.now().strftime('%Y-%m-%d')

# Bot 列表
BOTS = ['编导', '剪辑', '美工', '场控', '客服', '运营', '渠道']

# Bot 与知识库分类映射
BOT_CATEGORY_MAP = {
    '编导': '直播相关',
    '场控': '直播相关',
    '剪辑': '视频制作',
    '美工': '设计规范',
    '客服': '运营数据',
    '运营': '运营数据',
    '渠道': '运营数据'
}


def scan_learning_files(bot_name: str) -> list:
    """扫描指定 Bot 的学习总结文件"""
    bot_dir = WORKSPACES_DIR / bot_name
    if not bot_dir.exists():
        return []

    log_dir = bot_dir / 'memory' / '日志'
    if not log_dir.exists():
        return []

    learning_files = []
    for file in log_dir.glob('学习总结-*.md'):
        learning_files.append({
            'bot': bot_name,
            'file': file.name,
            'filepath': file,
            'mtime': file.stat().st_mtime
        })

    return sorted(learning_files, key=lambda x: x['mtime'], reverse=True)


def extract_knowledge(content: str, bot: str) -> list:
    """从学习总结中提取知识点"""
    knowledge_points = []
    lines = content.split('\n')

    current_section = ''

    # 提取包含关键词的段落
    knowledge_keywords = [
        '掌握', '学会', '技巧', '方法', '公式', '规则', '策略',
        '要点', '核心', '关键', '心得', '体会', '发现', '总结',
        '经验', '建议', '应该', '必须', '注意', '✅'
    ]

    for line in lines:
        # 检测章节标题
        if line.startswith('##') or line.startswith('###'):
            current_section = line.replace('#', '').strip()
            continue

        # 检测是否包含知识点关键词
        has_keyword = any(kw in line for kw in knowledge_keywords)
        has_content = len(line) > 10 and not line.startswith('- [ ]')

        if has_keyword and has_content:
            knowledge_points.append({
                'section': current_section or '通用',
                'content': line.strip(),
                'bot': bot
            })

    return knowledge_points


def is_high_value(content: str) -> bool:
    """判断是否为高价值知识点"""
    if len(content) < 20:
        return False
    score = sum(1 for kw in HIGH_VALUE_KEYWORDS if kw in content)
    return score >= 1


def save_to_bot_memory(bot: str, knowledge_points: list, source_file: str) -> str:
    """保存知识到 Bot 的记忆"""
    memory_dir = get_bot_memory_dir(bot)
    notes_file = memory_dir / '学习笔记' / '学习笔记.md'

    # 确保目录存在
    notes_file.parent.mkdir(parents=True, exist_ok=True)

    # 生成追加内容
    new_entry = f"\n\n---\n\n## {TIMESTAMP} - 学习总结提取\n\n"
    new_entry += f"**来源文件**: {source_file}\n\n"

    for point in knowledge_points:
        new_entry += f"### {point['section']}\n{point['content']}\n\n"

    with open(notes_file, 'a', encoding='utf-8') as f:
        f.write(new_entry)

    logger.info(f"✅ 追加到：{notes_file}")
    return str(notes_file)


def promote_to_knowledge(bot: str, knowledge_points: list) -> list:
    """提炼高价值知识到知识库"""
    memory_dir = get_bot_memory_dir(bot)
    category = BOT_CATEGORY_MAP.get(bot, '通用')
    knowledge_file = memory_dir / '知识库' / f'{category}-精华.md'

    # 确保目录存在
    knowledge_file.parent.mkdir(parents=True, exist_ok=True)

    # 筛选高价值知识点
    high_value_points = [p for p in knowledge_points if is_high_value(p['content'])]

    if not high_value_points:
        return []

    # 追加到知识库文件
    new_entry = f"\n\n---\n\n## {TIMESTAMP} - {bot} Bot 分享\n\n"

    for point in high_value_points:
        new_entry += f"### {point['section']}\n\n{point['content']}\n\n"

    with open(knowledge_file, 'a', encoding='utf-8') as f:
        f.write(new_entry)

    logger.info(f"💎 提炼到：{knowledge_file}")
    return [str(knowledge_file)]


def log_execution(bot: str, count: int, filepath: str, promoted_count: int = 0):
    """记录执行日志"""
    memory_dir = get_bot_memory_dir(bot)
    log_file = memory_dir / '日志' / f'{TODAY}.md'

    log_file.parent.mkdir(parents=True, exist_ok=True)

    new_entry = f"\n\n## [AUTO] {bot} Bot 知识保存 ({TIMESTAMP})\n"
    new_entry += f"- **知识点数量**: {count}\n"
    new_entry += f"- **高价值提炼**: {promoted_count} 条\n"
    new_entry += f"- **保存位置**: {filepath}\n"
    new_entry += f"- **状态**: ✅ 完成\n"

    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(new_entry)

    logger.info(f"📝 日志已记录到：{log_file}")


def process_bot(bot_name: str) -> tuple:
    """处理单个 Bot 的学习总结"""
    learning_files = scan_learning_files(bot_name)

    if not learning_files:
        logger.info(f"⚠️  {bot_name}: 没有找到学习总结文件")
        return 0, 0

    logger.info(f"📚 {bot_name}: 找到 {len(learning_files)} 个学习总结文件")

    total_points = 0
    total_promoted = 0
    last_saved_file = None

    for file_info in learning_files:
        try:
            with open(file_info['filepath'], 'r', encoding='utf-8') as f:
                content = f.read()

            knowledge_points = extract_knowledge(content, bot_name)

            if not knowledge_points:
                continue

            logger.info(f"  📌 {file_info['file']}: 提取到 {len(knowledge_points)} 个知识点")

            # 保存到 Bot 记忆
            saved_file = save_to_bot_memory(bot_name, knowledge_points, file_info['file'])
            last_saved_file = saved_file
            total_points += len(knowledge_points)

            # 提炼高价值知识
            promoted_files = promote_to_knowledge(bot_name, knowledge_points)
            total_promoted += len([p for p in knowledge_points if is_high_value(p['content'])])

        except Exception as e:
            logger.error(f"处理 {file_info['file']} 失败：{e}")

    if last_saved_file:
        log_execution(bot_name, total_points, last_saved_file, total_promoted)

    return total_points, total_promoted


def main():
    """主函数"""
    bot_name = sys.argv[1] if len(sys.argv) > 1 else None
    bots_to_process = [bot_name] if bot_name else BOTS

    logger.info("🔍 开始扫描 Bot 学习总结...\n")

    total_saved = 0
    total_promoted = 0

    for bot in bots_to_process:
        if bot not in BOTS:
            logger.warning(f"⚠️  跳过未知 Bot: {bot}")
            continue

        saved, promoted = process_bot(bot)
        total_saved += saved
        total_promoted += promoted
        logger.info("")

    logger.info(f"\n✅ 完成！共提取 {total_saved} 个知识点，提炼 {total_promoted} 个高价值知识")
    logger.info(f"📂 工作区：{WORKSPACES_DIR}")


if __name__ == '__main__':
    main()

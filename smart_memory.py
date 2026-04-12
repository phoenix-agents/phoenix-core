#!/usr/bin/env python3
"""
Phoenix Core 智能记忆管理器
- 自动检测长文档
- 生成摘要注入上下文
- 完整内容保存到文件
"""

import os
from pathlib import Path
from datetime import datetime

SHARED_MEMORY_DIR = Path(__file__).parent / "shared_memory"
PROJECTS_DIR = SHARED_MEMORY_DIR / "projects"
MEMORY_FILE = SHARED_MEMORY_DIR / "MEMORY.md"
MAX_MEMORY_CHARS = 2200


def smart_save_memory(content, title=None):
    """
    智能保存记忆：
    - 短内容：直接保存
    - 长内容：保存为项目文件 + 生成摘要
    """
    content = content.strip()

    if len(content) <= MAX_MEMORY_CHARS:
        # 短内容：直接追加到 MEMORY.md
        append_to_memory(content)
        return f"✅ 已保存到 MEMORY.md ({len(content)} 字符)"

    else:
        # 长内容：保存为项目文件
        if not title:
            title = f"长文档_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 清理标题（移除特殊字符）
        safe_title = "".join(c for c in title if c.isalnum() or c in ' -_.')
        filename = f"{safe_title}.md"
        filepath = PROJECTS_DIR / filename

        # 确保目录存在
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

        # 保存完整内容
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# {title}\n\n")
            f.write(f"**创建时间**: {datetime.now().isoformat()}\n\n")
            f.write(f"**字符数**: {len(content)}\n\n")
            f.write("---\n\n")
            f.write(content)

        # 生成摘要注入 MEMORY.md
        summary = generate_summary(content, title, filepath)
        append_to_memory(summary)

        return f"✅ 长文档已保存：{filepath} ({len(content)} 字符)\n   摘要已注入 MEMORY.md"


def generate_summary(content, title, filepath):
    """生成文档摘要（500 字符内）"""
    # 提取前 500 字符作为摘要
    preview = content[:500].strip()

    # 计算总长度
    total_chars = len(content)

    # 生成摘要
    summary = f"""## {title}
- **时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
- **长度**: {total_chars} 字符
- **位置**: `{filepath.relative_to(Path.home())}`
- **摘要**: {preview}...
"""
    return summary


def append_to_memory(content):
    """追加内容到 MEMORY.md"""
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    # 读取现有内容
    if MEMORY_FILE.exists():
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            existing = f.read()
    else:
        existing = ""

    # 追加新内容
    new_content = f"{existing}\n\n---\n\n{content}"

    # 如果超出限制，保留最新部分
    if len(new_content) > MAX_MEMORY_CHARS:
        new_content = new_content[-MAX_MEMORY_CHARS:]

    # 写入文件
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        f.write(new_content)


def load_context(bot_name=None):
    """
    加载上下文（带智能引用）
    - 返回 MEMORY.md 内容（2200 字符内）
    - 附加项目文件索引
    """
    context_parts = []

    # 1. 加载 MEMORY.md
    if MEMORY_FILE.exists():
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            memory = f.read()
        context_parts.append(memory)

    # 2. 添加项目文件索引
    if PROJECTS_DIR.exists():
        project_files = list(PROJECTS_DIR.glob("*.md"))
        if project_files:
            index = "\n\n## 📁 项目文件索引\n"
            for pf in project_files[-10:]:  # 只显示最近 10 个
                stat = pf.stat()
                size = stat.st_size
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%m-%d')
                index += f"- [{pf.stem}]({pf}) - {mtime} ({size:,} 字符)\n"
            context_parts.append(index)

    return "\n".join(context_parts)


# CLI 接口
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法：python3 smart_memory.py <命令> [参数]")
        print("\n命令:")
        print("  save <文件> [标题]  - 保存长文档")
        print("  status              - 查看记忆状态")
        print("  context             - 加载上下文")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "save":
        if len(sys.argv) < 3:
            print("❌ 需要提供文件路径")
            sys.exit(1)

        filepath = Path(sys.argv[2])
        title = sys.argv[3] if len(sys.argv) > 3 else filepath.stem

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        result = smart_save_memory(content, title)
        print(result)

    elif cmd == "status":
        print("=== Phoenix Core 记忆状态 ===\n")

        if MEMORY_FILE.exists():
            size = MEMORY_FILE.stat().st_size
            print(f"MEMORY.md: {size:,} 字符 (限制：{MAX_MEMORY_CHARS:,})")
        else:
            print("MEMORY.md: 不存在")

        if PROJECTS_DIR.exists():
            projects = list(PROJECTS_DIR.glob("*.md"))
            print(f"项目文件：{len(projects)} 个")
            for p in projects[-5:]:
                print(f"  - {p.name} ({p.stat().st_size:,} 字符)")
        else:
            print("项目目录：不存在")

    elif cmd == "context":
        context = load_context()
        print(context)

    else:
        print(f"❌ 未知命令：{cmd}")

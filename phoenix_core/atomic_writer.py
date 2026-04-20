#!/usr/bin/env python3
"""
Phoenix Core Atomic Writer - 原子写入工具

确保配置文件写入的原子性，避免写入一半被读取导致的数据不一致

Usage:
    from phoenix_core.atomic_writer import atomic_write

    # 方式 1: 使用上下文管理器
    with atomic_write("config.json") as f:
        json.dump(config, f)

    # 方式 2: 直接写入
    atomic_write_file("bot.env", content, mode="text")
"""

import os
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Union


def atomic_write_file(
    path: Union[str, Path],
    content: str,
    mode: str = "text",
    encoding: str = "utf-8",
    backup: bool = True,
) -> bool:
    """
    原子性地写入文件

    原理:
    1. 先写入临时文件 (.tmp)
    2. fsync 确保数据落盘
    3. os.replace 原子替换原文件

    Args:
        path: 目标文件路径
        content: 文件内容
        mode: "text" 或 "binary"
        encoding: 文本编码 (仅 text 模式)
        backup: 是否备份原文件 (.bak)

    Returns:
        是否成功
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # 备份现有文件
    if backup and path.exists():
        backup_path = path.with_suffix(path.suffix + ".bak")
        try:
            shutil.copy2(path, backup_path)
        except Exception as e:
            print(f"警告：备份失败 {e}")

    # 创建临时文件 (同目录，避免跨文件系统移动)
    tmp_path = path.with_suffix(path.suffix + ".tmp")

    try:
        # 写入临时文件
        if mode == "binary":
            with open(tmp_path, "wb") as f:
                f.write(content.encode() if isinstance(content, str) else content)
                f.flush()
                os.fsync(f.fileno())
        else:
            with open(tmp_path, "w", encoding=encoding) as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())

        # 原子替换
        os.replace(tmp_path, path)
        return True

    except Exception as e:
        # 清理临时文件
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except:
                pass
        print(f"错误：原子写入失败 {e}")
        return False


class AtomicWriter:
    """上下文管理器方式的原子写入"""

    def __init__(
        self,
        path: Union[str, Path],
        mode: str = "w",
        encoding: str = "utf-8",
        backup: bool = True,
    ):
        self.path = Path(path)
        self.mode = mode
        self.encoding = encoding
        self.backup = backup
        self.tmp_path: Optional[Path] = None
        self.file = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # 备份现有文件
        if self.backup and self.path.exists():
            backup_path = self.path.with_suffix(self.path.suffix + ".bak")
            try:
                shutil.copy2(self.path, backup_path)
            except Exception as e:
                print(f"警告：备份失败 {e}")

        # 创建临时文件
        self.tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        self.file = open(self.tmp_path, self.mode, encoding=self.encoding)
        return self.file

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.file:
            self.file.close()

        if exc_type is not None:
            # 发生异常，清理临时文件
            if self.tmp_path and self.tmp_path.exists():
                try:
                    self.tmp_path.unlink()
                except:
                    pass
            return False

        # 成功写入，原子替换
        try:
            os.replace(self.tmp_path, self.path)
            return True
        except Exception as e:
            print(f"错误：原子替换失败 {e}")
            return False


# 便捷函数
def atomic_json_dump(path: Union[str, Path], data: dict, **kwargs) -> bool:
    """原子性写入 JSON 文件"""
    import json
    content = json.dumps(data, indent=2, ensure_ascii=False, **kwargs)
    return atomic_write_file(path, content, mode="text")


def atomic_env_write(path: Union[str, Path], env_dict: dict, comment: str = "") -> bool:
    """原子性写入 .env 文件"""
    lines = [comment] if comment else []
    for key, value in env_dict.items():
        lines.append(f"{key}={value}")
    content = "\n".join(lines) + "\n"
    return atomic_write_file(path, content, mode="text")

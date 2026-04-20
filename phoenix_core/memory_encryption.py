#!/usr/bin/env python3
"""
Phoenix Core Memory Encryption - 记忆备份加密

适用场景：对话记忆涉及敏感信息 (API 密钥、用户隐私)
- GPG 对称加密
- sqlite3 SEE 加密扩展 (可选)
- 加密备份，明文恢复

Usage:
    from phoenix_core.memory_encryption import encrypt_backup, decrypt_backup

    # 加密备份
    encrypt_backup("data/memory.db", "data/backups/memory_encrypted.db.gpg")

    # 解密恢复
    decrypt_backup("data/backups/memory_encrypted.db.gpg", "data/memory.db")
"""

import subprocess
import os
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# 默认加密密码 (从环境变量读取)
ENCRYPTION_PASSWORD = os.environ.get("PHOENIX_BACKUP_PASSWORD", "default_phoenix_backup_key_2026")

# 备份目录
BACKUP_DIR = Path(__file__).parent.parent.parent / "data" / "backups" / "memory"


def check_gpg_available() -> bool:
    """检查 GPG 是否可用"""
    try:
        result = subprocess.run(["gpg", "--version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def encrypt_backup(
    src_path: str,
    dst_path: Optional[str] = None,
    password: Optional[str] = None,
) -> str:
    """
    使用 GPG 对称加密备份文件

    Args:
        src_path: 源文件路径
        dst_path: 目标路径 (默认为 src_path.gpg)
        password: 加密密码 (默认为环境变量或默认值)

    Returns:
        加密文件路径

    Usage:
        encrypt_backup("data/memory.db")
        # 输出：data/memory.db.gpg
    """
    if not check_gpg_available():
        logger.warning("[MemoryEncryption] GPG 不可用，使用明文备份")
        return src_path

    src = Path(src_path)
    if not src.exists():
        logger.error(f"[MemoryEncryption] 源文件不存在：{src_path}")
        return ""

    if dst_path is None:
        dst = src.with_suffix(src.suffix + ".gpg")
    else:
        dst = Path(dst_path)

    # 确保目标目录存在
    dst.parent.mkdir(parents=True, exist_ok=True)

    password = password or ENCRYPTION_PASSWORD

    try:
        # GPG 对称加密
        result = subprocess.run(
            [
                "gpg",
                "--batch",
                "--yes",
                "--passphrase", password,
                "--cipher-algo", "AES256",
                "--symmetric",
                "--output", str(dst),
                str(src),
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            logger.info(f"[MemoryEncryption] 加密完成：{dst}")
            return str(dst)
        else:
            logger.error(f"[MemoryEncryption] 加密失败：{result.stderr}")
            return ""

    except Exception as e:
        logger.error(f"[MemoryEncryption] 加密异常：{e}")
        return ""


def decrypt_backup(
    src_path: str,
    dst_path: Optional[str] = None,
    password: Optional[str] = None,
) -> str:
    """
    解密 GPG 加密的备份文件

    Args:
        src_path: 加密文件路径
        dst_path: 目标路径 (默认为去掉.gpg 后缀)
        password: 解密密码

    Returns:
        解密文件路径

    Usage:
        decrypt_backup("data/backups/memory_encrypted.db.gpg")
        # 输出：data/backups/memory_encrypted.db
    """
    if not check_gpg_available():
        logger.error("[MemoryEncryption] GPG 不可用，无法解密")
        return ""

    src = Path(src_path)
    if not src.exists():
        logger.error(f"[MemoryEncryption] 加密文件不存在：{src_path}")
        return ""

    if dst_path is None:
        # 默认去掉.gpg 后缀
        if src.suffix == ".gpg":
            dst = src.with_suffix("")
        else:
            dst = src.parent / (src.name + ".decrypted")
    else:
        dst = Path(dst_path)

    # 确保目标目录存在
    dst.parent.mkdir(parents=True, exist_ok=True)

    password = password or ENCRYPTION_PASSWORD

    try:
        result = subprocess.run(
            [
                "gpg",
                "--batch",
                "--yes",
                "--passphrase", password,
                "--decrypt",
                "--output", str(dst),
                str(src),
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            logger.info(f"[MemoryEncryption] 解密完成：{dst}")
            return str(dst)
        else:
            logger.error(f"[MemoryEncryption] 解密失败：{result.stderr}")
            return ""

    except Exception as e:
        logger.error(f"[MemoryEncryption] 解密异常：{e}")
        return ""


def encrypt_with_sqlite_see(src_path: str, dst_path: Optional[str] = None, key: Optional[str] = None) -> str:
    """
    使用 SQLite SEE 加密扩展 (需要编译时支持)

    注意：SQLite SEE 是付费扩展，开源项目可使用 SQLCipher 替代

    Args:
        src_path: 源数据库路径
        dst_path: 目标加密数据库路径
        key: 加密密钥

    Returns:
        加密文件路径
    """
    # 此功能需要 SQLite 编译时启用 SEE
    # 或使用 SQLCipher: https://www.zetetic.net/sqlcipher/
    logger.warning("[MemoryEncryption] SQLite SEE 加密需要特殊编译，建议使用 GPG 加密")
    return ""


def backup_and_encrypt(
    src_path: str,
    backup_dir: Optional[Path] = None,
    keep_encrypted: bool = True,
    password: Optional[str] = None,
) -> str:
    """
    备份并加密 (一键操作)

    Args:
        src_path: 源数据库路径
        backup_dir: 备份目录
        keep_encrypted: 是否保留加密文件 (删除明文)
        password: 加密密码

    Returns:
        备份文件路径

    Usage:
        backup_and_encrypt("data/memory.db")
        # 输出加密备份：data/backups/memory_20260416.db.gpg
    """
    import sqlite3
    from datetime import datetime

    src = Path(src_path)
    if not src.exists():
        logger.error(f"[MemoryEncryption] 源文件不存在：{src_path}")
        return ""

    if backup_dir is None:
        backup_dir = BACKUP_DIR

    backup_dir.mkdir(parents=True, exist_ok=True)

    # 备份文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    plain_backup = backup_dir / f"memory_{timestamp}.db"
    encrypted_backup = backup_dir / f"memory_{timestamp}.db.gpg"

    # 1. 使用 SQLite 在线备份 (不锁库)
    try:
        src_conn = sqlite3.connect(str(src))
        dst_conn = sqlite3.connect(str(plain_backup))
        src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()
        logger.info(f"[MemoryEncryption] 备份完成：{plain_backup}")
    except Exception as e:
        logger.error(f"[MemoryEncryption] 备份失败：{e}")
        return ""

    # 2. 加密备份
    if not check_gpg_available():
        logger.warning("[MemoryEncryption] GPG 不可用，保留明文备份")
        return str(plain_backup)

    password = password or ENCRYPTION_PASSWORD

    try:
        result = subprocess.run(
            [
                "gpg",
                "--batch",
                "--yes",
                "--passphrase", password,
                "--cipher-algo", "AES256",
                "--symmetric",
                "--output", str(encrypted_backup),
                str(plain_backup),
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            logger.info(f"[MemoryEncryption] 加密备份完成：{encrypted_backup}")

            # 删除明文备份
            if keep_encrypted:
                plain_backup.unlink()
                logger.info(f"[MemoryEncryption] 已删除明文备份：{plain_backup}")

            return str(encrypted_backup)
        else:
            logger.error(f"[MemoryEncryption] 加密失败：{result.stderr}")
            return str(plain_backup)  # 返回明文备份

    except Exception as e:
        logger.error(f"[MemoryEncryption] 加密异常：{e}")
        return str(plain_backup)


def decrypt_and_restore(
    encrypted_path: str,
    dst_path: str,
    password: Optional[str] = None,
) -> bool:
    """
    解密并恢复数据库

    Args:
        encrypted_path: 加密备份文件路径
        dst_path: 恢复目标路径
        password: 解密密码

    Returns:
        是否成功
    """
    decrypted = decrypt_backup(encrypted_path, password=password)
    if not decrypted:
        return False

    # 恢复数据库
    try:
        import shutil
        dst = Path(dst_path)
        dst.parent.mkdir(parents=True, exist_ok=True)

        # 备份当前文件 (如果存在)
        if dst.exists():
            emergency_backup = dst.with_suffix(".db.emergency")
            shutil.copy2(dst, emergency_backup)

        # 恢复
        shutil.copy2(decrypted, dst)

        # 清理临时文件
        Path(decrypted).unlink()

        logger.info(f"[MemoryEncryption] 恢复完成：{dst}")
        return True

    except Exception as e:
        logger.error(f"[MemoryEncryption] 恢复失败：{e}")
        return False

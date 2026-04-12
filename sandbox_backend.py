#!/usr/bin/env python3
"""
Sandbox Backend - 沙盒隔离后端

Phoenix Core Phoenix v2.0 扩展模块

支持:
1. Docker 容器隔离
2. SSH 远程执行
3. 本地沙盒目录
4. 资源限制 (CPU/内存/时间)
5. 执行日志记录

Usage:
    from sandbox_backend import SandboxBackend

    # Docker 模式
    backend = SandboxBackend(mode="docker")
    result = backend.execute("python3 script.py", timeout=60)

    # SSH 模式
    backend = SandboxBackend(mode="ssh", host="remote.host.com")
    result = backend.execute("ls -la")

    # 本地沙盒模式
    backend = SandboxBackend(mode="local")
    result = backend.execute("./safe_script.sh")
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import threading
import signal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
SANDBOX_DIR = Path(__file__).parent / "sandbox")
SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
EXECUTION_LOG = SANDBOX_DIR / "execution_log.jsonl"


class SandboxMode(Enum):
    """沙盒模式"""
    LOCAL = "local"       # 本地沙盒目录
    DOCKER = "docker"     # Docker 容器
    SSH = "ssh"           # SSH 远程执行


class ExecutionResult:
    """执行结果"""

    def __init__(self, command: str, success: bool, output: str = "",
                 error: str = "", exit_code: int = 0,
                 execution_time_ms: int = 0, timeout: bool = False):
        self.command = command
        self.success = success
        self.output = output
        self.error = error
        self.exit_code = exit_code
        self.execution_time_ms = execution_time_ms
        self.timeout = timeout
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        return {
            "command": self.command,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "exit_code": self.exit_code,
            "execution_time_ms": self.execution_time_ms,
            "timeout": self.timeout,
            "timestamp": self.timestamp
        }


class SandboxBackend:
    """
    沙盒后端管理器

    提供安全的代码执行环境
    """

    def __init__(self, mode: str = "local", **kwargs):
        self.mode = SandboxMode(mode.lower())
        self.kwargs = kwargs
        self.sandbox_id = str(uuid.uuid4())[:8]

        # 模式特定配置
        if self.mode == SandboxMode.DOCKER:
            self.image = kwargs.get("image", "python:3.11-slim")
            self.container_name = f"phoenix_sandbox_{self.sandbox_id}"
            self._init_docker()

        elif self.mode == SandboxMode.SSH:
            self.host = kwargs.get("host", "localhost")
            self.port = kwargs.get("port", 22)
            self.username = kwargs.get("username", "phoenix")
            self.password = kwargs.get("password")
            self.key_file = kwargs.get("key_file")
            self._init_ssh()

        elif self.mode == SandboxMode.LOCAL:
            self.work_dir = SANDBOX_DIR / f"sandbox_{self.sandbox_id}"
            self.work_dir.mkdir(parents=True, exist_ok=True)
            self._init_local()

        logger.info(f"SandboxBackend initialized: mode={self.mode.value}")

    def _init_docker(self):
        """初始化 Docker 环境"""
        # 检查 Docker 是否可用
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.info(f"Docker available: {result.stdout.strip()}")
            else:
                logger.warning("Docker command failed, falling back to local mode")
                self.mode = SandboxMode.LOCAL
        except FileNotFoundError:
            logger.warning("Docker not found, falling back to local mode")
            self.mode = SandboxMode.LOCAL
        except subprocess.TimeoutExpired:
            logger.warning("Docker check timed out, falling back to local mode")
            self.mode = SandboxMode.LOCAL

    def _init_ssh(self):
        """初始化 SSH 环境"""
        # 检查 SSH 配置
        if not self.host:
            logger.warning("SSH host not specified, falling back to local mode")
            self.mode = SandboxMode.LOCAL

        if not self.password and not self.key_file:
            logger.warning("No SSH password or key file, falling back to local mode")
            self.mode = SandboxMode.LOCAL

    def _init_local(self):
        """初始化本地沙盒"""
        logger.info(f"Local sandbox directory: {self.work_dir}")

    def execute(self, command: str, timeout: int = 60,
                work_dir: Path = None, env: Dict = None) -> ExecutionResult:
        """
        执行命令

        Args:
            command: 要执行的命令
            timeout: 超时时间 (秒)
            work_dir: 工作目录
            env: 环境变量

        Returns:
            ExecutionResult: 执行结果
        """
        start_time = datetime.now()

        try:
            if self.mode == SandboxMode.DOCKER:
                result = self._execute_docker(command, timeout)
            elif self.mode == SandboxMode.SSH:
                result = self._execute_ssh(command, timeout)
            else:
                result = self._execute_local(command, timeout, work_dir, env)

            end_time = datetime.now()
            execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

            exec_result = ExecutionResult(
                command=command,
                success=result.get("success", False),
                output=result.get("output", ""),
                error=result.get("error", ""),
                exit_code=result.get("exit_code", -1),
                execution_time_ms=execution_time_ms,
                timeout=result.get("timeout", False)
            )

            # 记录执行日志
            self._log_execution(exec_result)

            return exec_result

        except Exception as e:
            logger.error(f"Execution failed: {e}")
            end_time = datetime.now()
            execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

            return ExecutionResult(
                command=command,
                success=False,
                error=str(e),
                execution_time_ms=execution_time_ms
            )

    def _execute_local(self, command: str, timeout: int = 60,
                       work_dir: Path = None, env: Dict = None) -> Dict:
        """本地执行"""
        import subprocess

        cwd = work_dir or self.work_dir
        environment = os.environ.copy()
        if env:
            environment.update(env)

        try:
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=cwd,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid  # 创建新进程组
            )

            try:
                stdout, stderr = process.communicate(timeout=timeout)

                return {
                    "success": process.returncode == 0,
                    "output": stdout.decode("utf-8", errors="ignore"),
                    "error": stderr.decode("utf-8", errors="ignore"),
                    "exit_code": process.returncode
                }

            except subprocess.TimeoutExpired:
                # 超时：杀死整个进程组
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                process.wait()

                return {
                    "success": False,
                    "output": "",
                    "error": f"Command timed out after {timeout}s",
                    "exit_code": -1,
                    "timeout": True
                }

        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "exit_code": -1
            }

    def _execute_docker(self, command: str, timeout: int = 60) -> Dict:
        """Docker 容器执行"""
        # 创建临时容器执行命令
        docker_command = [
            "docker", "run", "--rm",
            "--name", self.container_name,
            "-w", "/workspace",
            "-v", f"{self.work_dir}:/workspace",
            "--memory", "512m",  # 限制内存
            "--cpus", "1.0",    # 限制 CPU
            self.image,
            "timeout", str(timeout), "bash", "-c", command
        ]

        try:
            result = subprocess.run(
                docker_command,
                capture_output=True,
                text=True,
                timeout=timeout + 10  # 额外给 10 秒 docker 开销
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr,
                "exit_code": result.returncode,
                "timeout": result.returncode == 124  # timeout 命令返回 124
            }

        except subprocess.TimeoutExpired:
            # 强制停止容器
            subprocess.run(["docker", "kill", self.container_name], capture_output=True)

            return {
                "success": False,
                "output": "",
                "error": f"Command timed out after {timeout}s",
                "exit_code": -1,
                "timeout": True
            }

    def _execute_ssh(self, command: str, timeout: int = 60) -> Dict:
        """SSH 远程执行"""
        # 使用 sshpass 或 SSH key
        ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no"]

        if self.key_file:
            ssh_cmd.extend(["-i", str(self.key_file)])
        elif self.password:
            ssh_cmd = ["sshpass", "-p", self.password] + ssh_cmd

        ssh_cmd.extend([
            f"{self.username}@{self.host}",
            "-p", str(self.port),
            command
        ])

        try:
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr,
                "exit_code": result.returncode
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": f"SSH command timed out after {timeout}s",
                "exit_code": -1,
                "timeout": True
            }

    def _log_execution(self, result: ExecutionResult):
        """记录执行日志"""
        with open(EXECUTION_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(result.to_dict(), ensure_ascii=False) + "\n")

    def upload_file(self, source: Path, destination: str = None) -> bool:
        """上传文件到沙盒"""
        if not source.exists():
            logger.error(f"Source file not found: {source}")
            return False

        dest = self.work_dir / (destination or source.name) if self.mode == SandboxMode.LOCAL else Path(destination or source.name)

        if self.mode == SandboxMode.LOCAL:
            shutil.copy2(source, dest)
            logger.info(f"Uploaded {source} to {dest}")
            return True

        elif self.mode == SandboxMode.DOCKER:
            # Docker 卷已经映射，直接复制到工作目录
            docker_dest = self.work_dir / (destination or source.name)
            shutil.copy2(source, docker_dest)
            return True

        elif self.mode == SandboxMode.SSH:
            # 使用 scp 上传
            scp_cmd = ["scp", "-o", "StrictHostKeyChecking=no"]

            if self.key_file:
                scp_cmd.extend(["-i", str(self.key_file)])
            elif self.password:
                scp_cmd = ["sshpass", "-p", self.password] + scp_cmd

            scp_cmd.extend([
                str(source),
                f"{self.username}@{self.host}:{destination or source.name}"
            ])

            result = subprocess.run(scp_cmd, capture_output=True, text=True)
            return result.returncode == 0

        return False

    def download_file(self, source: str, destination: Path = None) -> bool:
        """从沙盒下载文件"""
        if self.mode == SandboxMode.LOCAL:
            source_path = self.work_dir / source
            if not source_path.exists():
                logger.error(f"Source file not found: {source_path}")
                return False

            dest = destination or (SANDBOX_DIR / f"downloaded_{source}")
            shutil.copy2(source_path, dest)
            return True

        elif self.mode == SandboxMode.DOCKER:
            # 从容器复制文件
            source_path = self.work_dir / source
            if source_path.exists():
                dest = destination or (SANDBOX_DIR / f"downloaded_{source}")
                shutil.copy2(source_path, dest)
                return True

        elif self.mode == SandboxMode.SSH:
            # 使用 scp 下载
            scp_cmd = ["scp", "-o", "StrictHostKeyChecking=no"]

            if self.key_file:
                scp_cmd.extend(["-i", str(self.key_file)])
            elif self.password:
                scp_cmd = ["sshpass", "-p", self.password] + scp_cmd

            dest = destination or (SANDBOX_DIR / f"downloaded_{Path(source).name}")
            scp_cmd.extend([
                f"{self.username}@{self.host}:{source}",
                str(dest)
            ])

            result = subprocess.run(scp_cmd, capture_output=True, text=True)
            return result.returncode == 0

        return False

    def cleanup(self):
        """清理沙盒"""
        if self.mode == SandboxMode.LOCAL:
            if self.work_dir.exists():
                shutil.rmtree(self.work_dir)
                logger.info(f"Cleaned up local sandbox: {self.work_dir}")

        elif self.mode == SandboxMode.DOCKER:
            subprocess.run(["docker", "kill", self.container_name], capture_output=True)
            subprocess.run(["docker", "rm", self.container_name], capture_output=True)

        logger.info(f"Sandbox {self.sandbox_id} cleanup complete")

    def get_stats(self) -> Dict:
        """获取沙盒统计"""
        execution_count = 0
        if EXECUTION_LOG.exists():
            with open(EXECUTION_LOG, "r", encoding="utf-8") as f:
                execution_count = sum(1 for _ in f)

        return {
            "mode": self.mode.value,
            "sandbox_id": self.sandbox_id,
            "work_dir": str(self.work_dir) if self.mode == SandboxMode.LOCAL else None,
            "execution_count": execution_count
        }


# 工厂函数
def create_sandbox(mode: str = "local", **kwargs) -> SandboxBackend:
    """创建沙盒实例"""
    return SandboxBackend(mode=mode, **kwargs)


# 便捷函数
def execute_in_sandbox(command: str, mode: str = "local",
                       timeout: int = 60, **kwargs) -> ExecutionResult:
    """在沙盒中执行命令"""
    backend = create_sandbox(mode, **kwargs)
    try:
        return backend.execute(command, timeout)
    finally:
        backend.cleanup()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Sandbox Backend - 沙盒隔离后端")
        print("\nUsage:")
        print("  python3 sandbox_backend.py local <command>    # 本地沙盒执行")
        print("  python3 sandbox_backend.py docker <command>   # Docker 容器执行")
        print("  python3 sandbox_backend.py stats              # 显示统计")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "stats":
        backend = create_sandbox("local")
        stats = backend.get_stats()
        print("\nSandbox Stats")
        print("=" * 50)
        print(f"Mode: {stats['mode']}")
        print(f"Sandbox ID: {stats['sandbox_id']}")
        print(f"Work Dir: {stats['work_dir']}")
        print(f"Execution Count: {stats['execution_count']}")
        print("=" * 50)

    elif mode in ["local", "docker"]:
        command = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        if not command:
            print(f"Usage: sandbox_backend.py {mode} <command>")
            sys.exit(1)

        print(f"\nExecuting in {mode} mode: {command}\n")

        backend = create_sandbox(mode)
        try:
            result = backend.execute(command, timeout=30)
            print(f"Exit Code: {result.exit_code}")
            print(f"Execution Time: {result.execution_time_ms}ms")
            print(f"Success: {result.success}")

            if result.output:
                print("\nOutput:")
                print(result.output)

            if result.error:
                print("\nError:")
                print(result.error)

        finally:
            backend.cleanup()

    elif mode == "test":
        # 运行测试
        print("\nRunning Sandbox Tests...\n")

        # 测试本地模式
        backend = create_sandbox("local")
        result = backend.execute("echo 'Hello from sandbox'")
        print(f"Local test: {'✓' if result.success else '✗'}")
        print(f"  Output: {result.output.strip()}")

        # 测试超时
        result = backend.execute("sleep 2", timeout=1)
        print(f"Timeout test: {'✓' if result.timeout else '✗'}")

        # 测试错误命令
        result = backend.execute("exit 1")
        print(f"Error test: {'✓' if not result.success else '✗'}")

        backend.cleanup()
        print("\nTests completed.")

    else:
        print(f"Unknown mode: {mode}")

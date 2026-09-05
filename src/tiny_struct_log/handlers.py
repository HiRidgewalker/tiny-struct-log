"""集中构造终端和轮转文件这两种既有输出目标。"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .formatters import _ColoredConsoleFormatter, _JSONLineFormatter


class _LogOutputs:
    """聚合没有共享状态的 logging 输出构造操作。"""

    @staticmethod
    def create_console(formatter: _JSONLineFormatter) -> logging.Handler:
        """创建向标准输出写日志的终端 Handler。"""

        # 提前读取终端能力并构造 Formatter，避免检查失败时遗留已创建的 Handler。
        # 管道和重定向不是交互终端，必须关闭 ANSI 颜色以供采集程序解析 JSON。
        console_formatter = _ColoredConsoleFormatter(
            formatter, colors=sys.stdout.isatty()
        )
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        handler.setFormatter(console_formatter)
        return handler

    @staticmethod
    def create_file(
        path: Path,
        max_bytes: int,
        backup_count: int,
        formatter: _JSONLineFormatter,
    ) -> RotatingFileHandler:
        """创建延迟打开、按大小轮转的 UTF-8 JSONL 文件 Handler。"""

        path.parent.mkdir(parents=True, exist_ok=True)
        # 目录在创建 Logger 时建立，delay=True 让文件等到首条日志时才打开。
        # 标准库负责将旧文件依次改名为 .1、.2，最多保留 backup_count 份备份；
        # 此轮转方式适合单进程，多进程应分别写入不同目录或文件。
        handler = RotatingFileHandler(
            path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
            delay=True,
        )
        handler.setLevel(logging.INFO)
        handler.setFormatter(formatter)
        return handler

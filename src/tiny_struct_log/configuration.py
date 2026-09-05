"""在公开创建边界校验 Logger 参数，并保存不可变的规范化配置。"""

import logging
import re
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Literal

_LOGGER_NAME_PATTERN = r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z"
_LogLevelName = Literal["debug", "info", "warning", "error", "critical"]


class _LogLevel(IntEnum):
    """保存公共等级名称对应的标准库 logging 数值。"""

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL

    @classmethod
    def from_name(cls, level_name: _LogLevelName, field_name: str) -> "_LogLevel":
        """把严格的小写等级名称转换为 logging 使用的数值等级。"""

        if not isinstance(level_name, str):
            raise TypeError(f"{field_name} 必须是字符串")
        match level_name:
            case "debug":
                return cls.DEBUG
            case "info":
                return cls.INFO
            case "warning":
                return cls.WARNING
            case "error":
                return cls.ERROR
            case "critical":
                return cls.CRITICAL
            case _:
                raise ValueError(
                    f"{field_name} 必须是 debug、info、warning、error 或 critical"
                )


@dataclass(frozen=True, slots=True, kw_only=True)
class _LoggerConfiguration:
    """保存用于装配和同名比较的 Logger 配置。"""

    name: str
    console: bool
    persist: bool
    console_level: _LogLevel | None
    persist_level: _LogLevel | None
    log_dir: Path | None
    max_bytes: int | None
    backup_count: int | None

    @classmethod
    def from_parameters(
        cls,
        name: str,
        *,
        console: bool,
        persist: bool,
        console_level: _LogLevelName,
        persist_level: _LogLevelName,
        log_dir: str | Path | None,
        max_bytes: int | None,
        backup_count: int | None,
    ) -> "_LoggerConfiguration":
        """校验八项公开参数，在访问 logging 共享状态前拒绝无效请求。"""

        cls._validate_name(name)
        if not isinstance(console, bool):
            raise TypeError("console 必须是布尔值")
        if not isinstance(persist, bool):
            raise TypeError("persist 必须是布尔值")
        if not console and not persist:
            raise ValueError("console 和 persist 至少必须启用一个")

        checked_console_level = _LogLevel.from_name(console_level, "console_level")
        checked_persist_level = _LogLevel.from_name(persist_level, "persist_level")

        if not persist:
            if log_dir is not None or max_bytes is not None or backup_count is not None:
                raise ValueError(
                    "persist=False 时不能设置 log_dir、max_bytes 或 backup_count"
                )
            return cls(
                name=name,
                console=console,
                persist=persist,
                console_level=checked_console_level,
                persist_level=None,
                log_dir=None,
                max_bytes=None,
                backup_count=None,
            )

        if log_dir is None:
            raise ValueError("persist=True 时必须设置 log_dir")
        if not isinstance(log_dir, (str, Path)):
            raise TypeError("log_dir 必须是字符串或 pathlib.Path")
        if isinstance(log_dir, str) and not log_dir.strip():
            raise ValueError("log_dir 不能为空字符串")

        checked_max_bytes = cls._validate_positive_integer(max_bytes, "max_bytes")
        checked_backup_count = cls._validate_positive_integer(
            backup_count, "backup_count"
        )
        # 在创建入口固定相对路径和用户目录的含义，后续工作目录变化不会改变同名
        # Logger 的配置比较结果，也不会让文件输出临时转向另一个目录。
        normalized_directory = Path(log_dir).expanduser().resolve()
        configured_console_level: _LogLevel | None = checked_console_level
        if not console:
            configured_console_level = None
        return cls(
            name=name,
            console=console,
            persist=persist,
            console_level=configured_console_level,
            persist_level=checked_persist_level,
            log_dir=normalized_directory,
            max_bytes=checked_max_bytes,
            backup_count=checked_backup_count,
        )

    @staticmethod
    def _validate_name(name: str) -> None:
        if not isinstance(name, str):
            raise TypeError("Logger 名称必须是字符串")
        # getLogger("root") 返回根 Logger，不能等到检查已有 Handler 才拒绝；
        # 一个尚未配置日志的宿主，其根 Logger 可能完全没有 Handler 或 Filter。
        if name == "root":
            raise ValueError("Logger 名称不能使用保留名称 root")
        if re.fullmatch(_LOGGER_NAME_PATTERN, name) is None:
            raise ValueError(
                "Logger 名称必须以英文字母或数字开头，且只能包含英文字母、数字、"
                "下划线、连字符和点"
            )

    @staticmethod
    def _validate_positive_integer(value: int | None, field_name: str) -> int:
        # bool 是 int 的子类，但 True 不能作为有意义的轮转阈值或备份数量。
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{field_name} 必须是大于零的整数")
        return value

"""渲染固定字段 JSONL，并在交互终端为完整日志行添加颜色。"""

import json
import logging
from datetime import datetime, timezone
from enum import Enum

from .locations import _ModuleLocator


class _ConsoleColor(Enum):
    """定义终端输出使用的固定 ANSI 颜色集合。"""

    RESET = "\033[0m"
    WHITE = "\033[37m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"


class _JSONLineFormatter(logging.Formatter):
    """把 LogRecord 转换为一行固定字段 JSON。"""

    def __init__(self, module_locator: _ModuleLocator) -> None:
        """接收各输出目标共享的模块定位实例。"""

        super().__init__()
        self._module_locator = module_locator

    def format(self, record: logging.LogRecord) -> str:
        """生成可写入 UTF-8 JSONL 的单行日志文本。"""

        created_at = datetime.fromtimestamp(record.created, tz=timezone.utc)
        timestamp = created_at.isoformat(timespec="milliseconds")
        # LogRecord.__dict__ 是 logging 接收 extra 的动态边界。Filter 已保证 data
        # 为字典；这里只复制当前格式化所需的顶层内容，不改动调用方字典或 LogRecord。
        # 固定字段字典仅用于本方法的 JSON 序列化，没有跨模块传递数据结构的需要。
        business_fields: dict[object, object] = record.__dict__.get("data", {})
        structured_record: dict[str, object] = {
            "timestamp": timestamp.replace("+00:00", "Z"),
            "module": record.name,
            "location": self._module_locator.resolve(record),
            "level": record.levelname.lower(),
            "msg": record.getMessage(),
            "data": dict(business_fields),
        }
        if record.exc_info is not None:
            # logging.Formatter 的标准异常格式化会保留 raise ... from ... 的异常链。
            # JSON 编码负责转义 traceback 内的换行，确保异常日志也只占一个物理行。
            structured_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(structured_record, ensure_ascii=False)


class _ColoredConsoleFormatter(logging.Formatter):
    """复用 JSON 渲染结果，并按级别添加固定终端颜色。"""

    def __init__(self, formatter: _JSONLineFormatter, *, colors: bool) -> None:
        """接收 JSON 渲染协作者和创建时确定的终端能力。"""

        super().__init__()
        self._formatter = formatter
        self._colors = colors

    def format(self, record: logging.LogRecord) -> str:
        """在交互终端着色，重定向时直接返回可解析的 JSON。"""

        # 两个 Formatter 都遵守 logging 的 format 钩子。本类组合 JSON Formatter，
        # 只负责呈现颜色；字段或异常格式变化不需要再维护另一份 JSON 组装代码。
        message = self._formatter.format(record)
        if not self._colors:
            return message

        match record.levelno:
            case logging.DEBUG:
                color = _ConsoleColor.WHITE
            case logging.INFO:
                color = _ConsoleColor.GREEN
            case logging.WARNING:
                color = _ConsoleColor.YELLOW
            case logging.ERROR:
                color = _ConsoleColor.RED
            case logging.CRITICAL:
                color = _ConsoleColor.MAGENTA
            case _:
                return message
        return f"{color.value}{message}{_ConsoleColor.RESET.value}"

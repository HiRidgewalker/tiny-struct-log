"""管理 Logger 创建的共享状态，并提供唯一的公共创建入口。"""

import logging
import threading
from contextlib import ExitStack
from pathlib import Path

from .configuration import _LoggerConfiguration
from .filters import _FixedFieldsFilter
from .formatters import _JSONLineFormatter
from .handlers import _LogOutputs
from .locations import _ModuleLocator


class _LoggerSetup:
    """管理同名配置、创建锁和 Logger 装配过程。"""

    def __init__(self) -> None:
        """建立本进程共享的创建状态，不访问日志输出目标。"""

        self._configurations_by_name: dict[str, _LoggerConfiguration] = {}
        self._creation_lock = threading.Lock()
        self._module_locator = _ModuleLocator()

    def create(self, configuration: _LoggerConfiguration) -> logging.Logger:
        """串行完成同名检查和装配，成功后才保存配置。"""

        # getLogger() 按名称共享对象。锁必须同时覆盖配置检查和 Handler 挂载，
        # 否则两个线程可能都认为需要初始化，最终让一条日志被重复输出。
        with self._creation_lock:
            name = configuration.name
            existing_configuration = self._configurations_by_name.get(name)
            if existing_configuration is not None:
                if existing_configuration != configuration:
                    raise ValueError(
                        f"Logger {name!r} 已使用另一组配置创建，不能在同一进程中重新配置"
                    )
                logger = logging.getLogger(name)
                # 同配置复用也落实隔离约定，避免外部改动传播开关后继续向祖先输出。
                logger.propagate = False
                return logger

            logger = logging.getLogger(name)
            if logger.handlers or logger.filters:
                raise RuntimeError(
                    f"Logger {name!r} 已存在 Handler 或 Filter，tiny_struct_log 不会覆盖它"
                )

            self._attach_outputs(logger, configuration)
            self._configurations_by_name[name] = configuration
            return logger

    def _attach_outputs(
        self,
        logger: logging.Logger,
        configuration: _LoggerConfiguration,
    ) -> None:
        """先构造全部输出，再将资源所有权交给 Logger。"""

        formatter = _JSONLineFormatter(self._module_locator)
        field_filter = _FixedFieldsFilter()
        output_handlers: list[logging.Handler] = []
        # 创建文件目录可能失败。ExitStack 在失败时关闭已创建的终端 Handler；
        # 此时尚未修改 Logger，异常原样向上传递，调用方可以修正目录后重新创建。
        with ExitStack() as cleanup:
            if configuration.console:
                console_handler = _LogOutputs.create_console(formatter)
                cleanup.callback(console_handler.close)
                output_handlers.append(console_handler)
            if configuration.persist:
                # 配置构造已保证持久化三项完整；断言在内部类型边界表达这一不变量。
                assert configuration.log_dir is not None
                assert configuration.max_bytes is not None
                assert configuration.backup_count is not None
                log_path = configuration.log_dir / f"{configuration.name}.jsonl"
                file_handler = _LogOutputs.create_file(
                    log_path,
                    configuration.max_bytes,
                    configuration.backup_count,
                    formatter,
                )
                cleanup.callback(file_handler.close)
                output_handlers.append(file_handler)

            logger.setLevel(logging.INFO)
            logger.disabled = False
            # 点分名称也可能有业务父 Logger。False 会同时阻止向父 Logger 和根
            # Logger 传播；各 Handler 只负责当前 Logger 自己的输出目标。
            logger.propagate = False
            logger.addFilter(field_filter)
            for handler in output_handlers:
                logger.addHandler(handler)

            # 此后由 logging.shutdown() 统一关闭 Handler，不在创建函数退出时关闭。
            cleanup.pop_all()


_logger_setup = _LoggerSetup()


def create_logger(
    name: str,
    *,
    console: bool,
    persist: bool,
    log_dir: str | Path | None = None,
    max_bytes: int | None = None,
    backup_count: int | None = None,
) -> logging.Logger:
    """创建或复用固定 INFO 等级、禁止向上传播的结构化 Logger。

    名称同时决定 JSON 的 module 字段和 <log_dir>/<name>.jsonl 文件名；
    保留名称 root 始终被拒绝。创建及同配置复用均设置 propagate=False，
    使日志只经过自身的 Handler，不交给父 Logger 或根 Logger。
    业务扩展信息继续使用标准库的 extra={"data": {...}} 入口。
    """

    configuration = _LoggerConfiguration.from_parameters(
        name,
        console=console,
        persist=persist,
        log_dir=log_dir,
        max_bytes=max_bytes,
        backup_count=backup_count,
    )
    return _logger_setup.create(configuration)

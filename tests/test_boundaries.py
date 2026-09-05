"""从公开入口验证 Logger 的名称限制、宿主隔离和创建边界。"""

import importlib
import io
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

from tiny_struct_log import create_logger

from tests.support import _read_json_lines


def _create_concurrently(
    name: str, barrier: threading.Barrier, log_dir: Path
) -> logging.Logger:
    # 让所有工作线程越过同一屏障后再请求创建，实际经过公开入口的加锁流程。
    barrier.wait(timeout=5)
    return create_logger(
        name,
        console=False,
        persist=True,
        log_dir=log_dir,
        max_bytes=4096,
        backup_count=2,
    )


@pytest.mark.functional
class TestLoggerBoundariesFunctional:
    """验证日志包对宿主 logging 状态的保护。"""

    def test_root_name_is_rejected(self) -> None:
        """root 是标准库根 Logger 的保留名称，必须在装配前拒绝。"""

        root_logger = logging.getLogger()
        original_level = root_logger.level
        original_handlers = root_logger.handlers[:]
        original_filters = root_logger.filters[:]
        original_disabled = root_logger.disabled
        original_propagation = root_logger.propagate

        with pytest.raises(ValueError, match="root"):
            create_logger("root", console=True, persist=False)

        assert root_logger.level == original_level
        assert root_logger.handlers == original_handlers
        assert root_logger.filters == original_filters
        assert root_logger.disabled == original_disabled
        assert root_logger.propagate == original_propagation

    @pytest.mark.parametrize("reuse", [False, True])
    def test_logs_stay_on_created_logger(self, logger_name: str, reuse: bool) -> None:
        """创建和同配置复用均应阻断向业务父 Logger 及根 Logger 传播。"""

        parent_name = logger_name.rpartition(".")[0]
        parent_logger = logging.getLogger(parent_name)
        root_logger = logging.getLogger()
        with io.StringIO() as terminal, io.StringIO() as parent_output:
            with io.StringIO() as root_output:
                parent_handler = logging.StreamHandler(parent_output)
                root_handler = logging.StreamHandler(root_output)
                parent_logger.addHandler(parent_handler)
                root_logger.addHandler(root_handler)
                try:
                    with redirect_stdout(terminal):
                        logger = create_logger(logger_name, console=True, persist=False)
                        if reuse:
                            logger.propagate = True
                            reused_logger = create_logger(
                                logger_name, console=True, persist=False
                            )
                            assert reused_logger is logger
                        logger.info("日志只交给自己的输出目标")
                    assert logger.propagate is False
                    assert len(terminal.getvalue().splitlines()) == 1
                    assert parent_output.getvalue() == ""
                    assert root_output.getvalue() == ""
                finally:
                    parent_logger.removeHandler(parent_handler)
                    root_logger.removeHandler(root_handler)
                    parent_handler.close()
                    root_handler.close()

    def test_concurrent_creation_reuses_logger(
        self, logger_name: str, tmp_path: Path
    ) -> None:
        """多个线程同时首次创建，只装配一组 Handler，日志也只输出一次。"""

        worker_count = 4
        barrier = threading.Barrier(worker_count)
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [
                executor.submit(_create_concurrently, logger_name, barrier, tmp_path)
                for _ in range(worker_count)
            ]
            loggers = [future.result(timeout=10) for future in futures]
        logger = loggers[0]
        for created_logger in loggers:
            assert created_logger is logger
            assert created_logger.propagate is False
        assert len(logger.handlers) == 1
        logger.info("并发创建完成")
        records = _read_json_lines(tmp_path / f"{logger_name}.jsonl")
        assert len(records) == 1
        assert records[0]["msg"] == "并发创建完成"

    def test_directory_failure_releases_output(
        self, logger_name: str, tmp_path: Path
    ) -> None:
        """真实目录冲突应关闭已创建输出，并允许修正路径后重新创建。"""

        blocked_path = tmp_path / "occupied"
        blocked_path.write_text("这里是文件，不能作为目录", encoding="utf-8")
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)
        logger.disabled = True
        with patch.object(
            logging.StreamHandler, "close", autospec=True,
            side_effect=logging.Handler.close,
        ) as close_output:
            with pytest.raises(FileExistsError):
                create_logger(
                    logger_name,
                    console=True,
                    persist=True,
                    log_dir=blocked_path,
                    max_bytes=4096,
                    backup_count=2,
                )
            close_output.assert_called_once()
        assert logger.handlers == []
        assert logger.filters == []
        assert logger.level == logging.WARNING
        assert logger.disabled is True
        assert logger.propagate is True

        working_directory = tmp_path / "logs"
        created_logger = create_logger(
            logger_name,
            console=False,
            persist=True,
            log_dir=working_directory,
            max_bytes=4096,
            backup_count=2,
        )
        assert created_logger is logger
        created_logger.info("修正路径后创建成功")
        records = _read_json_lines(working_directory / f"{logger_name}.jsonl")
        assert records[0]["msg"] == "修正路径后创建成功"

    def test_example_import_has_no_side_effects(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """导入示例不会创建 Logger、创建目录或向终端输出。"""

        monkeypatch.chdir(tmp_path)
        with io.StringIO() as terminal:
            with redirect_stdout(terminal):
                with patch.object(logging, "getLogger", wraps=logging.getLogger) as lookup:
                    importlib.import_module("examples.basic")
                    lookup.assert_not_called()
            assert terminal.getvalue() == ""
        assert list(tmp_path.iterdir()) == []

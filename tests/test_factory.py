"""从公开入口验证有限参数、同名复用和宿主配置隔离。"""

import logging
from pathlib import Path

import pytest

from tiny_struct_log import create_logger


@pytest.mark.functional
class TestLoggerFactoryFunctional:
    """验证 Logger 的创建和配置约束。"""

    def test_same_name_and_configuration_return_same_logger(
        self, logger_name: str, tmp_path: Path
    ) -> None:
        """完全相同的创建请求不应重复添加 Handler。"""

        first_logger = create_logger(
            logger_name, console=True, persist=True,
            log_dir=tmp_path, max_bytes=1024, backup_count=2,
        )
        second_logger = create_logger(
            logger_name, console=True, persist=True,
            log_dir=tmp_path, max_bytes=1024, backup_count=2,
        )
        assert first_logger is second_logger
        assert isinstance(first_logger, logging.Logger)
        assert len(first_logger.handlers) == 2

    def test_same_name_cannot_change_configuration(
        self, logger_name: str, tmp_path: Path
    ) -> None:
        """同名 Logger 不能在同一进程中静默切换配置。"""

        create_logger(logger_name, console=True, persist=False)
        with pytest.raises(ValueError, match="另一组配置"):
            create_logger(
                logger_name, console=False, persist=True,
                log_dir=tmp_path, max_bytes=1024, backup_count=2,
            )

    def test_create_logger_does_not_modify_root_logger(self, logger_name: str) -> None:
        """创建包内 Logger 不应覆盖宿主项目的根 Logger。"""

        root_logger = logging.getLogger()
        original_level = root_logger.level
        original_handlers = root_logger.handlers[:]
        sentinel_handler = logging.NullHandler()
        root_logger.addHandler(sentinel_handler)
        root_logger.setLevel(logging.CRITICAL)
        try:
            logger = create_logger(logger_name, console=True, persist=False)
            assert root_logger.level == logging.CRITICAL
            assert sentinel_handler in root_logger.handlers
            assert logger.propagate is False
        finally:
            root_logger.removeHandler(sentinel_handler)
            sentinel_handler.close()
            root_logger.setLevel(original_level)
        assert root_logger.handlers == original_handlers

    @pytest.mark.parametrize("component", [logging.NullHandler, logging.Filter])
    def test_existing_logger_components_are_not_overwritten(
        self, logger_name: str, component: type[logging.Handler] | type[logging.Filter]
    ) -> None:
        """已有 Handler 或 Filter 的同名标准 Logger 应保持原有配置。"""

        occupied_logger = logging.getLogger(logger_name)
        sentinel = component()
        if isinstance(sentinel, logging.Handler):
            occupied_logger.addHandler(sentinel)
        else:
            occupied_logger.addFilter(sentinel)
        with pytest.raises(RuntimeError, match="不会覆盖"):
            create_logger(logger_name, console=True, persist=False)
        if isinstance(sentinel, logging.Handler):
            assert sentinel in occupied_logger.handlers
        else:
            assert sentinel in occupied_logger.filters

    def test_output_and_persistence_options_are_strictly_validated(
        self, logger_name: str
    ) -> None:
        """无输出和没有意义的持久化参数都应被拒绝。"""

        with pytest.raises(ValueError, match="至少必须启用一个"):
            create_logger(logger_name, console=False, persist=False)
        with pytest.raises(ValueError, match="必须设置 log_dir"):
            create_logger(
                logger_name, console=False, persist=True, max_bytes=1024, backup_count=2
            )
        with pytest.raises(ValueError, match="persist=False"):
            create_logger(logger_name, console=True, persist=False, log_dir="logs")

    @pytest.mark.parametrize(
        ("max_bytes", "backup_count", "field_name"),
        [(0, 2, "max_bytes"), (True, 2, "max_bytes"), (1024, True, "backup_count"),
         (None, 2, "max_bytes"), (1024, None, "backup_count"), (1024, -1, "backup_count")],
    )
    def test_rotation_values_are_validated(
        self, logger_name: str, tmp_path: Path,
        max_bytes: int | None, backup_count: int | None, field_name: str,
    ) -> None:
        """轮转参数必须为正整数，缺失值和 bool 不能通过校验。"""

        with pytest.raises(ValueError, match=field_name):
            create_logger(
                logger_name, console=False, persist=True,
                log_dir=tmp_path, max_bytes=max_bytes, backup_count=backup_count,
            )

    @pytest.mark.parametrize("name", ["", "../pay", "/pay", "pay/log", " pay"])
    def test_invalid_name_is_rejected(self, name: str) -> None:
        """名称不能组成任意文件路径。"""

        with pytest.raises(ValueError, match="Logger 名称"):
            create_logger(name, console=True, persist=False)

    def test_persistent_logger_creates_directory_but_delays_file(
        self, logger_name: str, tmp_path: Path
    ) -> None:
        """创建持久化 Logger 时建立目录，第一条日志到来后才建立文件。"""

        log_dir = tmp_path / "nested" / "logs"
        logger = create_logger(
            logger_name, console=False, persist=True,
            log_dir=log_dir, max_bytes=1024, backup_count=2,
        )
        log_path = log_dir / f"{logger_name}.jsonl"
        assert log_dir.is_dir()
        assert not log_path.exists()
        logger.info("创建文件")
        assert log_path.is_file()

    def test_equivalent_paths_reuse_logger(
        self, logger_name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """相对路径和对应的绝对路径应被视为同一份配置。"""

        monkeypatch.chdir(tmp_path)
        relative_logger = create_logger(
            logger_name, console=False, persist=True,
            log_dir="logs", max_bytes=1024, backup_count=2,
        )
        absolute_logger = create_logger(
            logger_name, console=False, persist=True,
            log_dir=tmp_path / "logs", max_bytes=1024, backup_count=2,
        )
        assert relative_logger is absolute_logger
        assert len(absolute_logger.handlers) == 1

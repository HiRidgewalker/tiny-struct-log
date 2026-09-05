"""从公开入口验证固定 JSON 字段、文件路由、终端颜色和异常链。"""

import io
import json
import logging
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from tiny_struct_log import create_logger

from tests.support import _read_json_lines


class _InteractiveTextBuffer(io.StringIO):
    """模拟交互终端，便于在没有真实终端时验证颜色输出。"""

    def isatty(self) -> bool:
        """返回标准流接口要求的终端状态。"""

        return True


@pytest.mark.functional
class TestStructuredOutputFunctional:
    """验证结构化日志的可观察输出。"""

    def test_fixed_fields_location_and_file_name(
        self, logger_name: str, tmp_path: Path
    ) -> None:
        """Logger 名称决定 module 和文件名，location 应为真正调用模块。"""

        logger = create_logger(
            logger_name, console=False, persist=True,
            log_dir=tmp_path, max_bytes=4096, backup_count=2,
        )
        logger.debug("这条日志不会输出")
        logger.info("订单创建成功", extra={"data": {"order_id": "O-1001"}})
        records = _read_json_lines(tmp_path / f"{logger_name}.jsonl")
        assert len(records) == 1
        record = records[0]
        assert set(record) == {"timestamp", "module", "location", "level", "msg", "data"}
        assert str(record["timestamp"]).endswith("Z")
        assert record["module"] == logger_name
        assert record["location"] == __name__
        assert record["level"] == "info"
        assert record["msg"] == "订单创建成功"
        assert record["data"] == {"order_id": "O-1001"}

    def test_missing_data_is_an_empty_dict(
        self, logger_name: str, tmp_path: Path
    ) -> None:
        """调用方没有提供 data 时，输出仍应包含空字典。"""

        logger = create_logger(
            logger_name, console=False, persist=True,
            log_dir=tmp_path, max_bytes=4096, backup_count=2,
        )
        logger.info("服务启动完成")
        records = _read_json_lines(tmp_path / f"{logger_name}.jsonl")
        assert records[0]["data"] == {}

    def test_additional_information_must_use_data_dict(self, logger_name: str) -> None:
        """独立扩展字段和非字典 data 应被明确拒绝。"""

        logger = create_logger(logger_name, console=True, persist=False)
        with pytest.raises(ValueError, match="放入 data 字典"):
            logger.info("字段位置错误", extra={"order_id": "O-1001"})
        with pytest.raises(TypeError, match="data 字段必须是字典"):
            logger.info("字段类型错误", extra={"data": "O-1001"})

    @pytest.mark.parametrize(
        ("level", "color"),
        [(logging.INFO, "\033[32m"), (logging.WARNING, "\033[33m"),
         (logging.ERROR, "\033[31m"), (logging.CRITICAL, "\033[35m")],
    )
    def test_interactive_terminal_has_color(
        self, logger_name: str, level: int, color: str
    ) -> None:
        """交互终端按日志级别显示固定颜色。"""

        with _InteractiveTextBuffer() as terminal:
            with redirect_stdout(terminal):
                logger = create_logger(logger_name, console=True, persist=False)
                logger.log(level, "终端颜色测试")
            terminal_text = terminal.getvalue()
        assert terminal_text.startswith(color)
        assert terminal_text.endswith("\033[0m\n")
        json_text = terminal_text.removeprefix(color).removesuffix("\033[0m\n")
        assert json.loads(json_text)["msg"] == "终端颜色测试"

    def test_console_can_be_disabled(self, logger_name: str, tmp_path: Path) -> None:
        """console=False 时日志只持久化，不应写入标准输出。"""

        with io.StringIO() as terminal:
            with redirect_stdout(terminal):
                logger = create_logger(
                    logger_name, console=False, persist=True,
                    log_dir=tmp_path, max_bytes=4096, backup_count=2,
                )
                logger.info("只写文件")
            assert terminal.getvalue() == ""
        records = _read_json_lines(tmp_path / f"{logger_name}.jsonl")
        assert records[0]["msg"] == "只写文件"

    def test_exception_chain_stays_in_one_json_line(
        self, logger_name: str, tmp_path: Path
    ) -> None:
        """from 形成的完整异常链应保存在一条可解析的 JSONL 记录中。"""

        logger = create_logger(
            logger_name, console=False, persist=True,
            log_dir=tmp_path, max_bytes=16 * 1024, backup_count=2,
        )
        try:
            try:
                _ = 1 / 0
            except ZeroDivisionError as exc:
                raise RuntimeError("支付计算中断") from exc
        except RuntimeError:
            logger.exception("支付失败", extra={"data": {"order_id": "O-1001"}})
        log_path = tmp_path / f"{logger_name}.jsonl"
        physical_lines = log_path.read_text(encoding="utf-8").splitlines()
        assert len(physical_lines) == 1
        record = json.loads(physical_lines[0])
        assert "ZeroDivisionError" in record["exception"]
        assert "RuntimeError" in record["exception"]

    def test_redirected_output_matches_file(
        self, logger_name: str, tmp_path: Path
    ) -> None:
        """终端重定向后应与文件产生相同 JSON，且不改动业务字典。"""

        business_fields = {"order_id": "O-1001"}
        with io.StringIO() as terminal:
            with redirect_stdout(terminal):
                logger = create_logger(
                    logger_name, console=True, persist=True,
                    log_dir=tmp_path, max_bytes=4096, backup_count=2,
                )
                logger.info("订单 %s\n已创建", "O-1001", extra={"data": business_fields})
            terminal_text = terminal.getvalue()
        records = _read_json_lines(tmp_path / f"{logger_name}.jsonl")
        assert "\033" not in terminal_text
        assert len(terminal_text.splitlines()) == 1
        assert json.loads(terminal_text) == records[0]
        assert records[0]["msg"] == "订单 O-1001\n已创建"
        assert business_fields == {"order_id": "O-1001"}

    def test_missing_source_uses_record_module(
        self, logger_name: str, tmp_path: Path
    ) -> None:
        """标准 Logger 收到无导入模块对应的记录时仍能输出模块简称。"""

        logger = create_logger(
            logger_name, console=False, persist=True,
            log_dir=tmp_path, max_bytes=4096, backup_count=2,
        )
        record = logging.LogRecord(
            name=logger_name, level=logging.INFO,
            pathname=str(tmp_path / "unloaded_module.py"),
            lineno=1, msg="无导入模块的日志", args=(), exc_info=None,
        )
        logger.handle(record)
        records = _read_json_lines(tmp_path / f"{logger_name}.jsonl")
        assert records[0]["location"] == "unloaded_module"
        assert records[0]["data"] == {}
        assert "data" not in record.__dict__

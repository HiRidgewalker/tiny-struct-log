"""从公开入口验证 JSONL 文件的大小轮转和备份数量限制。"""

from pathlib import Path

import pytest

from tiny_struct_log import create_logger

from tests.support import _read_json_lines


@pytest.mark.functional
class TestFileRotationFunctional:
    """验证持久化日志的轮转结果。"""

    def test_file_rotates_at_configured_size(
        self, logger_name: str, tmp_path: Path
    ) -> None:
        """持续写入应产生限定数量的备份，保留下来的文件仍是完整 JSONL。"""

        logger = create_logger(
            logger_name, console=False, persist=True,
            log_dir=tmp_path, max_bytes=350, backup_count=2,
        )
        for index in range(12):
            logger.info(
                "轮转测试",
                extra={"data": {"index": index, "payload": "x" * 120}},
            )

        assert (tmp_path / f"{logger_name}.jsonl.1").exists()
        backup_paths = list(tmp_path.glob(f"{logger_name}.jsonl.*"))
        assert len(backup_paths) == 2
        for path in [tmp_path / f"{logger_name}.jsonl", *backup_paths]:
            records = _read_json_lines(path)
            assert records
            for record in records:
                assert record["module"] == logger_name
                assert record["msg"] == "轮转测试"

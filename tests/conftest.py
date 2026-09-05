"""管理测试 Logger 的独立名称及 Handler 生命周期。"""

import logging
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest


@pytest.fixture
def logger_name(tmp_path: Path) -> Iterator[str]:
    """提供独立的点分名称，并在临时目录释放前关闭测试日志资源。"""

    # 依赖 tmp_path 使本 Fixture 先清理文件 Handler，再清理临时目录，兼容文件打开
    # 时不能删除的系统。唯一名称也避免同一进程多次执行用例时碰到旧的配置记录。
    name = f"test_{uuid4().hex}.payment"
    try:
        yield name
    finally:
        logger = logging.getLogger(name)
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            handler.close()
        for logging_filter in logger.filters[:]:
            logger.removeFilter(logging_filter)
        logger.setLevel(logging.NOTSET)
        logger.disabled = False
        logger.propagate = True

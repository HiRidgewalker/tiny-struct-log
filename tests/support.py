"""提供测试断言使用的 JSONL 文件读取操作。"""

import json
from pathlib import Path


def _read_json_lines(path: Path) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines()]

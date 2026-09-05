"""根据调用文件定位 Python 模块，并缓存成功的匹配结果。"""

import logging
import sys
from pathlib import Path


class _ModuleLocator:
    """维护调用文件与完整导入模块名称的对应关系。"""

    def __init__(self) -> None:
        """初始化成功定位结果的缓存。"""

        self._names_by_path: dict[Path, str] = {}

    def resolve(self, record: logging.LogRecord) -> str:
        """返回完整模块名称；没有对应导入模块时使用记录自带的模块简称。"""

        # LogRecord.module 仅含文件名，pathname 才能区分不同包里的同名源文件。
        # 缓存由装配对象注入的同一实例持有，终端与文件输出共同复用成功结果。
        source_path = Path(record.pathname).resolve()
        cached_name = self._names_by_path.get(source_path)
        if cached_name is not None:
            return cached_name

        # 其他线程可能正在导入模块，先复制条目，避免遍历可变的 sys.modules。
        for module_name, module in tuple(sys.modules.items()):
            module_file = getattr(module, "__file__", None)
            if module_file is None:
                continue
            try:
                module_path = Path(module_file).resolve()
            except (OSError, RuntimeError):
                # 一个候选模块的路径不可解析，只说明它不能用于此次匹配；
                # 跳过该候选并继续查找。实际调用文件的路径解析错误仍原样抛出。
                continue
            if module_path == source_path:
                self._names_by_path[source_path] = module_name
                return module_name

        # 冻结模块或动态代码可能没有对应源文件。这是允许的定位缺失，不缓存简称，
        # 以便未来模块导入完成后能够重新匹配完整名称。
        return record.module

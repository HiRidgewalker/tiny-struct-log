"""在 LogRecord 进入输出链前校验业务扩展字段。"""

import logging


class _FixedFieldsFilter(logging.Filter):
    """限制业务扩展字段，使所有输出目标遵守同一份字段约定。"""

    def __init__(self) -> None:
        """根据当前解释器建立标准日志字段集合。"""

        super().__init__()
        # 由当前解释器的 LogRecord 提供标准属性名，避免手写清单漏掉标准库字段。
        # 这份集合属于 Filter 的校验状态，不在模块导入时构造临时日志记录。
        standard_record = logging.LogRecord(
            name="",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="",
            args=(),
            exc_info=None,
        )
        self._standard_fields = frozenset(standard_record.__dict__)

    def filter(self, record: logging.LogRecord) -> bool:
        """放行符合约定的记录，对非法扩展字段直接抛出异常。"""

        # filter 是 logging.Filter 的标准钩子名称。Logger 在调用 Handler 前执行
        # 它，因此字段错误会直接反馈业务调用方，不会等到文件输出时才被发现。
        custom_fields = set(record.__dict__) - self._standard_fields
        unexpected_fields = custom_fields - {"data"}
        if unexpected_fields:
            field_names = "、".join(sorted(unexpected_fields))
            raise ValueError(
                "不支持独立的日志扩展字段，请将这些信息放入 data 字典："
                + field_names
            )

        # extra 是标准库明确提供的动态边界，只读取其已有属性字典。
        # 本包不补写或替换 LogRecord 属性，缺失 data 时由 Formatter 补齐 JSON。
        business_fields: object = record.__dict__.get("data", {})
        if not isinstance(business_fields, dict):
            raise TypeError("日志的 data 字段必须是字典")
        return True

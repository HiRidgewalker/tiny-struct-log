"""演示从 tiny_struct_log 创建并使用两个逻辑 Logger。"""

from tiny_struct_log import create_logger


def main() -> None:
    """分别记录普通业务日志和带异常堆栈的支付日志。"""

    # 把创建放在入口内，导入示例模块时不会创建目录，也不会向 Logger 挂载组件。
    log_dir = "logs"
    max_bytes = 10 * 1024 * 1024
    backup_count = 5
    general_logger = create_logger(
        "general",
        console=True,
        persist=True,
        log_dir=log_dir,
        max_bytes=max_bytes,
        backup_count=backup_count,
    )
    pay_logger = create_logger(
        "pay",
        console=True,
        persist=True,
        log_dir=log_dir,
        max_bytes=max_bytes,
        backup_count=backup_count,
    )

    general_logger.info(
        "服务启动完成",
        extra={"data": {"port": 8000}},
    )

    try:
        _ = 1 / 0
    except ZeroDivisionError:
        pay_logger.exception(
            "支付金额计算失败",
            extra={"data": {"order_id": "O-1001"}},
        )


if __name__ == "__main__":
    main()

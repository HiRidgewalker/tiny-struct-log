# tiny_struct_log

`tiny_struct_log` 是一个基于 Python 标准库 `logging` 的微型结构化日志包。它不使用
第三方日志运行时，也不追求覆盖所有 logging 配置场景，只提供一条固定、容易理解的
日志处理流水线。

分发包名称使用 `tiny-struct-log`，Python 导入包名称使用 `tiny_struct_log`。

## 功能边界

调用方只能决定：

- Logger 名称；
- 是否输出到终端；
- 终端输出的最低日志等级；
- 是否持久化日志；
- 持久化日志的最低日志等级；
- 持久化目录；
- 单个日志文件的最大字节数；
- 最大轮转备份数量。

以下行为由包固定，不提供配置入口：

- 文件格式为 UTF-8 JSONL；
- 时间为 UTC ISO 8601；
- 文件名为 `<Logger名称>.jsonl`；
- 轮转文件依次为 `.jsonl.1`、`.jsonl.2`；
- 日志字段、终端颜色、Formatter、Handler 和 Filter 固定；
- ERROR 不额外复制到单独文件；
- 不修改宿主项目的根 Logger，也不接管第三方库日志。

Logger 名称禁止使用标准库保留名称 `root`。本包创建和同配置复用的 Logger 均设置
`propagate=False`，日志只进入自身的 Handler，不向业务父 Logger 或根 Logger 传播。

## 安装

本项目不发布到 PyPI，推荐从 GitHub 版本标签安装。

使用 uv：

```bash
uv add git+https://github.com/HiRidgewalker/tiny-struct-log.git --tag V1.0.0
```

使用 pip：

```bash
python -m pip install \
  "tiny-struct-log @ git+https://github.com/HiRidgewalker/tiny-struct-log.git@V1.0.0"
```

建议依赖版本标签或完整 commit，不要让生产项目长期直接跟随 `main` 分支。这样上游
提交新代码时，现有项目不会在下一次安装时突然改变日志行为。

也可以先克隆后安装：

```bash
git clone https://github.com/HiRidgewalker/tiny-struct-log.git
cd tiny-struct-log

# 使用 uv 创建环境、构建并安装当前包。
uv sync
```

如果使用已经激活的普通 Python 虚拟环境，也可以通过 pip 从克隆目录安装：

```bash
python -m pip install .
```

克隆方式适合开发和验证本包。业务项目使用 Git 依赖后，包代码安装在项目虚拟环境
中，不需要把本仓库的 Formatter、Handler 或 Filter 源码复制到业务目录。

## 创建 Logger

只输出终端：

```python
from tiny_struct_log import create_logger

general_logger = create_logger(
    "general",
    console=True,
    persist=False,
)
```

只持久化到文件：

```python
from tiny_struct_log import create_logger

pay_logger = create_logger(
    "pay",
    console=False,
    persist=True,
    log_dir="logs",
    max_bytes=10 * 1024 * 1024,
    backup_count=5,
)
```

同时输出终端和文件：

```python
from tiny_struct_log import create_logger

pay_logger = create_logger(
    "pay",
    console=True,
    persist=True,
    console_level="warning",
    persist_level="debug",
    log_dir="logs",
    max_bytes=10 * 1024 * 1024,
    backup_count=5,
)
```

`console_level` 和 `persist_level` 分别控制终端和文件 Handler 的最低输出等级，默认
均为 `"info"`。只接受 `"debug"`、`"info"`、`"warning"`、`"error"` 和
`"critical"` 五种小写字符串；大写名称、别名、`"notset"` 和 logging 数值常量
都会被拒绝。两路输出可以采用不同等级，例如上面的终端输出 `WARNING` 及以上日志，
文件从 `DEBUG` 开始持久化。

某一路输出关闭时，其等级参数仍会接受合法性校验，但不会影响实际输出和同名 Logger
的配置比较。

当 `persist=True` 时，`log_dir`、`max_bytes` 和 `backup_count` 都是必需参数。日志
目录不存在时会自动创建；由于文件 Handler 使用延迟打开，具体 JSONL 文件会在第一
条日志到来时创建。

`console` 和 `persist` 不能同时为 `False`，否则 Logger 没有任何输出目标。

名称必须以英文字母或数字开头，后续只允许英文字母、数字、下划线、连字符和点；
`root` 始终抛出 `ValueError`，即使根 Logger 尚未配置任何 Handler 也不会被本包修改。

## 记录日志

普通日志：

```python
pay_logger.info(
    "支付成功",
    extra={
        "data": {
            "order_id": "O-1001",
            "amount": 99.8,
        }
    },
)
```

没有扩展信息时可以省略 `extra`，JSON 输出会自动包含空的 `data` 字典：

```python
pay_logger.info("支付模块启动完成")
```

`extra` 是标准库 logging 向 `LogRecord` 增加业务信息的原生入口。顶层只允许出现
`data`，其他业务信息必须放入该字典：

```python
# 错误：order_id 不允许成为独立顶层字段。
pay_logger.info(
    "支付成功",
    extra={"order_id": "O-1001"},
)
```

`data` 内部的值必须能够被标准 JSON 编码，例如字符串、数字、布尔值、列表、字典
和 `None`。不要把异常对象、文件对象、数据库连接等运行时对象直接放入 `data`。

Filter 在记录交给任何 Handler 前校验扩展字段，Formatter 在序列化时读取并浅复制
业务字典。本包不会给 `LogRecord` 主动补写 `data` 属性，也不会替换调用方传入的字典。

## 固定字段

普通日志固定包含：

| 字段 | 含义 | 示例 |
| --- | --- | --- |
| `timestamp` | UTC ISO 8601 时间 | `2026-09-04T08:00:00.123Z` |
| `module` | 创建 Logger 时传入的名称 | `general`、`pay` |
| `location` | 真正调用日志的 Python 模块 | `shop.payment.service` |
| `level` | 日志等级 | `info`、`error` |
| `msg` | 日志消息 | `支付成功` |
| `data` | 业务扩展信息字典 | `{"order_id": "O-1001"}` |

例如：

```json
{
  "timestamp": "2026-09-04T08:00:00.123Z",
  "module": "pay",
  "location": "shop.payment.service",
  "level": "info",
  "msg": "支付成功",
  "data": {"order_id": "O-1001"}
}
```

## 异常日志

使用标准库的 `logger.exception()`：

```python
try:
    run_payment()
except PaymentError:
    pay_logger.exception(
        "支付处理失败",
        extra={"data": {"order_id": "O-1001"}},
    )
```

异常信息从 `LogRecord.exc_info` 取得，经过标准 traceback 格式化后写入额外的
`exception` 字段。`raise ... from ...` 产生的完整异常链也会保留。堆栈中的真实
换行会被 JSON 转义为 `\n`，因此一条异常日志仍然只占 JSONL 的一个物理行。

## module 与 location

如果 `shop.order.service` 使用名称为 `general` 的 Logger：

```json
{
  "module": "general",
  "location": "shop.order.service"
}
```

`module` 表示日志的逻辑类别，同时决定日志文件名称；`location` 表示真正调用日志
方法的代码模块。同一个 Logger 可以在多个业务文件中共享，而不会丢失实际来源。

业务模块应直接调用 Logger。通过自定义包装函数间接记录时，location 可能变成包装
函数所在模块；确实需要包装时，可以使用 logging 的 `stacklevel` 参数跳过包装层。

## Logger 生命周期

标准库 `logging.getLogger(name)` 在同一进程中按名称共享 Logger。为避免重复添加
Handler，`create_logger()` 遵循以下规则：

- 同名且配置完全一致：返回同一个 Logger；
- 同配置复用时仍设置 `propagate=False`；
- 同名但配置不同：抛出异常，不静默切换目录或输出方式；
- 同名 Logger 已被宿主项目添加 Handler 或 Filter：抛出异常，不删除宿主配置。

相对路径会在创建入口规范化为绝对路径，因此指向同一目录的相对路径和绝对路径视为
相同配置。并发创建通过同一把锁完成检查与装配，避免重复挂载 Handler。目录创建失败
时会关闭已经构造的输出组件，保留原始异常，调用方修正目录后可以重新创建。

业务项目可以在启动入口创建 Logger，并将其传入需要记录日志的业务函数：

```python
# app/main.py
from tiny_struct_log import create_logger

from app.order.service import create_order


def main() -> None:
    """创建业务 Logger 并启动订单处理。"""

    general_logger = create_logger(
        "general",
        console=True,
        persist=True,
        console_level="warning",
        persist_level="info",
        log_dir="logs",
        max_bytes=10 * 1024 * 1024,
        backup_count=5,
    )
    create_order(general_logger)


if __name__ == "__main__":
    main()
```

```python
# app/order/service.py
import logging


def create_order(logger: logging.Logger) -> None:
    """演示通过传入的 Logger 记录订单结果。"""

    logger.info(
        "订单创建成功",
        extra={"data": {"order_id": "O-1001"}},
    )
```

业务项目只保留自己的 Logger 创建参数，不包含本包的日志实现代码。
本仓库的 `examples/basic.py` 也在 `main()` 内创建 Logger，单纯导入不会创建日志目录。

## 内部处理流程

```text
业务调用 Logger.info() / Logger.exception()
  → Logger 按已启用 Handler 中的最低等级初筛
  → 创建 LogRecord
  → Filter 校验扩展字段和 data 字典类型
  ├── 可选终端 Handler
  │     → 按 console_level 过滤
  │     → JSON Formatter 补齐固定字段，终端 Formatter 按需着色
  │     → 标准输出
  └── 可选轮转文件 Handler
        → 按 persist_level 过滤
        → JSON Formatter 补齐固定字段
        → <Logger名称>.jsonl
```

每个 Logger 的 Handler 都直接挂在自身，并设置 `propagate=False`。点分名称如
`shop.payment` 也不会把日志交给 `shop` 或根 Logger。本包不会修改这些祖先 Logger
的等级、Handler 或 Filter。

内部职责划分如下；这些实现均不属于公共 API，业务代码只导入 `create_logger()`。

| 模块 | 职责 |
| --- | --- |
| `configuration.py` | 校验参数，通过不可变 dataclass 保存规范化配置 |
| `factory.py` | 管理创建锁、同名配置及 Logger 装配 |
| `handlers.py` | 构造终端和轮转文件输出 |
| `filters.py` | 在输出前统一校验扩展字段 |
| `formatters.py` | 生成固定 JSONL，并为终端添加颜色 |
| `locations.py` | 定位完整模块名称，缓存成功匹配 |

终端 Formatter 通过组合复用 JSON Formatter；它们共享装配时传入的模块定位实例。
模块未匹配到源文件时使用 `LogRecord.module` 简称，实际调用路径的解析错误原样抛出。

## 文件轮转限制

文件使用标准库 `RotatingFileHandler`：

```text
pay.jsonl
pay.jsonl.1
pay.jsonl.2
```

`max_bytes` 是触发轮转的字节阈值，不是单条日志的硬上限。如果单条异常日志本身很
大，当前文件仍可能短暂超过这个值。

`RotatingFileHandler` 适合单进程写入。多个进程不能同时轮转同一个文件；多进程
部署时应让不同进程写入不同目录或文件，或者由独立日志写入进程统一处理。

## 本仓库开发与验证

本项目使用 uv 管理，日常开发版本由 `.python-version` 固定为 Python 3.13：

```bash
uv sync
uv run pytest tests/test_factory.py tests/test_output.py tests/test_rotation.py tests/test_boundaries.py
uv run python examples/basic.py
uv build
```

测试依赖 `pytest` 放在 `dev` 依赖组，沿用原有测试目录和场景。Fixture 为每个测试分配
独立 Logger 名称，并在临时目录清理前关闭 Handler。新增场景验证 `root` 名称保护、
祖先传播隔离、两路日志等级、并发首次创建、目录失败清理和示例导入行为。项目尚未
配置类型检查器与 linter。

`pyproject.toml` 显式声明了包发现规则：

```toml
[tool.uv.build-backend]
module-root = "src"
module-name = "tiny_struct_log"
```

`module-root` 表示源码从 `src/` 开始查找；`module-name` 表示真正安装并供 Python
导入的包是 `tiny_struct_log`。即使这两个值与 uv_build 的自动推导结果相同，项目也
不依赖隐式默认值。

构建产物位于 `dist/`：

```text
dist/
├── tiny_struct_log-1.0.0-py3-none-any.whl
└── tiny_struct_log-1.0.0.tar.gz
```

本包支持 Python 3.10～3.14，包元数据声明为 `>=3.10,<3.15`，运行时依赖为空。
Python 3.13 用于日常开发；兼容性验证使用其他受支持版本，不修改开发版本约定。

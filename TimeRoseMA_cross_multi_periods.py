"""
Multi-period trading strategy runner.

Refactored from single-period (OI/3m) to support multiple time periods concurrently.

Concurrency strategy: MULTI-PROCESS with `spawn` start method.

Uses multiprocessing.context 'spawn' instead of default 'fork', because:
- `fork` inherits the parent's ZMQ socket (from signalSend_noblock.py), causing
  multiple child processes to share one socket -> signals are lost / connection hangs.
- `fork` also inherits asyncio event loop state -> tqsdk "暂不支持在多线程下使用" warning.
- `spawn` gives each child a clean process with its own module state, its own
  TqApi connection, and its own ZMQ socket.

tqsdk documentation:
  https://tqsdk-python.readthedocs.io/en/latest/advanced/multi_strategy.html
  -> "每个进程执行一个策略实例"

API:
    run_single_period()   - Blocking: run ONE period in current process
    run_multi_strategy()  - Spawn a child process per config (recommended)
"""

import multiprocessing
from typing import Any, Dict, List

# Use 'spawn' to get clean process isolation (no fork inheritance issues)
_MP_CTX = multiprocessing.get_context("spawn")


def run_single_period(
    product: str,
    interval: int,
    single_volume: int = 1,
    bklimit: int = 2,
    sklimit: int = 2,
    auth: str = "YOUR_TQ_USER,YOUR_TQ_PASSWORD",
) -> None:
    """
    Run ma_cross for one product/period in the current process.

    BLOCKING — creates a TqApi connection and runs an indefinite event loop.
    For multiple periods use run_multi_strategy() to spawn child processes.
    """
    from strategies.TimeRoseMA_cross_speak import ma_cross
    from tqsdk import TqApi, TqKq

    api = TqApi(TqKq(), auth=auth)
    symbol = api.query_cont_quotes(product_id=product)[0]
    print(f"[{product}/{interval}s] 启动策略: 合约={symbol}, 周期={interval}秒")
    try:
        ma_cross(api, symbol, interval, single_volume, bklimit, sklimit)
    finally:
        api.close()


def run_multi_strategy(configs: List[Dict[str, Any]]) -> None:
    """
    Run strategy for MULTIPLE time periods concurrently via child processes.

    Each config spawns an independent process with its own TqApi connection,
    its own event loop, and its own ZMQ socket.  The 'spawn' start method
    ensures no file descriptors or module state are inherited from the parent.

    This is the officially documented approach:
        "每个进程执行一个策略实例"

    Args:
        configs: Each dict requires:
            - product:   str   (e.g. "OI")
            - interval:  int   (seconds, e.g. 60, 180, 300, 900)
            Optional:
            - single_volume: int (1)
            - bklimit:        int (2)
            - sklimit:        int (2)
            - auth:           str ("YOUR_TQ_USER,YOUR_TQ_PASSWORD")

    Usage:
        run_multi_strategy([
            {"product": "OI", "interval": 60},
            {"product": "OI", "interval": 180},
            {"product": "OI", "interval": 300},
            {"product": "OI", "interval": 900},
        ])
    """
    if not configs:
        print("run_multi_strategy: 空的配置列表，无操作。")
        return

    processes: List[_MP_CTX.Process] = []  # type: ignore[valid-type]
    for cfg in configs:
        p = _MP_CTX.Process(
            target=run_single_period,
            kwargs={
                "product": cfg["product"],
                "interval": cfg["interval"],
                "single_volume": cfg.get("single_volume", 1),
                "bklimit": cfg.get("bklimit", 2),
                "sklimit": cfg.get("sklimit", 2),
                "auth": cfg.get("auth", "YOUR_TQ_USER,YOUR_TQ_PASSWORD"),
            },
            name=f"strategy-{cfg['product']}-{cfg['interval']}s",
            daemon=True,
        )
        p.start()
        processes.append(p)

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\n收到中断信号，正在停止所有策略...")
        for p in processes:
            if p.is_alive():
                p.terminate()
                p.join(timeout=5)


def runstrategy() -> None:
    """Backward-compatible entry: run OI across four time periods."""
    run_multi_strategy([
        {"product": "OI", "interval": 60,   "single_volume": 1, "bklimit": 2, "sklimit": 2},
        {"product": "OI", "interval": 180,  "single_volume": 1, "bklimit": 2, "sklimit": 2},
        {"product": "OI", "interval": 300,  "single_volume": 1, "bklimit": 2, "sklimit": 2},
        {"product": "OI", "interval": 900,  "single_volume": 1, "bklimit": 2, "sklimit": 2},
    ])


if __name__ == "__main__":
    # Required guard for 'spawn' start method: without it, the child process
    # would re-execute module-level code and enter an infinite loop.
    runstrategy()

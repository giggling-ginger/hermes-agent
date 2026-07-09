"""Exit when the spawning parent process dies.

Desktop-spawned ``hermes serve`` backends are long-lived Python runtimes
(~330MB). If Electron force-quits or crashes without reaping them, they are
reparented to init/launchd and accumulate indefinitely (#61349).

``tui_gateway.slash_worker`` already runs the same check. This module is the
shared, import-light implementation for any desktop-owned child that must not
outlive its parent.

Detection strategy (mirrors slash_worker):
- Compare ``os.getppid()`` to the original parent PID (reparent → orphan).
- Guard PID reuse via ``psutil.Process.create_time()``.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Callable


def is_orphaned(
    original_ppid: int,
    parent_create_time: float,
    *,
    getppid: Callable[[], int] = os.getppid,
) -> bool:
    """Return True once the original parent is gone or its PID was reused."""
    if getppid() != original_ppid:
        return True
    try:
        import psutil

        if not psutil.pid_exists(original_ppid):
            return True
        return psutil.Process(original_ppid).create_time() != parent_create_time
    except Exception:
        # psutil missing or process vanished mid-check — treat as orphaned.
        return True


def start_parent_death_watchdog(
    *,
    poll_s: float = 2.0,
    getppid: Callable[[], int] = os.getppid,
) -> bool:
    """Start a daemon thread that ``os._exit(0)``s when the parent dies.

    Returns True if the watchdog was started, False if it could not capture
    parent identity (caller may continue without the safety net).
    """
    original_ppid = getppid()
    if original_ppid <= 1:
        # Already reparented or running under init — nothing useful to watch.
        return False

    parent_create_time = 0.0
    try:
        import psutil

        parent_create_time = psutil.Process(original_ppid).create_time()
    except Exception:
        parent_create_time = 0.0

    poll = max(0.05, float(poll_s))

    def _loop() -> None:
        while not is_orphaned(original_ppid, parent_create_time, getppid=getppid):
            time.sleep(poll)
        # Hard exit: skip graceful teardown. The parent is already gone, so
        # nobody is waiting on clean uvicorn shutdown — and a hung graceful
        # path is exactly how orphans accumulate.
        os._exit(0)

    threading.Thread(
        target=_loop,
        name="hermes-parent-death-watchdog",
        daemon=True,
    ).start()
    return True


def start_desktop_parent_death_watchdog() -> bool:
    """Start the watchdog only for desktop-spawned backends (``HERMES_DESKTOP=1``)."""
    if os.environ.get("HERMES_DESKTOP") != "1":
        return False
    return start_parent_death_watchdog()

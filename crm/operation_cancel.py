"""Токен отмены длительных операций."""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import threading
import time

logger = logging.getLogger(__name__)


def kill_process_tree(proc: subprocess.Popen, *, grace_sec: float = 3.0) -> None:
    """SIGTERM/SIGKILL всей группы процессов (bash -lc, git, ng build и дочерние)."""
    if proc.poll() is not None:
        return
    pid = proc.pid
    try:
        pgid = os.getpgid(pid)
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except Exception:
        logger.exception("killpg SIGTERM не удался pid=%s", pid)
        try:
            proc.terminate()
        except Exception:
            logger.exception("terminate fallback pid=%s", pid)
    deadline = time.monotonic() + grace_sec
    while proc.poll() is None and time.monotonic() < deadline:
        try:
            proc.wait(timeout=0.2)
        except subprocess.TimeoutExpired:
            pass
    if proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except ProcessLookupError:
        return
    except Exception:
        logger.exception("killpg SIGKILL не удался pid=%s", pid)
        try:
            proc.kill()
        except Exception:
            logger.exception("kill fallback pid=%s", pid)
    try:
        proc.wait(timeout=2)
    except Exception:
        logger.exception("wait after kill pid=%s", pid)


class CancelToken:
    def __init__(self) -> None:
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None

    def request_cancel(self) -> None:
        self._event.set()
        with self._lock:
            proc = self._proc
        if proc is not None and proc.poll() is None:
            kill_process_tree(proc)

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled():
            raise OperationCancelledError()

    def register_process(self, proc: subprocess.Popen) -> None:
        with self._lock:
            self._proc = proc
        if self.is_cancelled() and proc.poll() is None:
            kill_process_tree(proc)

    def clear_process(self) -> None:
        with self._lock:
            self._proc = None


class OperationCancelledError(Exception):
    """Операция прервана пользователем."""

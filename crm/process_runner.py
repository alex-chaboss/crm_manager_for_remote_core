"""Subprocess/SSH с отменой и потоковым логом."""

from __future__ import annotations

import logging
import subprocess
import time
from typing import Callable

from crm.operation_cancel import CancelToken, OperationCancelledError, kill_process_tree
from crm.ssh_ops import ssh_argv

logger = logging.getLogger(__name__)
LogFn = Callable[[str, str], None]


def _terminate(proc: subprocess.Popen) -> None:
    kill_process_tree(proc)


def run_local_command(
    argv: list[str],
    *,
    cwd: str | None = None,
    timeout_sec: float | None = None,
    log: LogFn | None = None,
    cancel: CancelToken | None = None,
) -> tuple[bool, str]:
    cancel = cancel or CancelToken()
    cancel.raise_if_cancelled()
    if log:
        log(f"$ {' '.join(argv)}", "info")
    try:
        proc = subprocess.Popen(
            argv,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        cancel.register_process(proc)
        assert proc.stdout is not None
        deadline = time.monotonic() + timeout_sec if timeout_sec else None
        lines: list[str] = []
        try:
            while True:
                cancel.raise_if_cancelled()
                if deadline and time.monotonic() > deadline:
                    _terminate(proc)
                    return False, "timeout"
                line = proc.stdout.readline()
                if line:
                    lines.append(line.rstrip("\n"))
                    if log:
                        log(line.rstrip("\n"), "info")
                elif proc.poll() is not None:
                    break
            rest = proc.stdout.read()
            if rest:
                for ln in rest.splitlines():
                    if log:
                        log(ln, "info")
                    lines.append(ln)
            code = proc.wait()
            out = "\n".join(lines)
            if code != 0:
                return False, out or f"exit {code}"
            return True, out or "OK"
        finally:
            cancel.clear_process()
    except OperationCancelledError:
        if log:
            log("Операция прервана пользователем", "warn")
        raise
    except FileNotFoundError:
        return False, f"Команда не найдена: {argv[0]}"
    except Exception as e:
        logger.exception("run_local_command")
        return False, str(e)


def run_ssh_command(
    ssh_host: str,
    remote_command: str,
    *,
    ssh_port: int | None = None,
    timeout_sec: float = 120,
    log: LogFn | None = None,
    cancel: CancelToken | None = None,
) -> tuple[bool, str]:
    cancel = cancel or CancelToken()
    cancel.raise_if_cancelled()
    argv = ssh_argv(ssh_host, remote_command, ssh_port)
    if log:
        log(f"$ ssh … {remote_command[:120]}", "info")
    try:
        proc = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        cancel.register_process(proc)
        assert proc.stdout is not None
        deadline = time.monotonic() + max(30.0, timeout_sec)
        lines: list[str] = []
        try:
            while True:
                cancel.raise_if_cancelled()
                if time.monotonic() > deadline:
                    _terminate(proc)
                    return False, "SSH timeout"
                line = proc.stdout.readline()
                if line:
                    lines.append(line.rstrip("\n"))
                    if log:
                        log(line.rstrip("\n"), "info")
                elif proc.poll() is not None:
                    break
            code = proc.wait()
            out = "\n".join(lines)
            if code != 0:
                return False, out or f"ssh exit {code}"
            return True, out or "OK"
        finally:
            cancel.clear_process()
    except OperationCancelledError:
        if log:
            log("Операция прервана пользователем", "warn")
        raise
    except FileNotFoundError:
        return False, "ssh не найден в PATH"
    except Exception as e:
        logger.exception("run_ssh_command")
        return False, str(e)


def run_ssh_script_stdin(
    ssh_host: str,
    script_text: str,
    *,
    ssh_port: int | None = None,
    timeout_sec: float = 300,
    log: LogFn | None = None,
    cancel: CancelToken | None = None,
) -> tuple[bool, str]:
    cancel = cancel or CancelToken()
    cancel.raise_if_cancelled()
    argv = ssh_argv(ssh_host, "bash -s", ssh_port)
    if log:
        log("$ ssh … bash -s <<stdin", "info")
    try:
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        assert proc.stdin is not None
        assert proc.stdout is not None
        proc.stdin.write(script_text)
        proc.stdin.close()
        cancel.register_process(proc)
        deadline = time.monotonic() + max(60.0, timeout_sec)
        lines: list[str] = []
        try:
            while True:
                cancel.raise_if_cancelled()
                if time.monotonic() > deadline:
                    _terminate(proc)
                    return False, "SSH script timeout"
                line = proc.stdout.readline()
                if line:
                    lines.append(line.rstrip("\n"))
                    if log:
                        log(line.rstrip("\n"), "info")
                elif proc.poll() is not None:
                    break
            code = proc.wait()
            out = "\n".join(lines)
            if code != 0:
                return False, out or f"ssh exit {code}"
            return True, out or "OK"
        finally:
            cancel.clear_process()
    except OperationCancelledError:
        if log:
            log("Операция прервана пользователем", "warn")
        raise
    except Exception as e:
        logger.exception("run_ssh_script_stdin")
        return False, str(e)

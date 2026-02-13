import os
import shlex
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import List, Optional


class DaemonControlError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _read_pid(pid_file: str) -> Optional[int]:
    try:
        with open(pid_file, "r", encoding="utf-8") as f:
            raw = f.read().strip()
    except FileNotFoundError:
        return None
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _write_pid(pid_file: str, pid: int) -> None:
    with open(pid_file, "w", encoding="utf-8") as f:
        f.write(str(pid))


def _remove_pid(pid_file: str) -> None:
    try:
        os.remove(pid_file)
    except FileNotFoundError:
        return


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        raise DaemonControlError(
            "permission_denied", "permission denied to query process"
        )
    return not _is_zombie(pid)


def _is_zombie(pid: int) -> bool:
    """
    On Unix, `kill(pid, 0)` returns success even for zombie processes.
    We treat zombies as not running to avoid stale daemon statuses.
    """
    try:
        proc = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return False

    if proc.returncode != 0:
        return False

    stat = proc.stdout.strip().upper()
    return "Z" in stat


@dataclass
class DaemonStatus:
    status: str
    pid: Optional[int]


class DaemonController:
    def __init__(
        self,
        pid_file: str,
        command: List[str],
        stop_timeout_s: float = 1.0,
        start_grace_s: float = 1.0,
        env_overrides: Optional[dict[str, str]] = None,
    ) -> None:
        self.pid_file = pid_file
        self.command = command
        self.stop_timeout_s = stop_timeout_s
        self.start_grace_s = start_grace_s
        self.env_overrides = env_overrides or {}

    @staticmethod
    def command_from_env(default: str) -> List[str]:
        raw = os.environ.get("DAEMON_COMMAND", "").strip()
        if not raw:
            raw = default
        return shlex.split(raw)

    def status(self) -> DaemonStatus:
        pid = _read_pid(self.pid_file)
        if pid is None:
            return DaemonStatus(status="stopped", pid=None)
        if _is_running(pid):
            return DaemonStatus(status="running", pid=pid)
        return DaemonStatus(status="stale", pid=pid)

    def start(self) -> DaemonStatus:
        pid = _read_pid(self.pid_file)
        if pid is not None and _is_running(pid):
            raise DaemonControlError("already_running", "daemon is already running")
        if pid is not None:
            _remove_pid(self.pid_file)

        command = self.command
        # Ensure daemon uses the same interpreter as the API process.
        if command and command[0] in {"python", "python3"}:
            command = [sys.executable, *command[1:]]

        proc_env = os.environ.copy()
        proc_env.update(self.env_overrides)

        try:
            proc = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=None,
                stderr=None,
                start_new_session=True,
                env=proc_env,
            )
        except PermissionError as exc:
            raise DaemonControlError("permission_denied", str(exc))

        # Give the process a short grace window: if it exits during bootstrap,
        # surface an explicit start error instead of a false "running" state.
        deadline = time.time() + self.start_grace_s
        while time.time() < deadline:
            rc = proc.poll()
            if rc is not None:
                raise DaemonControlError(
                    "start_failed", f"daemon exited immediately (exit_code={rc})"
                )
            time.sleep(0.05)

        _write_pid(self.pid_file, proc.pid)
        return DaemonStatus(status="running", pid=proc.pid)

    def stop(self) -> DaemonStatus:
        pid = _read_pid(self.pid_file)
        if pid is None:
            raise DaemonControlError("already_stopped", "daemon is already stopped")

        if not _is_running(pid):
            _remove_pid(self.pid_file)
            raise DaemonControlError("process_not_found", "daemon process not found")

        try:
            os.kill(pid, signal.SIGTERM)
        except PermissionError as exc:
            raise DaemonControlError("permission_denied", str(exc))

        deadline = time.time() + self.stop_timeout_s
        while time.time() < deadline:
            if not _is_running(pid):
                _remove_pid(self.pid_file)
                return DaemonStatus(status="stopped", pid=None)
            time.sleep(0.05)

        try:
            os.kill(pid, signal.SIGKILL)
        except PermissionError as exc:
            raise DaemonControlError("permission_denied", str(exc))

        _remove_pid(self.pid_file)
        return DaemonStatus(status="stopped", pid=None)

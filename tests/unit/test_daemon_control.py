import os
import subprocess
import sys
import time
import pytest

from tradebot.daemon.control import DaemonControlError, DaemonController


def test_start_stop_status(tmp_path):
    pid_file = tmp_path / "daemon.pid"
    cmd = [sys.executable, "-c", "import time; time.sleep(60)"]
    ctrl = DaemonController(str(pid_file), cmd, stop_timeout_s=0.2, start_grace_s=0.05)

    st = ctrl.status()
    assert st.status == "stopped"
    assert st.pid is None

    st = ctrl.start()
    assert st.status == "running"
    assert st.pid is not None

    st = ctrl.status()
    assert st.status == "running"
    assert st.pid is not None

    st = ctrl.stop()
    assert st.status == "stopped"
    assert st.pid is None

    assert not os.path.exists(pid_file)


def test_already_running(tmp_path):
    pid_file = tmp_path / "daemon.pid"
    cmd = [sys.executable, "-c", "import time; time.sleep(60)"]
    ctrl = DaemonController(str(pid_file), cmd, stop_timeout_s=0.2, start_grace_s=0.05)

    ctrl.start()
    with pytest.raises(DaemonControlError) as exc:
        ctrl.start()
    assert exc.value.code == "already_running"

    ctrl.stop()


def test_already_stopped(tmp_path):
    pid_file = tmp_path / "daemon.pid"
    cmd = [sys.executable, "-c", "import time; time.sleep(1)"]
    ctrl = DaemonController(str(pid_file), cmd, stop_timeout_s=0.2, start_grace_s=0.05)

    with pytest.raises(DaemonControlError) as exc:
        ctrl.stop()
    assert exc.value.code == "already_stopped"


def test_status_stale_pid(tmp_path):
    pid_file = tmp_path / "daemon.pid"
    cmd = [sys.executable, "-c", "import time; time.sleep(1)"]
    ctrl = DaemonController(str(pid_file), cmd, stop_timeout_s=0.2, start_grace_s=0.05)

    proc = subprocess.Popen([sys.executable, "-c", "print('x')"])
    proc.wait(timeout=5)

    pid_file.write_text(str(proc.pid), encoding="utf-8")
    st = ctrl.status()
    assert st.status == "stale"
    assert st.pid == proc.pid


def test_start_injects_env_overrides(tmp_path):
    pid_file = tmp_path / "daemon.pid"
    env_echo_file = tmp_path / "env.txt"
    cmd = [
        "python",
        "-c",
        (
            "import os, pathlib, time;"
            "pathlib.Path(os.environ['ENV_ECHO_FILE']).write_text("
            "os.environ.get('DATABASE_URL', ''), encoding='utf-8');"
            "time.sleep(60)"
        ),
    ]
    ctrl = DaemonController(
        str(pid_file),
        cmd,
        stop_timeout_s=0.2,
        start_grace_s=0.05,
        env_overrides={
            "ENV_ECHO_FILE": str(env_echo_file),
            "DATABASE_URL": "postgresql://user:pass@localhost:5432/tradebot",
        },
    )

    ctrl.start()

    deadline = time.time() + 2
    while time.time() < deadline and not env_echo_file.exists():
        time.sleep(0.05)

    assert env_echo_file.exists()
    assert (
        env_echo_file.read_text(encoding="utf-8")
        == "postgresql://user:pass@localhost:5432/tradebot"
    )

    ctrl.stop()


def test_start_fails_if_process_exits_immediately(tmp_path):
    pid_file = tmp_path / "daemon.pid"
    ctrl = DaemonController(
        str(pid_file),
        [sys.executable, "-c", "import sys; sys.exit(3)"],
        stop_timeout_s=0.2,
        start_grace_s=0.5,
    )

    with pytest.raises(DaemonControlError) as exc:
        ctrl.start()

    assert exc.value.code == "start_failed"
    assert not pid_file.exists()

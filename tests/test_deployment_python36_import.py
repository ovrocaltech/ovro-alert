"""Scheduling helpers must import on Python 3.6 with PYTHONPATH (deployment path)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LWA_SRC = ROOT.parent / "lwa-fasttransients" / "src"
SMOKE = ROOT / "scripts" / "smoke_alert_client_scheduling.py"


@pytest.fixture
def lwa_src_path():
    if not LWA_SRC.is_dir():
        pytest.skip(f"lwa-fasttransients src not present: {LWA_SRC}")
    return LWA_SRC


def test_lwa_src_has_slurm_schedule_module(lwa_src_path):
    assert (lwa_src_path / "frb_search_pipeline" / "slurm_schedule.py").is_file()


def test_smoke_scheduling_on_current_python(lwa_src_path):
    env = os.environ.copy()
    env["LWA_FT_SRC"] = str(lwa_src_path)
    env["PYTHONPATH"] = str(lwa_src_path)
    proc = subprocess.run(
        [sys.executable, str(SMOKE)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


@pytest.mark.skipif(not shutil.which("python3.6"), reason="python3.6 not on PATH")
def test_smoke_scheduling_on_python_36(lwa_src_path):
    py36 = shutil.which("python3.6")
    env = os.environ.copy()
    env["LWA_FT_SRC"] = str(lwa_src_path)
    env["PYTHONPATH"] = str(lwa_src_path)
    proc = subprocess.run(
        [py36, str(SMOKE)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "smoke_alert_client_scheduling: OK" in proc.stdout


def test_alert_client_env_sh_exports_pythonpath():
    env_sh = ROOT / "scripts" / "alert_client_env.sh"
    assert env_sh.is_file()
    text = env_sh.read_text(encoding="utf-8")
    assert "LWA_FT_SRC" in text
    assert "PYTHONPATH" in text

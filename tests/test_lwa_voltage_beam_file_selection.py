"""Mirror voltage beam file mtime window + selection in the Slurm job (manual / no filename=).

The Slurm script `slurm/voltage_beam_pipeline.job` picks the newest regular file under
`VOLTAGE_BEAM_SEARCH_DIR` whose mtime T satisfies start_sec <= T <= end_sec, with
end_sec from VOLTAGE_BEAM_WINDOW_END_EPOCH and start_sec = end_sec - lookback_min*60.
Alert-driven scheduling exports that window at sbatch time (see lwa_alert_client).

These helpers duplicate the mtime-window logic in Python so we can regression-test timing without Slurm.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from ovro_alert.voltage_beam_selection import schedule_voltage_beam_window


def pick_newest_voltage_file(
    files: list[tuple[float, str]],
    start_sec: float,
    end_sec: float,
) -> str | None:
    """Match voltage_beam_pipeline.job: awk filter + sort by mtime descending + head -1."""
    in_window = [(t, p) for t, p in files if start_sec <= t <= end_sec]
    if not in_window:
        return None
    in_window.sort(key=lambda x: x[0], reverse=True)
    return in_window[0][1]


def test_schedule_window_matches_sbatch_window_math():
    """Regression: window end / lookback numbers used in mtime-window examples."""
    fixed_t = 1_700_000_000
    end, lb, start = schedule_voltage_beam_window(fixed_t, 300.0)
    assert end == fixed_t + 300 + 180
    assert lb == 11
    assert start == end - lb * 60


@pytest.mark.parametrize(
    "file_mtime,expect_path",
    [
        # Observation mid-span and at nominal end (integer second boundary).
        (1_700_000_000 + 100, "a.raw"),
        (1_700_000_000 + 300 + 180, "a.raw"),
        (1_700_000_000 - 120, "a.raw"),  # within lookback before schedule
    ],
)
def test_typical_file_mtimes_inside_window(file_mtime, expect_path):
    t0 = 1_700_000_000
    end, lb, start = schedule_voltage_beam_window(t0, 300.0)
    got = pick_newest_voltage_file([(file_mtime, expect_path)], start, end)
    assert got == expect_path


def test_file_one_second_after_window_end_misses():
    """If the last chunk lands after WINDOW_END_EPOCH, Slurm finds nothing."""
    t0 = 1_700_000_000
    end, _, start = schedule_voltage_beam_window(t0, 300.0)
    late = float(end) + 1.0
    assert pick_newest_voltage_file([(late, "late.raw")], start, end) is None


def test_file_before_window_start_misses():
    t0 = 1_700_000_000
    end, _, start = schedule_voltage_beam_window(t0, 300.0)
    early = float(start) - 0.5
    assert pick_newest_voltage_file([(early, "early.raw")], start, end) is None


def test_newest_among_several_candidates():
    t0 = 1_700_000_000
    end, _, start = schedule_voltage_beam_window(t0, 300.0)
    files = [
        (t0 + 50.0, "old.raw"),
        (t0 + 200.0, "newer.raw"),
        (t0 + 150.0, "mid.raw"),
    ]
    assert pick_newest_voltage_file(files, start, end) == "newer.raw"


def test_fractional_mtime_past_integer_end_is_excluded():
    """awk compares float %T@ to integer end_sec; mtime > end_sec excludes file."""
    end = 1_700_000_480
    start = end - 600
    # Same calendar second as end but numerically above int end — excluded.
    assert pick_newest_voltage_file([(end + 0.001, "edge.raw")], start, end) is None
    assert pick_newest_voltage_file([(float(end), "ok.raw")], start, end) == "ok.raw"


def test_long_dm_derived_duration_expands_lookback():
    """Larger duration_sec widens lookback minutes (same formula as client)."""
    t0 = 1_700_000_000
    d = 3600.0
    end, lb, start = schedule_voltage_beam_window(t0, d)
    assert lb == int((d + 300) / 60) + 1 == 66
    # File written near start of hour-long obs still inside window
    ftime = t0 + 30.0
    assert pick_newest_voltage_file([(ftime, "long.raw")], start, end) == "long.raw"


def test_previous_observation_before_window_is_excluded():
    """Regression: file from an earlier alert must not win when a newer file is in-window."""
    t0 = 1_700_000_000
    end, _, start = schedule_voltage_beam_window(t0, 300.0)
    prev_mtime = float(start) - 3600.0
    curr_mtime = t0 + 250.0
    files = [(prev_mtime, "previous.raw"), (curr_mtime, "current.raw")]
    assert pick_newest_voltage_file(files, start, end) == "current.raw"


@pytest.mark.skipif(not shutil.which("bash"), reason="bash not available")
def test_bash_find_awk_pipeline_matches_python_mock(tmp_path: Path):
    """End-to-end: real find | awk | sort reproduces pick_newest_voltage_file."""
    d = tmp_path / "beam"
    d.mkdir()
    # Three files; mtimes set via touch -d where supported
    for name, spec in [
        ("a.raw", "2000-01-01 00:00:00"),
        ("b.raw", "2000-01-01 00:05:00"),
        ("c.raw", "2000-01-01 00:10:00"),
    ]:
        p = d / name
        p.write_text("x")
        subprocess.run(
            ["touch", "-d", spec, str(p)],
            check=True,
        )

    end_sec = int(
        subprocess.run(
            ["date", "-u", "-d", "2000-01-01 00:12:00", "+%s"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )
    start_sec = end_sec - 15 * 60
    # Expected: c.raw is newest in [start, end]
    cmd = f"""
set -euo pipefail
cd '{d}'
find . -maxdepth 1 -type f -name '*.raw' -printf '%T@\\t%p\\n' \\
  | awk -v s={start_sec} -v e={end_sec} -F '\\t' '$1>=s && $1<=e {{print}}' \\
  | sort -t $'\\t' -k1,1nr | head -1
"""
    out = subprocess.run(
        ["bash", "-c", cmd],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert out, f"no selection: {out!r}"
    ts_str, rel_path = out.split("\t", 1)
    assert rel_path.endswith("c.raw")

    # Build float mtimes like find prints
    files = []
    for name in ("a.raw", "b.raw", "c.raw"):
        st = (d / name).stat()
        files.append((st.st_mtime, str(d / name)))
    py_pick = pick_newest_voltage_file(files, start_sec, end_sec)
    assert py_pick.endswith("c.raw")

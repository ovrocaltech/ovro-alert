"""Voltage beam raw-file selection for delayed Slurm pipeline jobs.

Alert-driven scheduling must not pin ``filename=`` at sbatch time: the newest file in
the beam directory is usually the *previous* observation because the new recording has
not started yet. Instead, export an mtime window anchored to submit time + observation
duration; the job picks the newest file in that window when it starts (see
``slurm/voltage_beam_pipeline.job``).
"""
import re
import time
from pathlib import Path
from typing import Optional, Tuple

DEFAULT_VOLTAGE_BEAM_SEARCH_DIR = "/lustre/ubuntu/beam01"


def schedule_voltage_beam_window(
    schedule_unix: float,
    duration_sec: float,
    *,
    slack_s: int = 180,
    margin_s: int = 300,
) -> Tuple[int, int, int]:
    """Compute mtime window for the voltage file produced by this observation.

    Returns ``(window_end_epoch, lookback_min, window_start_epoch)`` matching
    ``voltage_beam_pipeline.job`` when ``VOLTAGE_BEAM_WINDOW_END_EPOCH`` is set.

    * ``window_end_epoch``: submit time + duration + slack (file should finish by then)
    * ``lookback_min``: wide enough to include the full recording span
    """
    end_sec = int(schedule_unix) + int(duration_sec) + int(slack_s)
    lookback_min = int((duration_sec + margin_s) / 60) + 1
    start_sec = end_sec - lookback_min * 60
    return end_sec, lookback_min, start_sec


def voltage_beam_search_dir() -> Path:
    """Beam directory from ``VOLTAGE_BEAM_SEARCH_DIR`` or the deployment default."""
    import os

    return Path(os.environ.get("VOLTAGE_BEAM_SEARCH_DIR", DEFAULT_VOLTAGE_BEAM_SEARCH_DIR))


def sbatch_voltage_beam_exports(
    dm: float,
    duration_sec: float,
    *,
    schedule_unix=None,  # type: Optional[float]
    explicit_time_sec=None,  # type: Optional[float]
) -> str:
    """Build the ``--export=`` body for ``voltage_beam_pipeline.job`` (without ``ALL,`` prefix)."""
    if schedule_unix is None:
        schedule_unix = time.time()
    end_sec, lookback_min, _ = schedule_voltage_beam_window(schedule_unix, duration_sec)
    search = voltage_beam_search_dir()
    parts = [
        f"dm={float(dm)}",
        f"VOLTAGE_BEAM_SEARCH_DIR={search.resolve()}",
        f"VOLTAGE_BEAM_WINDOW_END_EPOCH={end_sec}",
        f"VOLTAGE_BEAM_LOOKBACK_MIN={lookback_min}",
    ]
    if explicit_time_sec is not None:
        parts.append(f"time={float(explicit_time_sec)}")
    return ",".join(parts)


_PIPELINE_ENV_RE = re.compile(
    r"^Pipeline env:.*\bdm=(?P<dm>[^\s]+).*\btime=(?P<time>[^\s]+)",
)
_PIPELINE_PARAMS_RE = re.compile(
    r"^Pipeline parameters: dm=(?P<dm>[^\s]+) duration_sec=(?P<duration>[^\s]+)",
)


def parse_voltage_beam_slurm_stdout(content):
    # type: (str) -> Tuple[float, float]
    """Extract ``(dm, duration_sec)`` from ``voltage_beam_pipeline.job`` stdout.

    Prefers ``Pipeline parameters: ... duration_sec=`` (the value passed to
    ``run_pipeline.py --duration``). Falls back to ``time=`` on the
    ``Pipeline env:`` line when duration was exported explicitly.
    """
    dm = None  # type: Optional[float]
    duration_sec = None  # type: Optional[float]
    env_time = None  # type: Optional[float]

    for line in content.splitlines():
        m_env = _PIPELINE_ENV_RE.match(line)
        if m_env:
            dm = float(m_env.group("dm"))
            raw_time = m_env.group("time")
            if raw_time != "<derive" and not raw_time.startswith("<"):
                env_time = float(raw_time)
            continue
        m_params = _PIPELINE_PARAMS_RE.match(line)
        if m_params:
            dm = float(m_params.group("dm"))
            duration_sec = float(m_params.group("duration"))
            break

    if dm is None:
        raise ValueError(
            "Could not parse dm from Slurm stdout "
            "(expected 'Pipeline env:' or 'Pipeline parameters:' lines)"
        )
    if duration_sec is None:
        if env_time is not None:
            duration_sec = env_time
        else:
            raise ValueError(
                "Could not parse duration from Slurm stdout "
                "(expected 'Pipeline parameters: ... duration_sec=' or explicit time=)"
            )
    return dm, duration_sec

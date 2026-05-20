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


def lookback_minutes_for_duration(duration_sec, margin_s=300):
    # type: (float, int) -> int
    """Lookback width matching ``schedule_voltage_beam_window``."""
    return int((float(duration_sec) + margin_s) / 60) + 1


def sbatch_voltage_beam_exports(
    dm,
    duration_sec,
    schedule_unix=None,  # type: Optional[float]
    explicit_time_sec=None,  # type: Optional[float]
    window_end_epoch=None,  # type: Optional[int]
    lookback_min=None,  # type: Optional[int]
    filename=None,  # type: Optional[str]
    search_dir=None,  # type: Optional[str]
):
    # type: (float, float, ...) -> str
    """Build the ``--export=`` body for ``voltage_beam_pipeline.job`` (without ``ALL,`` prefix).

    When ``filename`` is set, the job uses that path and does not auto-pick by mtime.
    Otherwise ``window_end_epoch`` / ``lookback_min`` control the pick window; if
    ``window_end_epoch`` is omitted, the window is anchored to ``schedule_unix`` (default: now).
    """
    if search_dir:
        search = Path(search_dir)
    else:
        search = voltage_beam_search_dir()
    parts = [
        "dm={0}".format(float(dm)),
        "VOLTAGE_BEAM_SEARCH_DIR={0}".format(search.resolve()),
    ]
    if filename:
        parts.append("filename={0}".format(filename))
    else:
        if window_end_epoch is not None:
            end_sec = int(window_end_epoch)
            lb = (
                int(lookback_min)
                if lookback_min is not None
                else lookback_minutes_for_duration(duration_sec)
            )
        else:
            if schedule_unix is None:
                schedule_unix = time.time()
            end_sec, lb, _ = schedule_voltage_beam_window(schedule_unix, duration_sec)
        parts.append("VOLTAGE_BEAM_WINDOW_END_EPOCH={0}".format(end_sec))
        parts.append("VOLTAGE_BEAM_LOOKBACK_MIN={0}".format(lb))
    if explicit_time_sec is not None:
        parts.append("time={0}".format(float(explicit_time_sec)))
    return ",".join(parts)


_PIPELINE_ENV_DM_RE = re.compile(r"\bdm=(?P<dm>[^\s]+)")
_PIPELINE_ENV_TIME_RE = re.compile(r"\btime=(.+?)\s+filename=")
_PIPELINE_ENV_FILENAME_RE = re.compile(r"\bfilename=(?P<filename>\S+)")
_PIPELINE_ENV_WINDOW_END_RE = re.compile(
    r"VOLTAGE_BEAM_WINDOW_END_EPOCH=(?P<epoch>\d+|<unset>)"
)
_PIPELINE_ENV_LOOKBACK_RE = re.compile(
    r"VOLTAGE_BEAM_LOOKBACK_MIN=(?P<lookback>\d+)"
)
_PIPELINE_ENV_SEARCH_RE = re.compile(r"search_dir=(?P<dir>\S+)")
_PIPELINE_PARAMS_RE = re.compile(
    r"^Pipeline parameters: dm=(?P<dm>[^\s]+) duration_sec=(?P<duration>[^\s]+)"
)
_RESOLVED_FILE_RE = re.compile(
    r"^Resolved voltage file .*?: (?P<path>.+?) \(mtime unix=(?P<mtime>\d+)"
)


def _parse_pipeline_env_line(line):
    # type: (str) -> dict
    if not line.startswith("Pipeline env:"):
        return {}
    out = {}
    m = _PIPELINE_ENV_DM_RE.search(line)
    if m:
        out["dm"] = float(m.group("dm"))
    m = _PIPELINE_ENV_TIME_RE.search(line)
    if m:
        raw = m.group(1).strip()
        if raw != "<derive from dm>" and not raw.startswith("<"):
            out["env_time"] = float(raw)
    m = _PIPELINE_ENV_FILENAME_RE.search(line)
    if m:
        out["env_filename"] = m.group("filename")
    m = _PIPELINE_ENV_WINDOW_END_RE.search(line)
    if m and m.group("epoch") != "<unset>":
        out["window_end_epoch"] = int(m.group("epoch"))
    m = _PIPELINE_ENV_LOOKBACK_RE.search(line)
    if m:
        out["lookback_min"] = int(m.group("lookback"))
    m = _PIPELINE_ENV_SEARCH_RE.search(line)
    if m:
        out["search_dir"] = m.group("dir")
    return out


def parse_voltage_beam_job_log(content):
    # type: (str) -> dict
    """Parse ``voltage_beam_pipeline.job`` stdout into scheduling metadata.

    Returns a dict with keys ``dm``, ``duration_sec``, and optionally
    ``window_end_epoch``, ``lookback_min``, ``search_dir``, ``env_filename``,
    ``resolved_filename``, ``file_mtime``.
    """
    meta = {}  # type: dict
    duration_sec = None  # type: Optional[float]
    env_time = None  # type: Optional[float]

    for line in content.splitlines():
        meta.update(_parse_pipeline_env_line(line))
        m_params = _PIPELINE_PARAMS_RE.match(line)
        if m_params:
            meta["dm"] = float(m_params.group("dm"))
            duration_sec = float(m_params.group("duration"))
        m_res = _RESOLVED_FILE_RE.match(line)
        if m_res:
            meta["resolved_filename"] = m_res.group("path")
            meta["file_mtime"] = int(m_res.group("mtime"))

    dm = meta.get("dm")
    if dm is None:
        raise ValueError(
            "Could not parse dm from Slurm stdout "
            "(expected 'Pipeline env:' or 'Pipeline parameters:' lines)"
        )
    env_time = meta.pop("env_time", None)
    if duration_sec is None:
        if env_time is not None:
            duration_sec = env_time
        else:
            raise ValueError(
                "Could not parse duration from Slurm stdout "
                "(expected 'Pipeline parameters: ... duration_sec=' or explicit time=)"
            )
    meta["duration_sec"] = duration_sec
    return meta


def parse_voltage_beam_slurm_stdout(content):
    # type: (str) -> Tuple[float, float]
    """Extract ``(dm, duration_sec)`` from ``voltage_beam_pipeline.job`` stdout."""
    meta = parse_voltage_beam_job_log(content)
    return meta["dm"], meta["duration_sec"]


def historical_window_from_job_log(meta, slack_s=180):
    # type: (dict, int) -> Tuple[Optional[int], Optional[int]]
    """Return ``(window_end_epoch, lookback_min)`` for a late resubmit.

    Prefers the exported window from the original job. If the original run used
    ``find -mmin`` (no window end in env), derives the window from the resolved
    file mtime recorded in the log.
    """
    end = meta.get("window_end_epoch")
    lookback = meta.get("lookback_min")
    if end is not None:
        return end, lookback
    mtime = meta.get("file_mtime")
    if mtime is not None:
        duration_sec = meta["duration_sec"]
        return int(mtime) + int(slack_s), lookback_minutes_for_duration(duration_sec)
    return None, lookback


def build_resubmit_export(
    content,
    filename=None,  # type: Optional[str]
    window_end_epoch=None,  # type: Optional[int]
    lookback_min=None,  # type: Optional[int]
    window_now=False,
):
    # type: (str, ...) -> Tuple[float, float, str]
    """Build sbatch export for a resubmit from prior job stdout.

    Default (``window_now=False``): reuse the original job's mtime window so a
    late resubmit still finds the recorded file. Pass ``window_now=True`` to
    anchor the window to the current time (only useful if resubmitting soon).

    ``filename`` pins an explicit voltage file (skips mtime window pick).
    ``window_end_epoch`` / ``lookback_min`` override the parsed window.
    """
    meta = parse_voltage_beam_job_log(content)
    dm = meta["dm"]
    duration_sec = meta["duration_sec"]

    search_dir = meta.get("search_dir")

    if filename:
        export = sbatch_voltage_beam_exports(
            dm,
            duration_sec,
            explicit_time_sec=duration_sec,
            filename=filename,
            search_dir=search_dir,
        )
        return dm, duration_sec, export

    if window_now:
        export = sbatch_voltage_beam_exports(
            dm,
            duration_sec,
            explicit_time_sec=duration_sec,
            schedule_unix=time.time(),
            search_dir=search_dir,
        )
        return dm, duration_sec, export

    if window_end_epoch is None:
        window_end_epoch, parsed_lookback = historical_window_from_job_log(meta)
        if lookback_min is None:
            lookback_min = parsed_lookback
    if window_end_epoch is None:
        raise ValueError(
            "Could not determine mtime window from Slurm stdout "
            "(need VOLTAGE_BEAM_WINDOW_END_EPOCH in Pipeline env: or "
            "Resolved voltage file line). Use --window-end, --filename, or --window-now."
        )

    export = sbatch_voltage_beam_exports(
        dm,
        duration_sec,
        explicit_time_sec=duration_sec,
        window_end_epoch=window_end_epoch,
        lookback_min=lookback_min,
        search_dir=search_dir,
    )
    return dm, duration_sec, export

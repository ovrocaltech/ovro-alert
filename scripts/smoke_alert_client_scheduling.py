#!/usr/bin/env python
"""Import smoke for LWA alert client scheduling on deployment (Python 3.6+).

Expects LWA_FT_SRC on PYTHONPATH (set by alert_client_env.sh or deploy_alert_client.sh).
Does not require pip install -e ovro-alert (pyproject requires Python >=3.9).
"""
from __future__ import print_function

import os
import sys
from pathlib import Path


def _ensure_lwa_src():
    src = os.environ.get("LWA_FT_SRC")
    if not src:
        proj_root = Path(__file__).resolve().parents[2]
        src = str(proj_root / "lwa-fasttransients" / "src")
    src_path = Path(src)
    if not src_path.is_dir():
        print("ERROR: LWA_FT_SRC not found:", src_path, file=sys.stderr)
        return 1
    s = str(src_path)
    if s not in sys.path:
        sys.path.insert(0, s)
    os.environ.setdefault("LWA_FT_SRC", s)
    return 0


def main():
    if _ensure_lwa_src() != 0:
        return 1

    from frb_search_pipeline.slurm_schedule import (  # noqa: F401
        dispersion_delay_s,
        duration_from_dm,
        resolve_voltage_pipeline_begin,
        schedule_voltage_beam_window,
        sbatch_voltage_beam_exports,
    )

    dm = 87.5
    d = duration_from_dm(dm)
    delay = dispersion_delay_s(dm, 1e9, 50) + 10.0
    if abs(d - delay) > 1e-6:
        print("ERROR: duration_from_dm mismatch", d, delay, file=sys.stderr)
        return 1

    end, lookback, start = schedule_voltage_beam_window(1_700_000_000.0, 300.0)
    if lookback < 1 or end <= start:
        print("ERROR: bad mtime window", end, lookback, start, file=sys.stderr)
        return 1

    begin, _ = resolve_voltage_pipeline_begin(1_700_000_000.0, 300.0, now_unix=1_700_000_000.0)
    if not begin.startswith("now+"):
        print("ERROR: unexpected begin", begin, file=sys.stderr)
        return 1

    try:
        from ovro_alert.voltage_beam_selection import submit_voltage_beam_sbatch  # noqa: F401
    except ImportError as exc:
        print(
            "WARN: ovro_alert not importable (ok if only testing slurm_schedule):",
            exc,
            file=sys.stderr,
        )

    print(
        "smoke_alert_client_scheduling: OK python=%s LWA_FT_SRC=%s"
        % (sys.version.split()[0], os.environ.get("LWA_FT_SRC"))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

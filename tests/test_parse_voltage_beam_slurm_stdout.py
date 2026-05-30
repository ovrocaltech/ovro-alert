"""Tests for parsing voltage_beam_pipeline Slurm stdout."""

import pytest

from ovro_alert.voltage_beam_selection import (
    build_resubmit_export,
    historical_window_from_job_log,
    parse_voltage_beam_job_log,
    parse_voltage_beam_slurm_stdout,
)


def test_parse_full_file_time_zero():
    text = """\
Pipeline env: dm=57 time=0 filename=/lustre/ubuntu/beam01/foo.raw VOLTAGE_BEAM_WINDOW_END_EPOCH= VOLTAGE_BEAM_LOOKBACK_MIN=120 search_dir=/lustre/ubuntu/beam01
Pipeline parameters: dm=57 duration_sec=0 (full combined PSRFITS span (time=0))
"""
    dm, dur = parse_voltage_beam_slurm_stdout(text)
    assert dm == 57.0
    assert dur == 0.0


def test_parse_explicit_time_from_env_and_parameters():
    text = """\
Pipeline env: dm=87.3 time=300 filename=<auto> VOLTAGE_BEAM_WINDOW_END_EPOCH=1700000480 VOLTAGE_BEAM_LOOKBACK_MIN=11 search_dir=/lustre/ubuntu/beam01
Pipeline parameters: dm=87.3 duration_sec=300 (from exported time (seconds))
"""
    dm, dur = parse_voltage_beam_slurm_stdout(text)
    assert dm == 87.3
    assert dur == 300.0


def test_parse_dm_derived_duration_from_parameters():
    text = """\
Pipeline env: dm=1008.9138184 time=<derive from dm> filename=<auto> VOLTAGE_BEAM_WINDOW_END_EPOCH=1700005000 VOLTAGE_BEAM_LOOKBACK_MIN=34 search_dir=/lustre/ubuntu/beam01
Pipeline parameters: dm=1008.9138184 duration_sec=1685.407 (from dm (dispersion delay + 10 s; same as lwa_alert_client.delay))
"""
    dm, dur = parse_voltage_beam_slurm_stdout(text)
    assert dm == pytest.approx(1008.9138184)
    assert dur == pytest.approx(1685.407)


def test_parse_job_log_window_and_resolved_file():
    text = """\
Pipeline env: dm=10 time=<derive from dm> filename=<auto> VOLTAGE_BEAM_WINDOW_END_EPOCH=<unset> VOLTAGE_BEAM_LOOKBACK_MIN=120 search_dir=/lustre/ubuntu/beam01
Resolved voltage file (auto): /lustre/ubuntu/beam01/run.raw (mtime unix=1700001000, 2023-11-14T22:30:00Z)
Pipeline parameters: dm=10 duration_sec=600 (from dm ...)
"""
    meta = parse_voltage_beam_job_log(text)
    assert meta.get("window_end_epoch") is None
    assert meta["file_mtime"] == 1700001000
    end, lb = historical_window_from_job_log(meta, slack_s=180)
    assert end == 1700001180
    assert lb == 16


def test_build_resubmit_reuses_original_window():
    text = """\
Pipeline env: dm=87.3 time=300 filename=<auto> VOLTAGE_BEAM_WINDOW_END_EPOCH=1700000480 VOLTAGE_BEAM_LOOKBACK_MIN=11 search_dir=/lustre/ubuntu/beam01
Pipeline parameters: dm=87.3 duration_sec=300 (from exported time (seconds))
"""
    _, _, export = build_resubmit_export(text)
    assert "VOLTAGE_BEAM_WINDOW_END_EPOCH=1700000480" in export
    assert "VOLTAGE_BEAM_LOOKBACK_MIN=11" in export
    assert "time=300" in export
    assert "filename=" not in export


def test_build_resubmit_window_now_uses_no_historical_epoch():
    text = """\
Pipeline env: dm=87.3 time=300 filename=<auto> VOLTAGE_BEAM_WINDOW_END_EPOCH=1700000480 VOLTAGE_BEAM_LOOKBACK_MIN=11 search_dir=/lustre/ubuntu/beam01
Pipeline parameters: dm=87.3 duration_sec=300 (from exported time (seconds))
"""
    _, _, export = build_resubmit_export(text, window_now=True)
    assert "VOLTAGE_BEAM_WINDOW_END_EPOCH=1700000480" not in export
    assert "VOLTAGE_BEAM_WINDOW_END_EPOCH=" in export


def test_build_resubmit_explicit_filename():
    text = """\
Pipeline env: dm=1 time=10 filename=<auto> VOLTAGE_BEAM_WINDOW_END_EPOCH=99 VOLTAGE_BEAM_LOOKBACK_MIN=5 search_dir=/lustre/ubuntu/beam01
Pipeline parameters: dm=1 duration_sec=10 (x)
"""
    _, _, export = build_resubmit_export(
        text, filename="/lustre/ubuntu/beam01/pinned.raw"
    )
    assert "filename=/lustre/ubuntu/beam01/pinned.raw" in export
    assert "VOLTAGE_BEAM_WINDOW_END_EPOCH" not in export


def test_build_resubmit_cli_window_override():
    text = """\
Pipeline env: dm=1 time=10 filename=<auto> VOLTAGE_BEAM_WINDOW_END_EPOCH=99 VOLTAGE_BEAM_LOOKBACK_MIN=5 search_dir=/lustre/ubuntu/beam01
Pipeline parameters: dm=1 duration_sec=10 (x)
"""
    _, _, export = build_resubmit_export(
        text, window_end_epoch=2000000000, lookback_min=60
    )
    assert "VOLTAGE_BEAM_WINDOW_END_EPOCH=2000000000" in export
    assert "VOLTAGE_BEAM_LOOKBACK_MIN=60" in export


def test_parse_falls_back_to_env_time_without_parameters_line():
    text = """\
Pipeline env: dm=50.0 time=120.5 filename=/lustre/ubuntu/beam01/foo.raw VOLTAGE_BEAM_WINDOW_END_EPOCH= VOLTAGE_BEAM_LOOKBACK_MIN=120 search_dir=/lustre/ubuntu/beam01
Step failed before parameters line
"""
    dm, dur = parse_voltage_beam_slurm_stdout(text)
    assert dm == 50.0
    assert dur == 120.5


def test_parse_missing_dm_raises():
    with pytest.raises(ValueError, match="Could not parse dm"):
        parse_voltage_beam_slurm_stdout("no pipeline lines here\n")

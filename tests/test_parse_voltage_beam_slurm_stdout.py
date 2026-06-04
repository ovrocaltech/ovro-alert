"""Tests for parsing voltage_beam_pipeline Slurm stdout."""

import pytest

from ovro_alert.voltage_beam_selection import (
    build_resubmit_export,
    historical_window_from_job_log,
    locate_prior_job_artifacts,
    parse_slurm_job_id_from_stdout_path,
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


def test_parse_default_full_file_when_time_unset():
    text = """\
Pipeline env: dm=1008.9138184 time=<full file> filename=<auto> VOLTAGE_BEAM_WINDOW_END_EPOCH=1700005000 VOLTAGE_BEAM_LOOKBACK_MIN=34 search_dir=/lustre/ubuntu/beam01
Pipeline parameters: dm=1008.9138184 duration_sec=0 (full combined PSRFITS span (default; all time samples))
"""
    dm, dur = parse_voltage_beam_slurm_stdout(text)
    assert dm == pytest.approx(1008.9138184)
    assert dur == 0.0


def test_parse_job_log_window_and_resolved_file():
    text = """\
Pipeline env: dm=10 time=<full file> filename=<auto> VOLTAGE_BEAM_WINDOW_END_EPOCH=<unset> VOLTAGE_BEAM_LOOKBACK_MIN=120 search_dir=/lustre/ubuntu/beam01
Resolved voltage file (auto): /lustre/ubuntu/beam01/run.raw (mtime unix=1700001000, 2023-11-14T22:30:00Z)
Pipeline parameters: dm=10 duration_sec=0 (full combined PSRFITS span (default; all time samples))
"""
    meta = parse_voltage_beam_job_log(text)
    assert meta.get("window_end_epoch") is None
    assert meta["file_mtime"] == 1700001000
    end, lb = historical_window_from_job_log(meta, slack_s=180)
    assert end == 1700001180
    assert lb == 6


def _sample_log(*extra_lines):
    lines = [
        "Pipeline env: dm=87.3 time=<full file> filename=<auto> "
        "VOLTAGE_BEAM_WINDOW_END_EPOCH=1700000480 VOLTAGE_BEAM_LOOKBACK_MIN=11 "
        "search_dir=/lustre/ubuntu/beam01",
        "Pipeline parameters: dm=87.3 duration_sec=0 (full combined PSRFITS span (default; all time samples))",
        "Pipeline target: RA=83.6 Dec=22.0 lo_dm=37.3 hi_dm=137.3 lwa_fasttransients=/home/pipeline/proj/lwa-fasttransients",
    ]
    if extra_lines:
        lines = list(extra_lines)
    return "\n".join(lines) + "\n"


def test_build_resubmit_reuses_original_window():
    text = _sample_log()
    _, _, export, resume_dir = build_resubmit_export(text)
    assert resume_dir is None
    assert "VOLTAGE_BEAM_WINDOW_END_EPOCH=1700000480" in export
    assert "VOLTAGE_BEAM_LOOKBACK_MIN=11" in export
    assert ",time=" not in export and not export.startswith("time=")
    assert "filename=" not in export
    assert "VOLTAGE_BEAM_RA=83.6" in export
    assert "VOLTAGE_BEAM_DEC=22.0" in export


def test_build_resubmit_window_now_uses_no_historical_epoch():
    text = _sample_log()
    _, _, export, _ = build_resubmit_export(text, window_now=True)
    assert "VOLTAGE_BEAM_WINDOW_END_EPOCH=1700000480" not in export
    assert "VOLTAGE_BEAM_WINDOW_END_EPOCH=" in export


def test_build_resubmit_explicit_filename():
    text = _sample_log(
        "Pipeline env: dm=1 time=10 filename=<auto> VOLTAGE_BEAM_WINDOW_END_EPOCH=99 "
        "VOLTAGE_BEAM_LOOKBACK_MIN=5 search_dir=/lustre/ubuntu/beam01",
        "Pipeline parameters: dm=1 duration_sec=10 (x)",
        "Pipeline target: RA=10.0 Dec=20.0 lo_dm=0.0 hi_dm=51.0 lwa_fasttransients=/home/pipeline/proj/lwa-fasttransients",
    )
    _, _, export, _ = build_resubmit_export(
        text, filename="/lustre/ubuntu/beam01/pinned.raw"
    )
    assert "filename=/lustre/ubuntu/beam01/pinned.raw" in export
    assert "VOLTAGE_BEAM_WINDOW_END_EPOCH" not in export


def test_build_resubmit_cli_window_override():
    text = _sample_log(
        "Pipeline env: dm=1 time=10 filename=<auto> VOLTAGE_BEAM_WINDOW_END_EPOCH=99 "
        "VOLTAGE_BEAM_LOOKBACK_MIN=5 search_dir=/lustre/ubuntu/beam01",
        "Pipeline parameters: dm=1 duration_sec=10 (x)",
        "Pipeline target: RA=1.0 Dec=2.0 lo_dm=0.0 hi_dm=51.0 lwa_fasttransients=/home/pipeline/proj/lwa-fasttransients",
    )
    _, _, export, _ = build_resubmit_export(
        text, window_end_epoch=2000000000, lookback_min=60
    )
    assert "VOLTAGE_BEAM_WINDOW_END_EPOCH=2000000000" in export
    assert "VOLTAGE_BEAM_LOOKBACK_MIN=60" in export


def test_parse_job_log_ra_dec_from_pipeline_env():
    text = """\
Pipeline env: dm=57.1 time=0 filename=/lustre/ubuntu/beam01/foo.raw VOLTAGE_BEAM_RA=83.6324 VOLTAGE_BEAM_DEC=22.0174 VOLTAGE_BEAM_WINDOW_END_EPOCH= VOLTAGE_BEAM_LOOKBACK_MIN=120 search_dir=/lustre/ubuntu/beam01
Pipeline parameters: dm=57.1 duration_sec=0 (full combined PSRFITS span (time=0))
"""
    meta = parse_voltage_beam_job_log(text)
    assert meta["ra"] == pytest.approx(83.6324)
    assert meta["dec"] == pytest.approx(22.0174)


def test_parse_job_log_target_ra_dec():
    text = """\
Pipeline env: dm=57 time=0 filename=/lustre/ubuntu/beam01/foo.raw VOLTAGE_BEAM_WINDOW_END_EPOCH= VOLTAGE_BEAM_LOOKBACK_MIN=120 search_dir=/lustre/ubuntu/beam01
Pipeline parameters: dm=57 duration_sec=0 (full combined PSRFITS span (time=0))
Pipeline target: RA=180.0 Dec=-30.5 lo_dm=7.0 hi_dm=107.0 lwa_fasttransients=/home/pipeline/proj/lwa-fasttransients
"""
    meta = parse_voltage_beam_job_log(text)
    assert meta["ra"] == 180.0
    assert meta["dec"] == pytest.approx(-30.5)


def test_build_resubmit_missing_ra_dec_raises():
    text = """\
Pipeline env: dm=87.3 time=300 filename=<auto> VOLTAGE_BEAM_WINDOW_END_EPOCH=1700000480 VOLTAGE_BEAM_LOOKBACK_MIN=11 search_dir=/lustre/ubuntu/beam01
Pipeline parameters: dm=87.3 duration_sec=300 (from exported time (seconds))
"""
    with pytest.raises(ValueError, match="VOLTAGE_BEAM_RA/DEC"):
        build_resubmit_export(text)


def test_build_resubmit_env_ra_dec_override():
    text = """\
Pipeline env: dm=87.3 time=300 filename=<auto> VOLTAGE_BEAM_WINDOW_END_EPOCH=1700000480 VOLTAGE_BEAM_LOOKBACK_MIN=11 search_dir=/lustre/ubuntu/beam01
Pipeline parameters: dm=87.3 duration_sec=300 (from exported time (seconds))
"""
    _, _, export, _ = build_resubmit_export(text, ra=12.5, dec=-3.25)
    assert "VOLTAGE_BEAM_RA=12.5" in export
    assert "VOLTAGE_BEAM_DEC=-3.25" in export


def test_parse_slurm_job_id_from_stdout_path():
    assert parse_slurm_job_id_from_stdout_path("/home/pipeline/slurm/voltage_beam_pipeline-4242.out") == 4242
    assert parse_slurm_job_id_from_stdout_path("job.out") is None


def test_locate_prior_job_artifacts_from_moved_products(tmp_path):
    product = tmp_path / "voltage_beam_99"
    product.mkdir()
    (product / "checkpoint.json").write_text('{"conversion_done": true}')
    text = _sample_log("Moved products to {0}".format(product))
    found = locate_prior_job_artifacts(text, stdout_path="voltage_beam_pipeline-99.out")
    assert found == str(product.resolve())


def test_locate_prior_job_artifacts_from_fast_workdir(tmp_path, monkeypatch):
    fast_root = tmp_path / "fast"
    work = fast_root / "voltage_beam_55"
    work.mkdir(parents=True)
    (work / "checkpoint.json").write_text('{"conversion_done": true}')
    monkeypatch.setenv("VOLTAGE_BEAM_FAST_ROOT", str(fast_root))
    text = _sample_log()
    found = locate_prior_job_artifacts(
        text,
        stdout_path=str(tmp_path / "voltage_beam_pipeline-55.out"),
        product_root=str(tmp_path / "lustre"),
    )
    assert found == str(work.resolve())


def test_build_resubmit_exports_resume_from(tmp_path):
    product = tmp_path / "voltage_beam_12"
    product.mkdir()
    (product / "checkpoint.json").write_text(
        '{"conversion_done": true, "output_filenames": {"fil_file_name": "x.fil"}}'
    )
    text = _sample_log() + "Moved products to {0}\n".format(product)
    _, _, export, resume_dir = build_resubmit_export(
        text,
        stdout_path=str(tmp_path / "voltage_beam_pipeline-12.out"),
    )
    assert resume_dir == str(product.resolve())
    assert "VOLTAGE_BEAM_RESUME_FROM={0}".format(product.resolve()) in export


def test_build_resubmit_no_resume_skips_artifacts(tmp_path):
    product = tmp_path / "voltage_beam_12"
    product.mkdir()
    (product / "checkpoint.json").write_text('{"conversion_done": true}')
    text = _sample_log() + "Moved products to {0}\n".format(product)
    _, _, export, resume_dir = build_resubmit_export(
        text,
        stdout_path=str(tmp_path / "voltage_beam_pipeline-12.out"),
        no_resume=True,
    )
    assert resume_dir is None
    assert "VOLTAGE_BEAM_RESUME_FROM=" not in export


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


def test_parse_lwa_voltage_beam_run_log_format():
    """Stdout from lwa-voltage-beam run (Phase 3+) without legacy lo_dm/hi_dm line."""
    text = """\
Pipeline env: dm=87.3 time=<full file> filename=<auto> VOLTAGE_BEAM_RA=83.6 VOLTAGE_BEAM_DEC=22.0 VOLTAGE_BEAM_WINDOW_END_EPOCH=1700000480 VOLTAGE_BEAM_LOOKBACK_MIN=11 search_dir=/lustre/ubuntu/beam01
Voltage file search: assumed window end unix=1700000480 (2023-11-14T22:08:00Z), start unix=1700003820 (2023-11-14T21:17:00Z), lookback 11 min
Resolved voltage file (auto, window end epoch 1700000480): /lustre/ubuntu/beam01/foo.raw (mtime unix=1700000100, 2023-11-14T22:01:40Z)
Pipeline parameters: dm=87.3 duration_sec=0 (full combined PSRFITS span (default; all time samples))
Pipeline target: RA=83.6 Dec=22.0 lwa_fasttransients=/home/pipeline/proj/lwa-fasttransients
lwa-voltage-beam run: /opt/devel/pipeline/envs/fasttransients/bin/python .../run_pipeline.py --voltage ...
"""
    meta = parse_voltage_beam_job_log(text)
    assert meta["dm"] == 87.3
    assert meta["duration_sec"] == 0.0
    assert meta["ra"] == pytest.approx(83.6)
    assert meta["dec"] == pytest.approx(22.0)
    assert meta["resolved_filename"].endswith("foo.raw")
    _, _, export, _ = build_resubmit_export(text)
    assert "VOLTAGE_BEAM_WINDOW_END_EPOCH=1700000480" in export
    assert "VOLTAGE_BEAM_RA=83.6" in export


def test_build_resubmit_with_start_from_step():
    text = _sample_log()
    _, _, export, _ = build_resubmit_export(text, start_from="04")
    assert "VOLTAGE_BEAM_START_FROM=04" in export

"""Tests for delayed Slurm scheduling from submit_voltagebeam."""

import os

import pytest
from subprocess import CompletedProcess
from unittest.mock import MagicMock, patch


def _client_and_fake_job(tmp_path):
    """Build LWAAlertClient without controller deps when imports succeed."""
    try:
        import ovro_alert.lwa_alert_client as lac
    except ImportError as e:
        pytest.skip(f"LWA client dependencies unavailable: {e}")

    fake_job = tmp_path / "voltage_beam_pipeline.job"
    fake_job.write_text("#!/bin/bash\necho ok\n")

    with patch.object(lac.LWAAlertClient, "__init__", lambda self, con: None):
        client = lac.LWAAlertClient.__new__(lac.LWAAlertClient)
    return client, fake_job, lac


def test_schedule_voltage_beam_pipeline_exports_mtime_window_not_filename(
    tmp_path, monkeypatch
):
    client, fake_job, lac = _client_and_fake_job(tmp_path)
    monkeypatch.setenv("OVRO_ALERT_VOLTAGE_BEAM_JOB", str(fake_job))
    monkeypatch.setenv("OVRO_ALERT_VOLTAGE_PIPELINE_NODELIST", "lwacalim02")

    beam_dir = tmp_path / "beam01"
    beam_dir.mkdir()
    older = beam_dir / "old.raw"
    newer = beam_dir / "new.raw"
    older.write_bytes(b"a")
    newer.write_bytes(b"b")
    os.utime(older, (100, 1000))
    os.utime(newer, (100, 2000))
    monkeypatch.setenv("VOLTAGE_BEAM_SEARCH_DIR", str(beam_dir))

    fixed_t = 1_700_000_000.0
    mock_sbatch = MagicMock(
        return_value=CompletedProcess(
            args=[],
            returncode=0,
            stdout="Submitted batch job 4242\n",
            stderr="",
        )
    )
    with patch.object(lac.time, "time", return_value=fixed_t):
        with patch.object(lac, "submit_voltage_beam_sbatch", mock_sbatch):
            client._schedule_voltage_beam_pipeline({"dm": 87.5, "position": "10,20"}, 300.0)

    mock_sbatch.assert_called_once()
    export_body, kwargs = mock_sbatch.call_args[0][0], mock_sbatch.call_args[1]
    assert "dm=87.5" in export_body
    assert ",time=" not in export_body and not export_body.startswith("time=")
    assert "filename=" not in export_body
    end, lb, _ = lac.schedule_voltage_beam_window(fixed_t, 300.0)
    assert f"VOLTAGE_BEAM_WINDOW_END_EPOCH={end}" in export_body
    assert f"VOLTAGE_BEAM_LOOKBACK_MIN={lb}" in export_body
    assert f"VOLTAGE_BEAM_SEARCH_DIR={beam_dir.resolve()}" in export_body
    assert "VOLTAGE_BEAM_RA=10.0" in export_body
    assert "VOLTAGE_BEAM_DEC=20.0" in export_body
    assert kwargs["job_script"] == fake_job
    assert kwargs["begin"] == "now+900"
    assert kwargs["nodelist"] == "lwacalim02"


def test_schedule_voltage_beam_pipeline_exports_time_when_alert_has_explicit_duration(
    tmp_path, monkeypatch
):
    client, fake_job, lac = _client_and_fake_job(tmp_path)
    monkeypatch.setenv("OVRO_ALERT_VOLTAGE_BEAM_JOB", str(fake_job))
    monkeypatch.setenv("OVRO_ALERT_VOLTAGE_PIPELINE_NODELIST", "lwacalim02")

    beam_dir = tmp_path / "beam01"
    beam_dir.mkdir()
    only = beam_dir / "only.raw"
    only.write_bytes(b"x")
    monkeypatch.setenv("VOLTAGE_BEAM_SEARCH_DIR", str(beam_dir))

    mock_sbatch = MagicMock(
        return_value=CompletedProcess(
            args=[],
            returncode=0,
            stdout="Submitted batch job 4242\n",
            stderr="",
        )
    )
    with patch.object(lac, "submit_voltage_beam_sbatch", mock_sbatch):
        client._schedule_voltage_beam_pipeline(
            {"dm": 87.5, "position": "10,20", "duration": 450.0}, 450.0
        )

    mock_sbatch.assert_called_once()
    export_body = mock_sbatch.call_args[0][0]
    assert "dm=87.5" in export_body
    assert "time=450.0" in export_body
    assert "filename=" not in export_body
    assert "VOLTAGE_BEAM_WINDOW_END_EPOCH=" in export_body


def test_schedule_skips_when_search_dir_has_no_files(tmp_path, monkeypatch, caplog):
    """Scheduling no longer requires files at sbatch time (pick happens at job start)."""
    import logging

    client, fake_job, lac = _client_and_fake_job(tmp_path)
    monkeypatch.setenv("OVRO_ALERT_VOLTAGE_BEAM_JOB", str(fake_job))
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("VOLTAGE_BEAM_SEARCH_DIR", str(empty))

    mock_sbatch = MagicMock(
        return_value=CompletedProcess(
            args=[],
            returncode=0,
            stdout="Submitted batch job 4242\n",
            stderr="",
        )
    )
    with patch.object(lac, "submit_voltage_beam_sbatch", mock_sbatch):
        with caplog.at_level(logging.WARNING):
            client._schedule_voltage_beam_pipeline({"dm": 87.5, "position": "0,0"}, 300.0)

    mock_sbatch.assert_called_once()
    assert "no regular files" not in caplog.text


def test_schedule_skips_without_dm(tmp_path, monkeypatch, caplog):
    import logging

    client, fake_job, lac = _client_and_fake_job(tmp_path)
    monkeypatch.setenv("OVRO_ALERT_VOLTAGE_BEAM_JOB", str(fake_job))

    mock_sbatch = MagicMock()
    with patch.object(lac, "submit_voltage_beam_sbatch", mock_sbatch):
        with caplog.at_level(logging.WARNING):
            client._schedule_voltage_beam_pipeline({"duration": 100.0, "position": "0,0"}, 100.0)

    mock_sbatch.assert_not_called()
    assert "dm missing" in caplog.text


def test_schedule_honors_begin_delay_override(tmp_path, monkeypatch):
    client, fake_job, lac = _client_and_fake_job(tmp_path)
    monkeypatch.setenv("OVRO_ALERT_VOLTAGE_BEAM_JOB", str(fake_job))
    monkeypatch.setenv("OVRO_ALERT_VOLTAGE_PIPELINE_BEGIN_DELAY", "now+2hours")
    beam_dir = tmp_path / "beam01"
    beam_dir.mkdir()
    monkeypatch.setenv("VOLTAGE_BEAM_SEARCH_DIR", str(beam_dir))

    mock_sbatch = MagicMock(
        return_value=CompletedProcess(
            args=[],
            returncode=0,
            stdout="Submitted batch job 99\n",
            stderr="",
        )
    )
    with patch.object(lac, "submit_voltage_beam_sbatch", mock_sbatch):
        client._schedule_voltage_beam_pipeline({"dm": 87.5, "position": "10,20"}, 300.0)

    assert mock_sbatch.call_args[1]["begin"] == "now+2hours"


def test_schedule_logs_structured_sbatch_record(tmp_path, monkeypatch, caplog):
    import logging

    client, fake_job, lac = _client_and_fake_job(tmp_path)
    monkeypatch.setenv("OVRO_ALERT_VOLTAGE_BEAM_JOB", str(fake_job))
    monkeypatch.delenv("OVRO_ALERT_VOLTAGE_PIPELINE_BEGIN_DELAY", raising=False)
    beam_dir = tmp_path / "beam01"
    beam_dir.mkdir()
    monkeypatch.setenv("VOLTAGE_BEAM_SEARCH_DIR", str(beam_dir))

    fixed_t = 1_700_000_000.0
    mock_sbatch = MagicMock(
        return_value=CompletedProcess(
            args=[],
            returncode=0,
            stdout="Submitted batch job 4242\n",
            stderr="",
        )
    )
    with patch.object(lac.time, "time", return_value=fixed_t):
        with patch.object(lac, "submit_voltage_beam_sbatch", mock_sbatch):
            with caplog.at_level(logging.INFO):
                client._schedule_voltage_beam_pipeline({"dm": 87.5, "position": "10,20"}, 300.0)

    assert "Voltage beam sbatch: job_id=4242" in caplog.text
    assert "begin=now+900" in caplog.text

"""Tests for delayed Slurm scheduling from submit_voltagebeam."""

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


def test_schedule_voltage_beam_pipeline_export_dm_only_derives_duration_in_job(tmp_path, monkeypatch):
    client, fake_job, lac = _client_and_fake_job(tmp_path)
    monkeypatch.setenv("OVRO_ALERT_VOLTAGE_BEAM_JOB", str(fake_job))
    monkeypatch.setenv("OVRO_ALERT_VOLTAGE_PIPELINE_NODELIST", "lwacalim10")

    mock_run = MagicMock(
        return_value=CompletedProcess(
            args=[],
            returncode=0,
            stdout="Submitted batch job 4242\n",
            stderr="",
        )
    )
    fixed_t = 1_700_000_000
    with patch.object(lac.subprocess, "run", mock_run), patch.object(lac.time, "time", return_value=fixed_t):
        client._schedule_voltage_beam_pipeline({"dm": 87.5, "position": "10,20"}, 300.0)

    mock_run.assert_called_once()
    argv = mock_run.call_args[0][0]
    assert argv[0] == "sbatch"
    assert argv[1].startswith("--begin=")
    assert argv[2] == "--nodelist=lwacalim10"
    export = argv[3]
    assert export.startswith("--export=")
    body = export.removeprefix("--export=")
    assert "dm=87.5" in body
    assert ",time=" not in body and not body.startswith("time=")
    # Window anchored at schedule time + duration + slack, not Slurm job start (~2h later).
    assert f"VOLTAGE_BEAM_WINDOW_END_EPOCH={fixed_t + 300 + 180}" in body
    assert "VOLTAGE_BEAM_LOOKBACK_MIN=11" in body  # int((300 + 300) / 60) + 1
    assert argv[4] == str(fake_job)


def test_schedule_voltage_beam_pipeline_exports_time_when_alert_has_explicit_duration(
    tmp_path, monkeypatch
):
    client, fake_job, lac = _client_and_fake_job(tmp_path)
    monkeypatch.setenv("OVRO_ALERT_VOLTAGE_BEAM_JOB", str(fake_job))
    monkeypatch.setenv("OVRO_ALERT_VOLTAGE_PIPELINE_NODELIST", "lwacalim10")

    mock_run = MagicMock(
        return_value=CompletedProcess(
            args=[],
            returncode=0,
            stdout="Submitted batch job 4242\n",
            stderr="",
        )
    )
    fixed_t = 1_700_000_000
    with patch.object(lac.subprocess, "run", mock_run), patch.object(lac.time, "time", return_value=fixed_t):
        client._schedule_voltage_beam_pipeline(
            {"dm": 87.5, "position": "10,20", "duration": 450.0}, 450.0
        )

    mock_run.assert_called_once()
    argv = mock_run.call_args[0][0]
    body = argv[3].removeprefix("--export=")
    assert "dm=87.5" in body
    assert "time=450.0" in body
    assert f"VOLTAGE_BEAM_WINDOW_END_EPOCH={fixed_t + 450 + 180}" in body


def test_schedule_skips_without_dm(tmp_path, monkeypatch, caplog):
    import logging

    client, fake_job, lac = _client_and_fake_job(tmp_path)
    monkeypatch.setenv("OVRO_ALERT_VOLTAGE_BEAM_JOB", str(fake_job))

    mock_run = MagicMock()
    with patch.object(lac.subprocess, "run", mock_run):
        with caplog.at_level(logging.WARNING):
            client._schedule_voltage_beam_pipeline({"duration": 100.0, "position": "0,0"}, 100.0)

    mock_run.assert_not_called()
    assert "dm missing" in caplog.text

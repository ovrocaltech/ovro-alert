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


def test_schedule_voltage_beam_pipeline_export_dm_time(tmp_path, monkeypatch):
    client, fake_job, lac = _client_and_fake_job(tmp_path)
    monkeypatch.setenv("OVRO_ALERT_VOLTAGE_BEAM_JOB", str(fake_job))

    mock_run = MagicMock(
        return_value=CompletedProcess(
            args=[],
            returncode=0,
            stdout="Submitted batch job 4242\n",
            stderr="",
        )
    )
    with patch.object(lac.subprocess, "run", mock_run):
        client._schedule_voltage_beam_pipeline({"dm": 87.5, "position": "10,20"}, 300.0)

    mock_run.assert_called_once()
    argv = mock_run.call_args[0][0]
    assert argv[0] == "sbatch"
    assert argv[1].startswith("--begin=")
    assert "dm=87.5" in argv[2]
    assert "time=300.0" in argv[2]
    assert argv[3] == str(fake_job)


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

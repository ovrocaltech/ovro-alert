"""Tests for parsing voltage_beam_pipeline Slurm stdout."""

import pytest

from ovro_alert.voltage_beam_selection import parse_voltage_beam_slurm_stdout


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

"""Integration-style checks for voltage_beam_pipeline.job → lwa-voltage-beam run."""

from pathlib import Path

import pytest

JOB = Path(__file__).resolve().parents[1] / "slurm" / "voltage_beam_pipeline.job"


def test_job_invokes_lwa_voltage_beam_run_subcommand():
    text = JOB.read_text()
    assert 'lwa-voltage-beam "${RUN_ARGS[@]}"' in text
    assert "run" in text.split("RUN_ARGS=(")[1].split(")")[0]


def test_job_passes_duration_when_time_exported():
    text = JOB.read_text()
    assert 'if [[ -v time ]]; then' in text
    assert 'RUN_ARGS+=(--duration "${time}")' in text


def test_job_does_not_pass_duration_when_time_unset():
    text = JOB.read_text()
    # Duration derived inside Python when time is unset
    assert "DM_FOR_DELAY" not in text
    assert "prepare_metadata" not in text


@pytest.mark.skipif(not Path("/bin/bash").exists(), reason="bash required")
def test_job_run_section_exits_on_cli_failure(tmp_path, monkeypatch):
    """Simulate the job's run+exit path with a failing lwa-voltage-beam."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    script = fake_bin / "lwa-voltage-beam"
    script.write_text("#!/bin/bash\nexit 2\n")
    script.chmod(0o755)

    snippet = """
set -euo pipefail
export PATH="{bin}:$PATH"
lwa-voltage-beam run --dm 1 --ra 0 --dec 0 --workdir /tmp --duration 0
run_rc=$?
exit "${{run_rc}}"
""".format(
        bin=fake_bin
    )
    proc = __import__("subprocess").run(
        ["bash", "-c", snippet],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2

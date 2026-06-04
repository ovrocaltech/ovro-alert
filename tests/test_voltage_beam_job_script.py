"""Tests that voltage_beam_pipeline.job delegates to lwa-voltage-beam run."""

from pathlib import Path


JOB = Path(__file__).resolve().parents[1] / "slurm" / "voltage_beam_pipeline.job"


def test_job_calls_lwa_voltage_beam_run():
    text = JOB.read_text()
    assert "lwa-voltage-beam" in text
    assert 'RUN_ARGS=(\n  run' in text or "run\n" in text
    assert "--workdir" in text


def test_job_no_legacy_pipeline_py():
    text = JOB.read_text()
    assert "src/pipeline.py" not in text
    assert "prepare_metadata.py" not in text
    assert "from conversion import data" not in text
    assert "pip install" not in text


def test_job_keeps_product_finalize():
    text = JOB.read_text()
    assert "Moved products to" in text
    assert "voltage_beam_${SLURM_JOB_ID" in text

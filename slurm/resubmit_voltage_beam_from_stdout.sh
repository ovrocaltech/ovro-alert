#!/usr/bin/env bash
# Re-submit voltage_beam_pipeline.job using dm and duration parsed from a prior job's stdout.
#
# Reads lines written by slurm/voltage_beam_pipeline.job, e.g.:
#   Pipeline env: dm=87.3 time=300 ...
#   Pipeline parameters: dm=87.3 duration_sec=300 (from exported time ...)
#
# A fresh mtime window is computed at resubmit time (same rules as alert-driven sbatch).
#
# Usage:
#   resubmit_voltage_beam_from_stdout.sh SLURM_STDOUT_FILE
#   resubmit_voltage_beam_from_stdout.sh --begin=now+1hour /home/pipeline/slurm/voltage_beam_pipeline-12345.out
#   resubmit_voltage_beam_from_stdout.sh --dry-run voltage_beam_pipeline-12345.out
#
# Environment (optional):
#   OVRO_ALERT_VOLTAGE_BEAM_JOB          — path to voltage_beam_pipeline.job
#   OVRO_ALERT_VOLTAGE_PIPELINE_NODELIST — sbatch --nodelist (default: lwacalim02)
#   VOLTAGE_BEAM_SEARCH_DIR              — beam directory for file pick at job start

set -euo pipefail

usage() {
  sed -n '1,18p' "$0" | tail -n +2 | sed -n '/^# /s/^# //p'
  echo "Options:" >&2
  echo "  --begin WHEN   sbatch --begin (default: now)" >&2
  echo "  --job PATH     batch script (default: slurm/voltage_beam_pipeline.job)" >&2
  echo "  --dry-run      parse and print sbatch command without submitting" >&2
  echo "  --             remaining args passed to sbatch before the job script" >&2
}

BEGIN="now"
JOB_SCRIPT="${OVRO_ALERT_VOLTAGE_BEAM_JOB:-}"
DRY_RUN=0
EXTRA=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h | --help)
      usage
      exit 0
      ;;
    --begin=*)
      BEGIN="${1#*=}"
      shift
      ;;
    --begin)
      BEGIN="${2:?--begin requires an argument}"
      shift 2
      ;;
    --job=*)
      JOB_SCRIPT="${1#*=}"
      shift
      ;;
    --job)
      JOB_SCRIPT="${2:?--job requires an argument}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --)
      shift
      EXTRA=("$@")
      break
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      break
      ;;
  esac
done

if [[ $# -lt 1 ]]; then
  echo "Expected: SLURM_STDOUT_FILE" >&2
  usage >&2
  exit 2
fi

STDOUT_FILE="$1"
if [[ ! -f "$STDOUT_FILE" ]]; then
  echo "Not a file: ${STDOUT_FILE}" >&2
  exit 1
fi

if [[ -z "$JOB_SCRIPT" ]]; then
  _here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  JOB_SCRIPT="${_here}/voltage_beam_pipeline.job"
fi
if [[ ! -f "$JOB_SCRIPT" ]]; then
  echo "Job script not found: ${JOB_SCRIPT}" >&2
  exit 1
fi

_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

read -r DM DURATION_SEC EXPORT_BODY < <(
  python3 - "${STDOUT_FILE}" "${_REPO_ROOT}" <<'PY'
import sys
from pathlib import Path

repo = Path(sys.argv[2])
sys.path.insert(0, str(repo))
from ovro_alert.voltage_beam_selection import (
    parse_voltage_beam_slurm_stdout,
    sbatch_voltage_beam_exports,
)

content = Path(sys.argv[1]).read_text()
dm, duration_sec = parse_voltage_beam_slurm_stdout(content)
export_body = sbatch_voltage_beam_exports(
    dm, duration_sec, explicit_time_sec=duration_sec
)
print(dm, duration_sec, export_body, sep="\t")
PY
)

NODELIST="${OVRO_ALERT_VOLTAGE_PIPELINE_NODELIST:-lwacalim02}"

echo "Parsed from ${STDOUT_FILE}: dm=${DM} duration_sec=${DURATION_SEC}" >&2
echo "sbatch export: ${EXPORT_BODY}" >&2

SBATCH_CMD=(
  sbatch
  "--begin=${BEGIN}"
  "--nodelist=${NODELIST}"
  "--export=ALL,${EXPORT_BODY}"
  "${EXTRA[@]}"
  "$JOB_SCRIPT"
)

if [[ "${DRY_RUN}" -eq 1 ]]; then
  printf 'Would run: '
  printf '%q ' "${SBATCH_CMD[@]}"
  echo
  exit 0
fi

exec "${SBATCH_CMD[@]}"

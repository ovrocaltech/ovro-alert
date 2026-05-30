#!/usr/bin/env bash
# Submit the voltage beam Slurm pipeline for a specific raw voltage file.
# You do not need to export any variables: dm and filename are passed via sbatch --export.
# TIME_SECONDS is optional; if omitted, exports time=0 (search the full voltage/PSRFITS span).
# Pass a positive value to cap the HDF5/search window (same as run_pipeline.py --duration).
# Optional overrides: OVRO_ALERT_VOLTAGE_BEAM_JOB, --job.
#
# Usage:
#   submit_voltage_beam_file.sh [--begin WHEN] [--job PATH] VOLTAGE_FILE DM [TIME_SECONDS]
#   submit_voltage_beam_file.sh ... -- EXTRA_SBATCH_ARGS...
#
# Examples:
#   ./slurm/submit_voltage_beam_file.sh /lustre/ubuntu/beam01/foo.raw 87.3
#   ./slurm/submit_voltage_beam_file.sh /lustre/ubuntu/beam01/foo.raw 87.3 300
#   ./slurm/submit_voltage_beam_file.sh --begin=now+1hour /path/to/file.raw 120 600
#   ./slurm/submit_voltage_beam_file.sh /path/to/file.raw 50 120 -- --mail-type=END
#
# Override job script path (same idea as OVRO_ALERT_VOLTAGE_BEAM_JOB in Python):
#   OVRO_ALERT_VOLTAGE_BEAM_JOB=/other/voltage_beam_pipeline.job ./slurm/submit_voltage_beam_file.sh ...

set -euo pipefail

usage() {
  sed -n '1,20p' "$0" | tail -n +2 | sed -n '/^# /s/^# //p'
  echo "Options:" >&2
  echo "  --begin WHEN   sbatch --begin (default: now)" >&2
  echo "  --job PATH     batch script (default: slurm/voltage_beam_pipeline.job next to this script," >&2
  echo "                 or OVRO_ALERT_VOLTAGE_BEAM_JOB if set)" >&2
  echo "  --             remaining args are passed to sbatch before the job script" >&2
}

BEGIN="now"
JOB_SCRIPT="${OVRO_ALERT_VOLTAGE_BEAM_JOB:-}"
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

if [[ $# -lt 2 ]]; then
  echo "Expected: VOLTAGE_FILE DM [TIME_SECONDS]" >&2
  usage >&2
  exit 2
fi

VOLTAGE_FILE="$1"
DM="$2"
if [[ $# -ge 3 ]]; then
  TIME_SEC="$3"
else
  TIME_SEC="0"
fi

if [[ ! -f "$VOLTAGE_FILE" ]]; then
  echo "Not a regular file: ${VOLTAGE_FILE}" >&2
  exit 1
fi

if command -v realpath >/dev/null 2>&1; then
  VOLTAGE_FILE="$(realpath "$VOLTAGE_FILE")"
else
  VOLTAGE_FILE="$(readlink -f "$VOLTAGE_FILE")"
fi

if [[ -z "$JOB_SCRIPT" ]]; then
  _here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  JOB_SCRIPT="${_here}/voltage_beam_pipeline.job"
fi

if [[ ! -f "$JOB_SCRIPT" ]]; then
  echo "Job script not found: ${JOB_SCRIPT}" >&2
  exit 1
fi

# filename= is set so the job never auto-picks by mtime. After ALL, we reset
# VOLTAGE_BEAM_* tuning vars so a submitter shell (e.g. VOLTAGE_BEAM_LOOKBACK_MIN=8
# from testing) cannot leak into the batch step and break unrelated logic.
_submit_export="ALL,dm=${DM},filename=${VOLTAGE_FILE},time=${TIME_SEC}"
_submit_export+=",VOLTAGE_BEAM_WINDOW_END_EPOCH="
_submit_export+=",VOLTAGE_BEAM_LOOKBACK_MIN=120"

exec sbatch \
  "--begin=${BEGIN}" \
  "--export=${_submit_export}" \
  "${EXTRA[@]}" \
  "$JOB_SCRIPT"

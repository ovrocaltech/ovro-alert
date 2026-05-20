#!/usr/bin/env bash
# Re-submit voltage_beam_pipeline.job using dm and duration parsed from a prior job's stdout.
#
# By default reuses the *original* mtime window from the log so a late resubmit still finds
# the recorded file under /lustre/ubuntu/beam01. Override with the options below.
#
# Usage:
#   resubmit_voltage_beam_from_stdout.sh SLURM_STDOUT_FILE
#   resubmit_voltage_beam_from_stdout.sh --window-end=1700005000 --lookback-min=34 job.out
#   resubmit_voltage_beam_from_stdout.sh --filename=/lustre/ubuntu/beam01/foo.raw job.out
#   resubmit_voltage_beam_from_stdout.sh --window-now job.out
#   resubmit_voltage_beam_from_stdout.sh --dry-run job.out
#
# Options:
#   --window-end EPOCH    VOLTAGE_BEAM_WINDOW_END_EPOCH for file pick (mtime <= EPOCH)
#   --lookback-min MIN    VOLTAGE_BEAM_LOOKBACK_MIN (window start = end - MIN*60)
#   --filename PATH       Pin voltage file; skip mtime window pick
#   --window-now          Anchor window to resubmit time (not for late retries)
#   --begin WHEN          sbatch --begin (default: now)
#   --job PATH            batch script path
#   --dry-run             print sbatch command only
#
# Environment (optional):
#   OVRO_ALERT_VOLTAGE_BEAM_JOB, OVRO_ALERT_VOLTAGE_PIPELINE_NODELIST

set -euo pipefail

usage() {
  sed -n '1,26p' "$0" | tail -n +2 | sed -n '/^# /s/^# //p'
}

BEGIN="now"
JOB_SCRIPT="${OVRO_ALERT_VOLTAGE_BEAM_JOB:-}"
DRY_RUN=0
WINDOW_NOW=0
WINDOW_END=""
LOOKBACK_MIN=""
FILENAME=""
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
    --window-end=*)
      WINDOW_END="${1#*=}"
      shift
      ;;
    --window-end)
      WINDOW_END="${2:?--window-end requires an argument}"
      shift 2
      ;;
    --lookback-min=*)
      LOOKBACK_MIN="${1#*=}"
      shift
      ;;
    --lookback-min)
      LOOKBACK_MIN="${2:?--lookback-min requires an argument}"
      shift 2
      ;;
    --filename=*)
      FILENAME="${1#*=}"
      shift
      ;;
    --filename)
      FILENAME="${2:?--filename requires an argument}"
      shift 2
      ;;
    --window-now)
      WINDOW_NOW=1
      shift
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
  python3 - "${STDOUT_FILE}" "${_REPO_ROOT}" "${WINDOW_END}" "${LOOKBACK_MIN}" \
    "${FILENAME}" "${WINDOW_NOW}" <<'PY'
import sys
from pathlib import Path

repo = Path(sys.argv[2])
sys.path.insert(0, str(repo))
from ovro_alert.voltage_beam_selection import build_resubmit_export

stdout_path = Path(sys.argv[1])
window_end = sys.argv[3].strip() or None
lookback = sys.argv[4].strip() or None
filename = sys.argv[5].strip() or None
window_now = sys.argv[6].strip() == "1"

content = stdout_path.read_text()
dm, duration_sec, export_body = build_resubmit_export(
    content,
    filename=filename,
    window_end_epoch=int(window_end) if window_end else None,
    lookback_min=int(lookback) if lookback else None,
    window_now=window_now,
)
print("{0}\t{1}\t{2}".format(dm, duration_sec, export_body))
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

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
#   resubmit_voltage_beam_from_stdout.sh --no-resume job.out
#   resubmit_voltage_beam_from_stdout.sh --resume-from=/fast/pipeline/fast/voltage_beam_123 job.out
#   resubmit_voltage_beam_from_stdout.sh --dry-run job.out
#
# Options:
#   --window-end EPOCH    VOLTAGE_BEAM_WINDOW_END_EPOCH for file pick (mtime <= EPOCH)
#   --lookback-min MIN    VOLTAGE_BEAM_LOOKBACK_MIN (window start = end - MIN*60)
#   --filename PATH       Pin voltage file; skip mtime window pick
#   --window-now          Anchor window to resubmit time (not for late retries)
#   --resume-from PATH    Reuse checkpoint/artifacts from a prior job directory
#   --no-resume           Do not auto-detect prior artifacts from the stdout log
#   --begin WHEN          sbatch --begin (default: now)
#   --job PATH            batch script path
#   --dry-run             print sbatch command only
#
# Environment (optional):
#   OVRO_ALERT_VOLTAGE_BEAM_JOB, OVRO_ALERT_VOLTAGE_PIPELINE_NODELIST
#   VOLTAGE_BEAM_RA, VOLTAGE_BEAM_DEC — override when stdout lacks Pipeline target line

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
RESUME_FROM=""
NO_RESUME=0
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
    --resume-from=*)
      RESUME_FROM="${1#*=}"
      shift
      ;;
    --resume-from)
      RESUME_FROM="${2:?--resume-from requires an argument}"
      shift 2
      ;;
    --no-resume)
      NO_RESUME=1
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

read -r DM DURATION_SEC EXPORT_BODY RESUME_DIR RESUME_NOTE < <(
  python3 - "${STDOUT_FILE}" "${_REPO_ROOT}" "${WINDOW_END}" "${LOOKBACK_MIN}" \
    "${FILENAME}" "${WINDOW_NOW}" "${RESUME_FROM}" "${NO_RESUME}" <<'PY'
import os
import sys
from pathlib import Path

repo = Path(sys.argv[2])
sys.path.insert(0, str(repo))
from ovro_alert.voltage_beam_selection import (
    _checkpoint_summary,
    build_resubmit_export,
)

stdout_path = Path(sys.argv[1])
window_end = sys.argv[3].strip() or None
lookback = sys.argv[4].strip() or None
filename = sys.argv[5].strip() or None
window_now = sys.argv[6].strip() == "1"
resume_from = sys.argv[7].strip() or None
no_resume = sys.argv[8].strip() == "1"

ra = os.environ.get("VOLTAGE_BEAM_RA")
dec = os.environ.get("VOLTAGE_BEAM_DEC")
ra = float(ra) if ra else None
dec = float(dec) if dec else None

content = stdout_path.read_text()
dm, duration_sec, export_body, resume_dir = build_resubmit_export(
    content,
    filename=filename,
    window_end_epoch=int(window_end) if window_end else None,
    lookback_min=int(lookback) if lookback else None,
    window_now=window_now,
    ra=ra,
    dec=dec,
    stdout_path=str(stdout_path),
    resume_from=resume_from,
    no_resume=no_resume,
)
resume_note = ""
if resume_dir:
    resume_note = _checkpoint_summary(Path(resume_dir) / "checkpoint.json")
print("{0}\t{1}\t{2}\t{3}\t{4}".format(
    dm, duration_sec, export_body, resume_dir or "", resume_note
))
PY
)

NODELIST="${OVRO_ALERT_VOLTAGE_PIPELINE_NODELIST:-lwacalim02}"

echo "Parsed from ${STDOUT_FILE}: dm=${DM} duration_sec=${DURATION_SEC}" >&2
if [[ -n "${RESUME_DIR}" ]]; then
  echo "Resume artifacts: ${RESUME_DIR} (${RESUME_NOTE:-})" >&2
fi
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

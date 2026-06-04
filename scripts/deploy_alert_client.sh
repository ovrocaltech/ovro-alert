#!/usr/bin/env bash
# Deploy voltage-beam alert *scheduling* on the observing host (deployment conda, Python 3.6).
#
# Do NOT run: pip install -e .   (ovro-alert pyproject requires Python >=3.9)
#
# Instead:
#   - Keep ovro-alert from the deployment env (mnc_python environment.yml pin), or
#     use the checkout on PYTHONPATH only for ovro_alert if you manage that separately.
#   - Expose lwa-fasttransients scheduling via PYTHONPATH (frb_search_pipeline.slurm_schedule).
#
# After git pull on ovro-alert and/or lwa-fasttransients:
#   cd /home/pipeline/proj/ovro-alert
#   ./scripts/deploy_alert_client.sh
#
# Persist for long-running clients (systemd, cron, login):
#   source .../ovro-alert/scripts/alert_client_env.sh
#
# Pipeline processing still deploys on lwacalim02 only:
#   cd .../lwa-fasttransients && ./scripts/deploy_calim.sh

set -eo pipefail

: "${DEPLOYMENT_CONDA:=/opt/devel/pipeline/envs/deployment}"
: "${OVRO_ALERT_ROOT:=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
: "${LWA_FT_ROOT:=$(cd "${OVRO_ALERT_ROOT}/../lwa-fasttransients" && pwd)}"

# conda activate.d hooks may reference unset vars; avoid nounset during activate.
set +u
if [[ -f "${DEPLOYMENT_CONDA}/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "${DEPLOYMENT_CONDA}/bin/activate"
elif command -v conda >/dev/null 2>&1; then
  eval "$(conda shell.bash hook)"
  conda activate deployment
else
  set -u
  echo "ERROR: deployment conda not found (set DEPLOYMENT_CONDA or install conda)" >&2
  exit 1
fi
set -u

# shellcheck source=scripts/alert_client_env.sh
source "${OVRO_ALERT_ROOT}/scripts/alert_client_env.sh"

echo "Deploy alert client scheduling:"
echo "  conda env: deployment"
echo "  python:    $(command -v python) ($(python --version 2>&1))"
echo "  OVRO_ALERT_ROOT=${OVRO_ALERT_ROOT}"
echo "  LWA_FT_SRC=${LWA_FT_SRC}"
echo "  PYTHONPATH=${PYTHONPATH}"

if [[ ! -d "${LWA_FT_SRC}/frb_search_pipeline" ]]; then
  echo "ERROR: missing ${LWA_FT_SRC}/frb_search_pipeline (git pull lwa-fasttransients?)" >&2
  exit 1
fi

python "${OVRO_ALERT_ROOT}/scripts/smoke_alert_client_scheduling.py"

if command -v python3.6 >/dev/null 2>&1; then
  echo "Running Python 3.6 scheduling smoke..."
  PYTHONPATH="${LWA_FT_SRC}:${PYTHONPATH:-}" python3.6 "${OVRO_ALERT_ROOT}/scripts/smoke_alert_client_scheduling.py"
fi

echo "deploy_alert_client.sh: OK"
echo "Reminder: do not pip install -e ${OVRO_ALERT_ROOT} into deployment (requires Python >=3.9)."

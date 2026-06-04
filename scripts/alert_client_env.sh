# Source from bash after: conda activate deployment
#   source /home/pipeline/proj/ovro-alert/scripts/alert_client_env.sh
#
# Exposes lwa-fasttransients scheduling on Python 3.6 without pip install -e ovro-alert.

: "${OVRO_ALERT_ROOT:=/home/pipeline/proj/ovro-alert}"
: "${LWA_FT_ROOT:=/home/pipeline/proj/lwa-fasttransients}"
: "${LWA_FT_SRC:=${LWA_FT_ROOT}/src}"

export OVRO_ALERT_ROOT LWA_FT_ROOT LWA_FT_SRC
export PYTHONPATH="${LWA_FT_SRC}:${PYTHONPATH:-}"

if [[ -z "${OVRO_ALERT_VOLTAGE_BEAM_JOB:-}" && -f "${OVRO_ALERT_ROOT}/slurm/voltage_beam_pipeline.job" ]]; then
  export OVRO_ALERT_VOLTAGE_BEAM_JOB="${OVRO_ALERT_ROOT}/slurm/voltage_beam_pipeline.job"
fi

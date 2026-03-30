#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="cobalt-boat.service"
HEALTHCHECK_SERVICE_NAME="cobalt-boat-healthcheck.service"
HEALTHCHECK_TIMER_NAME="cobalt-boat-healthcheck.timer"
SYSTEMD_DIR="/etc/systemd/system"
ENV_PATH="/etc/default/cobalt-boat"
TMPFILES_PATH="/etc/tmpfiles.d/cobalt-boat.conf"
LOGROTATE_PATH="/etc/logrotate.d/cobalt-boat"
HEALTHCHECK_BIN_PATH="/usr/local/bin/cobalt-boat-healthcheck"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_USER="${SERVICE_USER:-$(stat -c '%U' "${REPO_ROOT}")}"
SERVICE_GROUP="${SERVICE_GROUP:-$(stat -c '%G' "${REPO_ROOT}")}"
SERVICE_SRC="${REPO_ROOT}/deploy/systemd/${SERVICE_NAME}"
HEALTHCHECK_SERVICE_SRC="${REPO_ROOT}/deploy/systemd/${HEALTHCHECK_SERVICE_NAME}"
HEALTHCHECK_TIMER_SRC="${REPO_ROOT}/deploy/systemd/${HEALTHCHECK_TIMER_NAME}"
ENV_SRC="${REPO_ROOT}/deploy/systemd/cobalt-boat.env"
TMPFILES_SRC="${REPO_ROOT}/deploy/systemd/cobalt-boat.tmpfiles.conf"
LOGROTATE_SRC="${REPO_ROOT}/deploy/logrotate/cobalt-boat"
HEALTHCHECK_BIN_SRC="${REPO_ROOT}/scripts/cobalt-boat-healthcheck"

log() {
  printf '[install_systemd] %s\n' "$*"
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    log "this script must run as root (use sudo)"
    exit 1
  fi
}

install_files() {
  if [[ ! -x "${REPO_ROOT}/.venv/bin/cobalt-boat-api" ]]; then
    log "missing runtime binary: ${REPO_ROOT}/.venv/bin/cobalt-boat-api"
    log "create venv and install first: python -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'"
    exit 1
  fi

  local service_rendered
  local env_rendered
  local tmpfiles_rendered
  local logrotate_rendered
  service_rendered="$(mktemp)"
  env_rendered="$(mktemp)"
  tmpfiles_rendered="$(mktemp)"
  logrotate_rendered="$(mktemp)"

  sed \
    -e "s#__COBALT_REPO_ROOT__#${REPO_ROOT}#g" \
    -e "s#__COBALT_USER__#${SERVICE_USER}#g" \
    -e "s#__COBALT_GROUP__#${SERVICE_GROUP}#g" \
    "${SERVICE_SRC}" > "${service_rendered}"
  sed \
    -e "s#__COBALT_REPO_ROOT__#${REPO_ROOT}#g" \
    "${ENV_SRC}" > "${env_rendered}"
  sed \
    -e "s#__COBALT_REPO_ROOT__#${REPO_ROOT}#g" \
    -e "s#__COBALT_USER__#${SERVICE_USER}#g" \
    -e "s#__COBALT_GROUP__#${SERVICE_GROUP}#g" \
    "${TMPFILES_SRC}" > "${tmpfiles_rendered}"
  sed \
    -e "s#__COBALT_USER__#${SERVICE_USER}#g" \
    -e "s#__COBALT_GROUP__#${SERVICE_GROUP}#g" \
    "${LOGROTATE_SRC}" > "${logrotate_rendered}"

  install -D -m 0644 "${service_rendered}" "${SYSTEMD_DIR}/${SERVICE_NAME}"
  install -D -m 0644 "${HEALTHCHECK_SERVICE_SRC}" "${SYSTEMD_DIR}/${HEALTHCHECK_SERVICE_NAME}"
  install -D -m 0644 "${HEALTHCHECK_TIMER_SRC}" "${SYSTEMD_DIR}/${HEALTHCHECK_TIMER_NAME}"
  install -D -m 0755 "${HEALTHCHECK_BIN_SRC}" "${HEALTHCHECK_BIN_PATH}"
  install -D -m 0644 "${tmpfiles_rendered}" "${TMPFILES_PATH}"
  install -D -m 0644 "${logrotate_rendered}" "${LOGROTATE_PATH}"

  if [[ -f "${ENV_PATH}" ]]; then
    local backup_path
    backup_path="${ENV_PATH}.bak.$(date -u +%Y%m%dT%H%M%SZ)"
    cp "${ENV_PATH}" "${backup_path}"
    log "existing env backed up to ${backup_path}"
  fi

  install -D -m 0644 "${env_rendered}" "${ENV_PATH}"

  rm -f "${service_rendered}" "${env_rendered}" "${tmpfiles_rendered}" "${logrotate_rendered}"

  systemd-tmpfiles --create "${TMPFILES_PATH}"
}

enable_service() {
  systemctl daemon-reload
  systemctl enable "${SERVICE_NAME}"
  systemctl enable --now "${HEALTHCHECK_TIMER_NAME}"
  log "enabled ${SERVICE_NAME}"
  log "enabled and started ${HEALTHCHECK_TIMER_NAME}"
}

main() {
  require_root
  install_files
  enable_service
  log "installation complete"
  log "service user/group: ${SERVICE_USER}:${SERVICE_GROUP}"
  log "repo root: ${REPO_ROOT}"
  log "start service: systemctl start ${SERVICE_NAME}"
  log "check status: systemctl status ${SERVICE_NAME} --no-pager"
  log "tail logs: journalctl -u ${SERVICE_NAME} -f"
}

main "$@"

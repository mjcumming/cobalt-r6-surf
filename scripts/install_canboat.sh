#!/usr/bin/env bash
set -euo pipefail

# Reproducible CANboat installer for Raspberry Pi OS.
# Installs pinned CANboat release and records installed version metadata.

CANBOAT_REPO_URL="${CANBOAT_REPO_URL:-https://github.com/canboat/canboat.git}"
CANBOAT_VERSION="${CANBOAT_VERSION:-v6.1.6}"
BUILD_ROOT="${BUILD_ROOT:-/tmp/cobalt-canboat-build}"
INSTALL_PREFIX="${INSTALL_PREFIX:-/usr/local}"
METADATA_DIR="${METADATA_DIR:-/usr/local/share/cobalt}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() {
  printf '[install_canboat] %s\n' "$*"
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    log "this script must run as root (use sudo)"
    exit 1
  fi
}

install_deps() {
  log "installing build dependencies"
  apt-get update
  apt-get install -y --no-install-recommends \
    build-essential \
    git \
    libsocketcan-dev \
    pkg-config \
    ca-certificates
}

checkout_source() {
  rm -rf "${BUILD_ROOT}"
  mkdir -p "${BUILD_ROOT}"
  log "cloning CANboat ${CANBOAT_VERSION}"
  git clone --depth 1 --branch "${CANBOAT_VERSION}" "${CANBOAT_REPO_URL}" "${BUILD_ROOT}/canboat"
}

build_and_install() {
  log "building CANboat"
  make -C "${BUILD_ROOT}/canboat"
  log "installing CANboat into ${INSTALL_PREFIX}"
  make -C "${BUILD_ROOT}/canboat" PREFIX="${INSTALL_PREFIX}" install
}

write_metadata() {
  local commit
  commit="$(git -C "${BUILD_ROOT}/canboat" rev-parse HEAD)"
  mkdir -p "${METADATA_DIR}"
  cat > "${METADATA_DIR}/canboat-install.txt" <<META
repo=${CANBOAT_REPO_URL}
version=${CANBOAT_VERSION}
commit=${commit}
installed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
install_prefix=${INSTALL_PREFIX}
META
  log "wrote metadata to ${METADATA_DIR}/canboat-install.txt"
}

install_wrapper() {
  local wrapper_src="${SCRIPT_DIR}/cobalt-canboat-decoder"
  local wrapper_dst="${INSTALL_PREFIX}/bin/cobalt-canboat-decoder"
  if [[ ! -f "${wrapper_src}" ]]; then
    log "wrapper script not found: ${wrapper_src}"
    exit 1
  fi
  install -D -m 0755 "${wrapper_src}" "${wrapper_dst}"
  log "installed wrapper to ${wrapper_dst}"
}

main() {
  require_root
  install_deps
  checkout_source
  build_and_install
  install_wrapper
  write_metadata
  log "installation complete"
  log "verify with: /usr/local/bin/cobalt-canboat-decoder --self-check"
}

main "$@"

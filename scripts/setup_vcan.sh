#!/usr/bin/env bash
set -euo pipefail

IFACE="${1:-vcan0}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "run as root: sudo ./scripts/setup_vcan.sh [iface]" >&2
  exit 1
fi

modprobe vcan
ip link show "${IFACE}" >/dev/null 2>&1 || ip link add dev "${IFACE}" type vcan
ip link set "${IFACE}" up

echo "vcan ready: ${IFACE}"
ip -details link show "${IFACE}"

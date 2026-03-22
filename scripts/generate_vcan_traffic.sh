#!/usr/bin/env bash
set -euo pipefail

IFACE="${1:-vcan0}"
COUNT="${2:-100}"

if ! command -v cangen >/dev/null 2>&1; then
  echo "missing cangen (install can-utils)" >&2
  exit 1
fi

echo "Generating ${COUNT} random CAN frames on ${IFACE}"
cangen "${IFACE}" -g 10 -n "${COUNT}" -e

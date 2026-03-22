#!/usr/bin/env bash
set -euo pipefail

IFACE="${1:-vcan0}"
DUMP_FILE="${2:-}"

if [[ -z "${DUMP_FILE}" ]]; then
  echo "usage: ./scripts/replay_candump.sh [iface] <candump_file.log>" >&2
  exit 2
fi

if ! command -v canplayer >/dev/null 2>&1; then
  echo "missing canplayer (install can-utils)" >&2
  exit 1
fi

if [[ ! -f "${DUMP_FILE}" ]]; then
  echo "file not found: ${DUMP_FILE}" >&2
  exit 1
fi

# Replay all channels in dump to one target interface for deterministic local test.
canplayer -I "${DUMP_FILE}" "*=${IFACE}"

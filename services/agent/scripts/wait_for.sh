#!/usr/bin/env bash
# wait_for.sh <url> [timeout_s]  - poll until the URL returns 2xx.
set -euo pipefail
url="${1:?usage: wait_for.sh <url> [timeout_s]}"
timeout="${2:-90}"
start=$(date +%s)
until curl -sf -o /dev/null "$url"; do
  if (( $(date +%s) - start > timeout )); then
    echo "timeout waiting for $url" >&2
    exit 1
  fi
  sleep 1
done
echo "ready: $url"

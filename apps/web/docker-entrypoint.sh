#!/bin/sh
token_file="${AGENT_DEV_TOKEN_FILE:-/tokens/token}"
tries=0
while [ -z "${AGENT_DEV_TOKEN:-}" ] && [ "$tries" -lt 15 ]; do
  if [ -s "$token_file" ]; then
    AGENT_DEV_TOKEN="$(cat "$token_file")"
  else
    tries=$((tries + 1))
    sleep 1
  fi
done
if [ -z "${AGENT_DEV_TOKEN:-}" ]; then
  echo "[web] missing dev token at $token_file" >&2
  exit 1
fi
export AGENT_DEV_TOKEN

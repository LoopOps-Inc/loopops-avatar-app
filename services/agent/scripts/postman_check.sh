#!/usr/bin/env bash
# Run the Postman collection end to end with Newman (Postman's CLI), including
# the step-up signature that is a manual step inside the Postman app.
#
#   scripts/postman_check.sh            # needs node/npx and the compose stack up
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-.venv/bin/python}
COL=docs/postman/actinver-agent.postman_collection.json
ENV=docs/postman/local.postman_environment.json
TMP=${TMPDIR:-/tmp}/actinver-postman-$$
mkdir -p "$TMP"; trap 'rm -rf "$TMP"' EXIT

$PY scripts/postman_env.py --client "${CLIENT:-cl_demo_moderado}" >/dev/null

# 1) everything up to the step-up challenge (folders 0-4 and request 5.1)
npx -y newman run "$COL" -e "$ENV" \
  --folder "0. Health" \
  --folder "1. Session" \
  --folder "2. Consents (first turn is refused until these are acknowledged)" \
  --folder "3. Chat turns (SSE)" \
  --folder "4. Transaction: the agent prepares a form" \
  --folder "5.1 POST /v1/auth/step-up/challenge" \
  --export-environment "$TMP/env.json" --reporters cli

# 2) the manual step: sign the challenge with the dev device key
CHALLENGE=$(python3 -c "import json,sys;print({v['key']:v['value'] for v in json.load(open(sys.argv[1]))['values']}['challenge'])" "$TMP/env.json")
ASSERTION=$($PY scripts/dev_token.py --sign-challenge "$CHALLENGE" --quiet)

# 3) submit + replay, then the rest of the collection
npx -y newman run "$COL" -e "$TMP/env.json" --env-var "assertion=$ASSERTION" \
  --folder "5.2 POST .../forms/{{form_id}}/submit (set \`assertion\` first)" \
  --folder "5.3 Replay same Idempotency-Key (same order_id back)" \
  --folder "6. Avatar (LiveAvatar LITE, emulated locally)" \
  --folder "7. Config and telemetry" \
  --folder "8. Compliance console (officer token)" \
  --export-environment "$TMP/env.json" --reporters cli

#!/usr/bin/env bash
# Step-by-step smoke test against a running stack (docker compose up -d --build).
# Mirrors docs/API.md. Requires: curl, jq, python (.venv) for dev tokens.
#
#   AGENT_BASE_URL=http://localhost:8443 bash scripts/smoke.sh
set -euo pipefail
cd "$(dirname "$0")/.."

BASE="${AGENT_BASE_URL:-http://localhost:8443}"
PY="${PY:-.venv/bin/python}"
CLIENT="${CLIENT:-cl_demo_moderado}"
PASS=0; FAIL=0

ok()   { PASS=$((PASS+1)); printf '\033[32mPASS\033[0m %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '\033[31mFAIL\033[0m %s\n' "$1"; }
step() { printf '\n== %s\n' "$1"; }

# SSE helper: POST a message, collect the raw stream (curl -N), stop at `done`.
sse() { # $1=thread $2=text  → prints raw event stream
  curl -sN -X POST "$BASE/v1/threads/$1/messages" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -H "Accept: text/event-stream" -H "Accept-Language: es-MX" \
    -H "Idempotency-Key: $(uuidgen 2>/dev/null || date +%s%N)" \
    -d "$(jq -cn --arg t "$2" '{text:$t}')" --max-time 60
}
# Extract the `data:` JSON of the first event of a given name from a stream.
sse_data() { # $1=event name ; stream on stdin (SSE lines end in CRLF)
  tr -d '\r' | awk -v ev="$1" '
    $0 == "event: "ev {want=1; next}
    want && /^data: / {sub(/^data: /,""); print; exit}
    /^event: / {want=0}'
}

step "1. Liveness / readiness"
curl -sf "$BASE/healthz" >/dev/null && ok "GET /healthz" || bad "GET /healthz"
READY=$(curl -s "$BASE/readyz"); echo "$READY" | jq -c . || true
[ "$(echo "$READY" | jq -r .ready)" = "true" ] && ok "GET /readyz ready=true" || bad "GET /readyz not ready"

step "2. Dev token (AUTH_MODE=dev) for $CLIENT"
TOKEN_JSON=$($PY scripts/dev_token.py --client "$CLIENT" --json)
TOKEN=$(echo "$TOKEN_JSON" | jq -r .access_token); JKT=$(echo "$TOKEN_JSON" | jq -r .jkt)
DEVICE_JWK=$(echo "$TOKEN_JSON" | jq -c .public_jwk)
[ -n "${TOKEN:-}" ] && [ "$TOKEN" != "null" ] && ok "minted token (jkt=$JKT)" || { bad "token"; exit 1; }
AUTH=(-H "Authorization: Bearer $TOKEN")

step "3. POST /v1/sessions"
SESSION=$(curl -sf -X POST "$BASE/v1/sessions" "${AUTH[@]}" -H "Content-Type: application/json" \
  -H "Idempotency-Key: smoke-session-$RANDOM" -d "$(jq -cn --argjson jwk "$DEVICE_JWK" '{channel:"chat",device_id:"dev-device-1",device_public_jwk:$jwk}')")
echo "$SESSION" | jq -c '{thread_id,capabilities,disclosures_required:[.disclosures_required[]|{id,acknowledged}]}'
THREAD=$(echo "$SESSION" | jq -r .thread_id)
[ -n "$THREAD" ] && [ "$THREAD" != "null" ] && ok "session thread_id=$THREAD" || { bad "session"; exit 1; }

step "4. Acknowledge first-turn disclosures (privacy notice, services guide, AI disclosure)"
for id in privacy_notice investment_services_guide ai_disclosure; do
  ver=$(echo "$SESSION" | jq -r --arg id "$id" '.disclosures_required[] | select(.id==($id|ascii_upcase) or .id==("SERVICES_GUIDE") and $id=="investment_services_guide" or .id=="AI_ASSISTANT" and $id=="ai_disclosure" or .id=="PRIVACY_NOTICE" and $id=="privacy_notice") | .version' | head -1)
  ver="${ver:-2026-08}"
  code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/v1/consents" "${AUTH[@]}" \
    -H "Content-Type: application/json" -H "Idempotency-Key: smoke-consent-$id-$RANDOM" \
    -d "$(jq -cn --arg t "$id" --arg v "$ver" '{type:$t,version:$v,granted:true}')")
  [[ "$code" =~ ^20[01]$ ]] && ok "consent $id ($code)" || bad "consent $id ($code)"
done
curl -s "$BASE/v1/consents" "${AUTH[@]}" | jq -c '[.consents[]|{type,granted}]'

step "5. Chat turn (SSE): portfolio_inspect"
STREAM=$(sse "$THREAD" "¿Cómo va mi portafolio?")
echo "$STREAM" | sed -n '1,40p'
DONE=$(echo "$STREAM" | sse_data done)
[ -n "$DONE" ] && ok "done event: $(echo "$DONE" | jq -c '{turn_id,evidence_id,service_type}')" || bad "no done event"
echo "$STREAM" | grep -q '^event: ui' && ok "ui event present (split-channel data)" || bad "no ui event"
echo "$STREAM" | grep -q '^event: token' && ok "token event present (speech)" || bad "no token event"

step "6. GET /v1/threads/{id}"
HIST=$(curl -sf "$BASE/v1/threads/$THREAD?limit=5" "${AUTH[@]}")
echo "$HIST" | jq -c '{thread_id,turns:(.turns|length),next_cursor}'
[ "$(echo "$HIST" | jq '.turns|length')" -ge 1 ] && ok "history has turns" || bad "history empty"

step "7. Explanation turn (portfolio_explain, PAST_PERF disclosure)"
STREAM=$(sse "$THREAD" "¿Por qué bajó mi fondo de deuda este mes?")
echo "$STREAM" | sse_data done | jq -c . && ok "explain turn completed" || bad "explain turn"

step "8. Advisory turn (advisory_recommend → suitability_gate)"
STREAM=$(sse "$THREAD" "¿Dónde me conviene invertir 200 mil pesos a dos años?")
echo "$STREAM" | sed -n '1,30p'
DONE=$(echo "$STREAM" | sse_data done)
ST=$(echo "$DONE" | jq -r .service_type)
if [ "$CLIENT" = "cl_demo_moderado" ]; then
  [ "$ST" = "asesorado" ] && ok "service_type=asesorado" || bad "expected asesorado, got $ST"
  echo "$STREAM" | grep -q 'suitability_summary' && ok "suitability_summary ui emitted" || bad "no suitability_summary"
else
  ok "service_type=$ST (client may not be contracted for advisory)"
fi

step "9. Transaction: plan → challenge → sign → submit"
STREAM=$(sse "$THREAD" "Quiero invertir 100 mil pesos en ACTIGOB-BF")
FORM=$(echo "$STREAM" | sse_data form_spec)
if [ -z "$FORM" ]; then
  echo "$STREAM" | sed -n '1,20p'
  bad "no form_spec event (is $CLIENT contracted for execution?)"
else
  FORM_ID=$(echo "$FORM" | jq -r .form_id)
  ok "form_spec $FORM_ID ($(echo "$FORM" | jq -r '.operation') $(echo "$FORM" | jq -r '.product.id'))"
  ACKS=$(echo "$FORM" | jq -c '[.disclosures[]|select(.ack==true)|.id]')
  CH=$(curl -sf -X POST "$BASE/v1/auth/step-up/challenge" "${AUTH[@]}" -H "Content-Type: application/json" \
    -H "Idempotency-Key: smoke-ch-$RANDOM" \
    -d "$(jq -cn --arg f "$FORM_ID" '{form_id:$f, amount:{amount:"100000.00",currency:"MXN"}}')")
  CHALLENGE=$(echo "$CH" | jq -r .challenge); CHID=$(echo "$CH" | jq -r .challenge_id)
  [ -n "$CHALLENGE" ] && ok "step-up challenge $CHID" || bad "challenge"
  ASSERTION=$($PY scripts/dev_token.py --sign-challenge "$CHALLENGE")
  SUBMIT=$(curl -s -X POST "$BASE/v1/threads/$THREAD/forms/$FORM_ID/submit" "${AUTH[@]}" \
    -H "Content-Type: application/json" -H "Idempotency-Key: smoke-submit-$FORM_ID" \
    -d "$(jq -cn --arg a "$ASSERTION" --arg c "$CHID" --argjson acks "$ACKS" \
        '{values:{amount:{amount:"100000.00",currency:"MXN"},account_id:"acc_demo_1",recurring:false},acknowledgements:$acks,challenge_id:$c,step_up_assertion:$a}')")
  echo "$SUBMIT" | jq -c '{order_id,status,settlement_date,evidence_id,code,message}'
  [ "$(echo "$SUBMIT" | jq -r .status)" = "RECEIVED" ] && ok "order RECEIVED" || bad "submit: $(echo "$SUBMIT" | jq -r '.code // .status')"
fi

step "10. Avatar preflight / session / stop (LIVEAVATAR_PROVIDER=stub by default)"
PRE=$(curl -s "$BASE/v1/avatar/preflight" "${AUTH[@]}"); echo "$PRE" | jq -c .
# Voice consent is a separate, revocable consent (DP-02).
curl -s -o /dev/null -X POST "$BASE/v1/consents" "${AUTH[@]}" -H "Content-Type: application/json" \
  -H "Idempotency-Key: smoke-voice-$RANDOM" -d '{"type":"voice_recording","version":"2026-08","granted":true}'
AV=$(curl -s -X POST "$BASE/v1/avatar/session" "${AUTH[@]}" -H "Content-Type: application/json" \
  -H "Idempotency-Key: smoke-av-$RANDOM" -d "$(jq -cn --arg t "$THREAD" '{thread_id:$t}')")
echo "$AV" | jq -c 'del(.livekit_client_token)'
if echo "$AV" | jq -e .avatar_session_id >/dev/null 2>&1; then
  echo "$AV" | jq -e 'has("livekit_agent_token")|not' >/dev/null && ok "no livekit_agent_token in client payload" || bad "AGENT TOKEN LEAKED"
  AVID=$(echo "$AV" | jq -r .avatar_session_id)
  STOP=$(curl -s -X POST "$BASE/v1/avatar/session/stop" "${AUTH[@]}" -H "Content-Type: application/json" \
    -H "Idempotency-Key: smoke-stop-$RANDOM" -d "$(jq -cn --arg s "$AVID" '{avatar_session_id:$s,reason:"user"}')")
  [ "$(echo "$STOP" | jq -r .stopped)" = "true" ] && ok "avatar session stopped" || bad "stop"
else
  bad "avatar session: $(echo "$AV" | jq -r '.code // .')"
fi

step "11. Client config poll + telemetry ingest"
curl -sf "$BASE/v1/config" "${AUTH[@]}" | jq -c '{kill_switch,voice_mode,avatar,advisory,transactional}' && ok "GET /v1/config" || bad "config"
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/v1/telemetry" "${AUTH[@]}" -H "Content-Type: application/json" \
  -d '{"events":[{"name":"ui.unknown_component","attributes":{"type":"x","client_id":"must-be-stripped"}}]}')
[[ "$code" =~ ^20 ]] && ok "POST /v1/telemetry ($code)" || bad "telemetry ($code)"

step "12. Compliance console (roles: compliance,risk)"
eval "$($PY scripts/dev_token.py --client officer_demo --roles compliance,risk --export | sed 's/^export TOKEN/export CTOKEN/;s/^export JKT/export CJKT/')"
CAUTH=(-H "Authorization: Bearer $CTOKEN")
EV=$(curl -s "$BASE/v1/compliance/evidence?thread_id=$THREAD&limit=10" "${CAUTH[@]}" -H "X-Reason: smoke test")
echo "$EV" | jq -c '{items:(.items|length)}' && ok "evidence list" || bad "evidence list"
VER=$(curl -s "$BASE/v1/compliance/evidence/verify/$THREAD" "${CAUTH[@]}" -H "X-Reason: smoke test")
echo "$VER" | jq -c .
[ "$(echo "$VER" | jq -r .ok)" = "true" ] && ok "hash chain verifies" || bad "chain verify"
curl -s "$BASE/v1/compliance/summary" "${CAUTH[@]}" | jq -c '{evidence_records,turns_by_service_type}' && ok "summary" || bad "summary"
curl -s "$BASE/v1/compliance/flags" "${CAUTH[@]}" | jq -c '[.[]|{name,value}]' | head -c 400; echo

step "13. Kill switch drill (Risk authority): flip on, observe static message, flip off"
curl -s -o /dev/null -X PUT "$BASE/v1/compliance/flags/advisor.kill_switch" "${CAUTH[@]}" -H "Content-Type: application/json" \
  -d '{"value":"on","reason":"smoke drill"}'
STREAM=$(sse "$THREAD" "¿Cómo va mi portafolio?" || true)
echo "$STREAM" | sse_data error | jq -c . 2>/dev/null || echo "$STREAM" | head -5
echo "$STREAM" | grep -q 'KILL_SWITCH' && ok "kill switch refuses without a model call" || bad "kill switch not enforced"
curl -s -o /dev/null -X PUT "$BASE/v1/compliance/flags/advisor.kill_switch" "${CAUTH[@]}" -H "Content-Type: application/json" \
  -d '{"value":"off","reason":"smoke drill end"}' && ok "kill switch off"

printf '\n%d passed, %d failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]

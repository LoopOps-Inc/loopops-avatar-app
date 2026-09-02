#!/usr/bin/env sh
# Bootstraps the local AWS emulator (floci, https://floci.io/aws/) so the stack
# has what production gets from real AWS + the External Secrets Operator:
#   * two S3 buckets with Object Lock (evidence WORM tier + the separate
#     trust-domain anchor bucket for chain heads, ADR-0012)
#   * Secrets Manager entries for every `secretsmanager://` / `kms://` reference
#     in config.py. Values are random per environment; never real credentials.
# Idempotent: every step tolerates "already exists".
set -eu

ENDPOINT="${AWS_ENDPOINT_URL:-http://floci:4566}"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"
export AWS_DEFAULT_REGION="$REGION"
export AWS_PAGER=""

EVIDENCE_BUCKET="${OBJECT_STORE_BUCKET:-actinver-evidence-local}"
ANCHOR_BUCKET="${ANCHOR_BUCKET:-actinver-anchor-local}"

aws() { command aws --endpoint-url "$ENDPOINT" --region "$REGION" "$@"; }

echo "[floci-init] waiting for $ENDPOINT ..."
i=0
until aws s3 ls >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -gt 60 ]; then
    echo "[floci-init] emulator not reachable after 60s" >&2
    exit 1
  fi
  sleep 1
done

random_hex() {
  # 32 bytes hex; works without openssl (aws-cli image is minimal).
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  else
    head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'
  fi
}

ensure_bucket() {
  bucket="$1"
  if aws s3api head-bucket --bucket "$bucket" >/dev/null 2>&1; then
    echo "[floci-init] bucket $bucket exists"
  else
    echo "[floci-init] creating bucket $bucket (object lock enabled)"
    aws s3api create-bucket --bucket "$bucket" --object-lock-enabled-for-bucket >/dev/null
  fi
  aws s3api put-bucket-versioning --bucket "$bucket" \
    --versioning-configuration Status=Enabled >/dev/null 2>&1 || true
  # Default retention is deliberately short (1 day, GOVERNANCE) so local test
  # data can be cleaned. The evidence writer sets the real per-object
  # retention (5 years; COMPLIANCE mode in prod, ADR-0012) on every PutObject.
  aws s3api put-object-lock-configuration --bucket "$bucket" \
    --object-lock-configuration '{"ObjectLockEnabled":"Enabled","Rule":{"DefaultRetention":{"Mode":"GOVERNANCE","Days":1}}}' \
    >/dev/null 2>&1 || echo "[floci-init] object-lock default config not applied on $bucket (emulator may not support defaults; per-object retention still applies)"
}

ensure_secret() {
  name="$1"
  value="$2"
  if aws secretsmanager describe-secret --secret-id "$name" >/dev/null 2>&1; then
    echo "[floci-init] secret $name exists"
  else
    echo "[floci-init] creating secret $name"
    aws secretsmanager create-secret --name "$name" --secret-string "$value" >/dev/null
  fi
}

# Host-provided vendor keys replace whatever is stored (so a key added to .env
# after the first `up` takes effect on the next `up`).
set_secret() {
  name="$1"
  value="$2"
  if aws secretsmanager describe-secret --secret-id "$name" >/dev/null 2>&1; then
    echo "[floci-init] updating secret $name"
    aws secretsmanager put-secret-value --secret-id "$name" --secret-string "$value" >/dev/null
  else
    echo "[floci-init] creating secret $name"
    aws secretsmanager create-secret --name "$name" --secret-string "$value" >/dev/null
  fi
}

ensure_bucket "$EVIDENCE_BUCKET"
ensure_bucket "$ANCHOR_BUCKET"

if [ -n "${LIVEAVATAR_API_KEY:-}" ]; then
  set_secret "actinver/liveavatar/api-key" "$LIVEAVATAR_API_KEY"
else
  ensure_secret "actinver/liveavatar/api-key" "sandbox-placeholder"
fi
ensure_secret "actinver/formspec-hmac" "$(random_hex)"
ensure_secret "actinver/suitability-hmac" "$(random_hex)"
if [ -n "${DEV_SIGNING_KEY:-}" ]; then
  set_secret "actinver/dev-signing-key" "$DEV_SIGNING_KEY"
else
  ensure_secret "actinver/dev-signing-key" "$(random_hex)"
fi
ensure_secret "actinver/client-hash-salt" "$(random_hex)"
if [ -n "${GEMINI_API_KEY:-}" ]; then
  set_secret "actinver/gemini-api-key" "$GEMINI_API_KEY"
fi

echo "[floci-init] done"

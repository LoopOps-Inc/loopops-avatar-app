#!/usr/bin/env bash
# Seed the local stack: migrations, Secrets Manager entries (floci) and the
# retrieval corpus (research notes, policy FAQ, disclosures - no client data).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> migrations"
docker compose run --rm migrate

echo "==> secrets (floci Secrets Manager)"
docker compose run --rm floci-init
docker compose run --rm --no-deps agent seed-secrets || echo "(seed-secrets: nothing extra to seed)"

echo "==> retrieval corpus (pgvector)"
docker compose run --rm --no-deps agent seed-retrieval

echo "==> done"

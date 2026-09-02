#!/usr/bin/env python
"""Generate a Postman environment for the local stack.

Writes ``docs/postman/local.postman_environment.json`` with a client token, a
compliance-officer token and the device public key (JWK) that
``POST /v1/sessions`` registers for the step-up signature. Tokens live 15
minutes at most (contract): re-run this script when they expire.

    .venv/bin/python scripts/postman_env.py [--client cl_demo_moderado]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "postman" / "local.postman_environment.json"


def _token(args: list[str]) -> dict:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "dev_token.py"), *args, "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", default="cl_demo_moderado")
    parser.add_argument("--base-url", default="http://localhost:8443")
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()

    client = _token(["--client", args.client])
    officer = _token(["--client", "officer_1", "--roles", "compliance,risk"])
    values = [
        {"key": "base_url", "value": args.base_url, "type": "default", "enabled": True},
        {"key": "token", "value": client["access_token"], "type": "default", "enabled": True},
        {"key": "officer_token", "value": officer["access_token"], "type": "default", "enabled": True},
        {"key": "device_jwk", "value": json.dumps(client["public_jwk"]), "type": "default", "enabled": True},
        {"key": "client_id", "value": args.client, "type": "default", "enabled": True},
        # filled by the requests' test scripts / by hand (step 5.2)
        {"key": "assertion", "value": "", "type": "default", "enabled": True},
    ]
    environment = {
        "id": str(uuid.uuid4()),
        "name": f"actinver-agent local ({args.client})",
        "values": values,
        "_postman_variable_scope": "environment",
        "_postman_exported_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "_postman_exported_using": "actinver-agent/scripts/postman_env.py",
    }
    Path(args.out).write_text(json.dumps(environment, indent=2, ensure_ascii=False))
    print(f"wrote {args.out}")
    print(f"client: {args.client}   tokens expire in 15 minutes - re-run to refresh")


if __name__ == "__main__":
    main()

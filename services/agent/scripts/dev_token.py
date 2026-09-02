#!/usr/bin/env python
"""Mint local development credentials.

Local only (AUTH_MODE=dev). Produces:

* an HS256 access token for a demo client (``sub`` = client_id, ``cnf.jkt``
  bound to a device key, optional ``roles``);
* a device key pair (P-256) persisted under ``~/.actinver-dev/`` so the same
  ``jkt`` is reused across runs - the step-up flow needs the registered key;
* optionally a DPoP proof (RFC 9449) for one method/URL;
* optionally a step-up assertion (ES256 signature over a server challenge).

Examples::

    python scripts/dev_token.py --client cl_demo_moderado --export
    python scripts/dev_token.py --client cl_demo_moderado --roles compliance,risk
    python scripts/dev_token.py --client cl_demo_moderado --dpop \
        --method POST --url http://localhost:8443/v1/sessions
    python scripts/dev_token.py --client cl_demo_moderado --sign-challenge "<base64 challenge>"

The signing key comes from ``DEV_SIGNING_KEY`` or from Secrets Manager
(``actinver/dev-signing-key`` at ``SECRETS_MANAGER_ENDPOINT``, floci locally).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from actinver_agent.auth import devkeys
except ImportError:  # pragma: no cover - the auth module is written by another workstream
    sys.stderr.write(
        "actinver_agent.auth.devkeys is not importable. Install the package "
        "(`uv pip install -e .[dev]`) and run from services/agent.\n"
    )
    raise

DEFAULT_KEY_DIR = Path(os.environ.get("ACTINVER_DEV_DIR", "~/.actinver-dev")).expanduser()


def _load_signing_key() -> str:
    key = os.environ.get("DEV_SIGNING_KEY")
    if key:
        return key
    endpoint = os.environ.get("SECRETS_MANAGER_ENDPOINT", "http://localhost:14566")
    try:
        import boto3
    except ImportError:
        sys.stderr.write(
            "Set DEV_SIGNING_KEY or install boto3 to fetch actinver/dev-signing-key "
            f"from {endpoint}.\n"
        )
        sys.exit(2)
    client = boto3.client(
        "secretsmanager",
        endpoint_url=endpoint,
        region_name=os.environ.get("SECRETS_MANAGER_REGION", "us-east-1"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
    )
    response = client.get_secret_value(SecretId="actinver/dev-signing-key")
    return str(response["SecretString"])


def _device_key(key_dir: Path) -> tuple[str, dict[str, object], str]:
    key_dir.mkdir(parents=True, exist_ok=True)
    pem_path = key_dir / "device.pem"
    jwk_path = key_dir / "device.jwk.json"
    if pem_path.exists() and jwk_path.exists():
        private_pem = pem_path.read_text()
        public_jwk = json.loads(jwk_path.read_text())
        jkt = str(public_jwk.get("_jkt") or devkeys.jwk_thumbprint(public_jwk))
        return private_pem, {k: v for k, v in public_jwk.items() if k != "_jkt"}, jkt
    private_pem, public_jwk, jkt = devkeys.generate_device_key()
    pem_path.write_text(private_pem)
    pem_path.chmod(0o600)
    jwk_path.write_text(json.dumps({**public_jwk, "_jkt": jkt}, indent=2))
    return private_pem, public_jwk, jkt


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--client", default="cl_demo_moderado", help="client_id (token subject)")
    parser.add_argument("--roles", default="", help="comma-separated roles, e.g. compliance,risk")
    parser.add_argument("--device-id", default="dev-device-1")
    parser.add_argument("--ttl", type=int, default=86400, help="token TTL seconds (default 86400 / 24h)")
    parser.add_argument("--dpop", action="store_true", help="also print a DPoP proof header")
    parser.add_argument("--method", default="POST", help="HTTP method for the DPoP proof")
    parser.add_argument(
        "--url", default="http://localhost:8443/v1/sessions", help="URL for the DPoP proof"
    )
    parser.add_argument("--sign-challenge", metavar="B64", help="sign a step-up challenge and exit")
    parser.add_argument("--export", action="store_true", help="print `export TOKEN=...` lines only")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="print only the token (or the signature with --sign-challenge)",
    )
    parser.add_argument("--key-dir", default=str(DEFAULT_KEY_DIR))
    args = parser.parse_args()

    private_pem, public_jwk, jkt = _device_key(Path(args.key_dir).expanduser())

    if args.sign_challenge:
        assertion = devkeys.sign_challenge(private_pem, args.sign_challenge)
        if args.json:
            print(json.dumps({"step_up_assertion": assertion, "jkt": jkt}))
        else:
            print(assertion)
        return

    roles = [r.strip() for r in args.roles.split(",") if r.strip()]
    token = devkeys.mint_dev_access_token(
        _load_signing_key(),
        args.client,
        roles=roles,
        jkt=jkt,
        device_id=args.device_id,
        ttl_s=args.ttl,
    )
    proof = None
    if args.dpop:
        proof = devkeys.make_dpop_proof(private_pem, public_jwk, args.method, args.url, token)

    if args.quiet:
        print(token)
        return
    if args.export:
        print(f"export TOKEN={token}")
        print(f"export JKT={jkt}")
        if proof:
            print(f"export DPOP={proof}")
        return
    if args.json:
        print(
            json.dumps({"access_token": token, "jkt": jkt, "dpop": proof, "public_jwk": public_jwk})
        )
        return
    print(f"client_id : {args.client}")
    print(f"roles     : {roles or '-'}")
    print(f"jkt       : {jkt}")
    print(f"token     : {token}")
    if proof:
        print(f"DPoP ({args.method} {args.url}):\n{proof}")
        print("\ncurl example:")
        print(
            f'  curl -H "Authorization: DPoP {token}" -H "DPoP: {proof}" -X {args.method} {args.url}'
        )
    else:
        print("\ncurl example:")
        print(f'  curl -H "Authorization: Bearer {token}" -X {args.method} {args.url}')


if __name__ == "__main__":
    main()

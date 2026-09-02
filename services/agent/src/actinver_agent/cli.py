"""Operational CLI: ``actinver-agent <command>``.

serve --role agent|suitability|guardrail|audit|transaction [--port N]
migrate                      alembic upgrade head
export-openapi --out DIR     write openapi JSON for every role
verify-chain --thread ID     re-walk a thread's hash chain
anchor                       publish chain heads to the external anchor
drain-spool                  write spooled informational evidence
retention                    run the retention/expiry jobs
seed-secrets                 write local dev secrets into the secrets manager (floci)
seed-retrieval               index the non-client retrieval corpus
dev-token                    mint a dev access token (+ device key, DPoP proof)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

ROLE_APPS: dict[str, str] = {
    "agent": "actinver_agent.main:app",
    "suitability": "actinver_agent.suitability.service:app",
    "guardrail": "actinver_agent.guardrails.service:app",
    "audit": "actinver_agent.audit.service:app",
    "transaction": "actinver_agent.transactions.service:app",
}


def _serve(args: argparse.Namespace) -> int:
    import uvicorn

    os.environ.setdefault("SERVICE_ROLE", args.role)
    port = args.port or int(os.environ.get("PORT", "8443"))
    uvicorn.run(
        ROLE_APPS[args.role],
        factory=args.role != "agent",
        host=args.host,
        port=port,
        workers=1,
        server_header=False,
        proxy_headers=True,
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
    )
    return 0


def _migrate(args: argparse.Namespace) -> int:
    from alembic import command
    from alembic.config import Config

    root = _migrations_root()
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(cfg, args.revision)

    # Automatically seed retrieval corpus on migration in local/dev
    try:
        from actinver_agent.retrieval.seed import seed_all

        async def _seed(deps: Any) -> None:
            await seed_all(deps)

        asyncio.run(_with_deps(_seed))
    except Exception as exc:
        print(f"(retrieval seed skipped: {exc})")

    return 0


def _migrations_root() -> Path:
    """alembic.ini + migrations/ live next to the source tree in a checkout and
    under /app in the container (Dockerfile). ``MIGRATIONS_ROOT`` overrides."""
    candidates = [
        Path(os.environ["MIGRATIONS_ROOT"]) if os.environ.get("MIGRATIONS_ROOT") else None,
        Path(__file__).resolve().parents[2],
        Path("/app"),
        Path.cwd(),
    ]
    for candidate in candidates:
        if (
            candidate is not None
            and (candidate / "alembic.ini").exists()
            and (candidate / "migrations").is_dir()
        ):
            return candidate
    raise SystemExit("alembic.ini/migrations not found; set MIGRATIONS_ROOT")


def _export_openapi(args: argparse.Namespace) -> int:
    from actinver_agent.config import get_settings

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    from actinver_agent.api.app import create_app

    (out / "agent.openapi.json").write_text(
        json.dumps(create_app(settings=settings).openapi(), indent=2, ensure_ascii=False)
    )
    written = ["agent.openapi.json"]
    for role in ("suitability", "guardrail", "audit", "transaction"):
        try:
            app = _openapi_app_for(role, settings)
            (out / f"{role}.openapi.json").write_text(
                json.dumps(app.openapi(), indent=2, ensure_ascii=False)
            )
            written.append(f"{role}.openapi.json")
        except Exception as exc:
            print(f"skipping {role}: {type(exc).__name__}: {exc}", file=sys.stderr)
    print("\n".join(str(out / w) for w in written))
    return 0


async def _with_deps(fn: Any) -> int:
    from actinver_agent.config import get_settings
    from actinver_agent.wiring import build_dependencies

    deps = await build_dependencies(get_settings())
    try:
        return int(await fn(deps) or 0)
    finally:
        await deps.aclose()


def _verify_chain(args: argparse.Namespace) -> int:
    async def run(deps: Any) -> int:
        verifier = getattr(deps.audit, "verify_thread", None)
        if verifier is None:
            print("chain verification is not available for this audit adapter", file=sys.stderr)
            return 2
        ok, records, divergent = await verifier(args.thread)
        print(
            json.dumps(
                {
                    "thread_id": args.thread,
                    "ok": ok,
                    "records": records,
                    "first_divergent_evidence_id": divergent,
                }
            )
        )
        return 0 if ok else 1

    return asyncio.run(_with_deps(run))


def _anchor(_: argparse.Namespace) -> int:
    async def run(deps: Any) -> int:
        from actinver_agent.audit.sink import anchor_heads

        count = await anchor_heads(deps)
        print(json.dumps({"anchored_threads": count}))
        return 0

    return asyncio.run(_with_deps(run))


def _drain_spool(_: argparse.Namespace) -> int:
    async def run(deps: Any) -> int:
        from actinver_agent.audit.sink import drain_spool

        count = await drain_spool(deps)
        print(json.dumps({"drained": count}))
        return 0

    return asyncio.run(_with_deps(run))


def _retention(_: argparse.Namespace) -> int:
    async def run(deps: Any) -> int:
        from actinver_agent.persistence.retention import run_retention

        report = await run_retention(deps)
        print(json.dumps(report, default=str))
        return 0

    return asyncio.run(_with_deps(run))


def _seed_secrets(args: argparse.Namespace) -> int:
    async def run() -> int:
        import secrets as pysecrets

        from actinver_agent.adapters.aws_secrets import AwsSecretsManager
        from actinver_agent.config import get_settings

        settings = get_settings()
        manager = AwsSecretsManager(
            endpoint=settings.secrets.manager_endpoint,
            region=settings.secrets.manager_region,
            access_key=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
            secret_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
        )
        values = {
            "actinver/liveavatar/api-key": args.liveavatar_api_key or "sandbox-not-a-real-key",
            "actinver/formspec-hmac": pysecrets.token_hex(32),
            "actinver/suitability-hmac": pysecrets.token_hex(32),
            "actinver/auth/dev-signing-key": pysecrets.token_hex(32),
            "actinver/client-hash-salt": pysecrets.token_hex(16),
        }
        for name, value in values.items():
            await manager.put_secret(name, value)
            print(f"seeded {name}")
        return 0

    return asyncio.run(run())


def _seed_retrieval(_: argparse.Namespace) -> int:
    async def run(deps: Any) -> int:
        from actinver_agent.retrieval.seed import seed_all

        count = await seed_all(deps)
        print(json.dumps({"chunks_indexed": count}))
        return 0

    return asyncio.run(_with_deps(run))


def _dev_token(args: argparse.Namespace) -> int:
    from actinver_agent.auth import devkeys

    key = args.key or os.environ.get("AUTH_DEV_SIGNING_KEY")
    if not key:
        print("provide --key or AUTH_DEV_SIGNING_KEY", file=sys.stderr)
        return 2
    private_pem, public_jwk, jkt = devkeys.generate_device_key()
    token = devkeys.mint_dev_access_token(
        key,
        args.client_id,
        roles=args.roles,
        jkt=jkt if args.dpop else None,
        device_id=args.device_id,
        ttl_s=args.ttl,
    )
    out: dict[str, Any] = {"access_token": token, "client_id": args.client_id}
    if args.dpop:
        out.update(
            {"device_private_key_pem": private_pem, "device_public_jwk": public_jwk, "jkt": jkt}
        )
        if args.url:
            out["dpop_proof"] = devkeys.make_dpop_proof(
                private_pem, public_jwk, args.method, args.url, token
            )
    print(json.dumps(out, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="actinver-agent")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="run one service role")
    serve.add_argument(
        "--role", choices=sorted(ROLE_APPS), default=os.environ.get("SERVICE_ROLE", "agent")
    )
    serve.add_argument("--port", type=int, default=None)
    serve.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))  # noqa: S104
    serve.set_defaults(fn=_serve)

    migrate = sub.add_parser("migrate", help="alembic upgrade")
    migrate.add_argument("--revision", default="head")
    migrate.set_defaults(fn=_migrate)

    export = sub.add_parser("export-openapi", help="write OpenAPI documents")
    export.add_argument("--out", default="docs/openapi")
    export.set_defaults(fn=_export_openapi)

    verify = sub.add_parser("verify-chain", help="re-walk a thread's evidence chain")
    verify.add_argument("--thread", required=True)
    verify.set_defaults(fn=_verify_chain)

    sub.add_parser("anchor", help="publish chain heads to the external anchor").set_defaults(
        fn=_anchor
    )
    sub.add_parser("drain-spool", help="write spooled evidence").set_defaults(fn=_drain_spool)
    sub.add_parser("retention", help="run retention jobs").set_defaults(fn=_retention)

    seed = sub.add_parser("seed-secrets", help="seed local dev secrets into the secrets manager")
    seed.add_argument("--liveavatar-api-key", default=None)
    seed.set_defaults(fn=_seed_secrets)

    sub.add_parser("seed-retrieval", help="index the retrieval corpus").set_defaults(
        fn=_seed_retrieval
    )

    token = sub.add_parser("dev-token", help="mint a dev access token")
    token.add_argument("--client-id", default="cl_demo_moderado")
    token.add_argument("--roles", nargs="*", default=[])
    token.add_argument("--device-id", default="dev-device-1")
    token.add_argument("--ttl", type=int, default=900)
    token.add_argument("--key", default=None)
    token.add_argument("--dpop", action="store_true")
    token.add_argument("--method", default="POST")
    token.add_argument("--url", default=None)
    token.set_defaults(fn=_dev_token)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.fn(args))


def _openapi_app_for(role: str, settings: Any) -> Any:
    """Control-service apps over memory doubles, for schema export only."""
    from actinver_agent.persistence import memory

    if role == "suitability":
        from actinver_agent.suitability.engine import SuitabilityEngine
        from actinver_agent.suitability.service import create_app

        return create_app(SuitabilityEngine(settings.suitability_ruleset_version, b"openapi-only"))
    if role == "guardrail":
        from actinver_agent.guardrails.service import create_app as guardrail_app

        return guardrail_app(prompts_dir=settings.prompts_dir)
    from actinver_agent.audit.inprocess import InProcessAudit
    from actinver_agent.audit.sink import EvidenceWriter

    writer = EvidenceWriter(
        store=memory.MemoryObjectStore(),
        chain=memory.MemoryChainStore(),
        index=memory.MemoryEvidenceIndexRepository(),
        spool=memory.MemorySpool(),
    )
    if role == "audit":
        from actinver_agent.audit.service import create_app as audit_app

        return audit_app(
            writer,
            access_log=memory.MemoryAccessLogRepository(),
            anchor_store=memory.MemoryObjectStore(),
        )
    from actinver_agent.clients.synthetic import SyntheticCoreBanking, SyntheticOms
    from actinver_agent.transactions.executor import TransactionExecutor
    from actinver_agent.transactions.service import create_app as tx_app

    return tx_app(
        TransactionExecutor(
            core=SyntheticCoreBanking(),
            oms=SyntheticOms(),
            form_specs=memory.MemoryFormSpecRepository(),
            idempotency=memory.MemoryIdempotencyRepository(),
            challenges=memory.MemoryChallengeRepository(),
            devices=memory.MemoryDeviceRepository(),
            audit=InProcessAudit(writer),
            form_key=b"openapi-only",
        )
    )


if __name__ == "__main__":
    sys.exit(main())

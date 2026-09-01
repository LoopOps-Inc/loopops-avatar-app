"""Evidence record assembly - the DCGSI Art. 26 artefact (ADR-0012,
docs/01-architecture/04 §4). One record per turn, assembled from typed graph
state, never from loose dicts.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from datetime import UTC, datetime
from typing import Any

import orjson

from actinver_agent.graph.state import SERVICE_SUBTYPE, AdvisorState, Intent

SCHEMA_VERSION = "1.0"
RETENTION_CLASS = "DCGSI_ART26"


def new_evidence_id(now: datetime | None = None) -> str:
    """Time-ordered, unique: ``ev_<ms-since-epoch hex><80 random bits hex>``."""
    ts = int((now or datetime.now(UTC)).timestamp() * 1000)
    return f"ev_{ts:012x}{secrets.token_hex(10)}"


def canonical_hash(record: dict[str, Any]) -> str:
    """``sha256(canonical_json(record without chain.content_hash))``, independently
    recomputable by an auditor."""
    body = {k: v for k, v in record.items() if k != "chain"}
    chain = record.get("chain", {})
    body["chain"] = {k: v for k, v in chain.items() if k != "content_hash"}
    return hashlib.sha256(orjson.dumps(body, option=orjson.OPT_SORT_KEYS)).hexdigest()


def chain_fields(prev_hash: str | None) -> dict[str, Any]:
    return {"prev_hash": prev_hash, "algo": "sha256"}


def hash_payload(payload: Any) -> str:
    return hashlib.sha256(
        orjson.dumps(payload, option=orjson.OPT_SORT_KEYS, default=str)
    ).hexdigest()


def retention_for(created_at: datetime, *, years: int = 5) -> dict[str, Any]:
    expires = created_at.replace(year=created_at.year + years)
    return {"class": RETENTION_CLASS, "expires_at": expires.isoformat(), "legal_hold": False}


def build_record(
    state: AdvisorState,
    *,
    model_meta: dict[str, Any] | None,
    prompt_version: str,
    ruleset_version: int,
    disclosures_shown: dict[str, str] | None = None,
    client_input: dict[str, Any] | None = None,
    audio_refs: dict[str, str | None] | None = None,
    created_at: datetime | None = None,
    retention_years: int = 5,
) -> dict[str, Any]:
    """Assemble the evidence record from graph state.

    ``chain.content_hash`` is filled by the writer once ``prev_hash`` is known.
    """
    now = created_at or datetime.now(UTC)
    intent = state.get("intent")
    intent_str = str(intent) if intent else None
    subtype = state.get("service_subtype") or (
        SERVICE_SUBTYPE.get(intent, "informacion") if isinstance(intent, Intent) else "informacion"
    )
    suitability = state.get("suitability")
    profile = state.get("investor_profile")
    ui_payload = [c.model_dump(mode="json") for c in state.get("ui_payload", [])]
    audio_refs = audio_refs or {}
    error = state.get("error")
    form_spec = state.get("form_spec")
    refusal = (
        {"code": error.code, "message_es": error.message_es, "escalate": error.escalate}
        if error is not None
        else None
    )

    record: dict[str, Any] = {
        "evidence_id": new_evidence_id(now),
        "schema_version": SCHEMA_VERSION,
        "thread_id": state["thread_id"],
        "turn_id": state["turn_id"],
        "client_id": state["client_id"],
        "created_at": now.isoformat(),
        "channel": state.get("channel", "chat"),
        "service_type": state.get("service_type", "no_asesorado"),
        "refusal": refusal,
        "service_subtype": subtype,
        "intent": intent_str,
        "intent_confidence": state.get("intent_confidence"),
        "degraded_from": str(state["degraded_from"]) if state.get("degraded_from") else None,
        "profile_filtered": bool(state.get("profile_filtered", False)),
        "client_input": client_input
        or {
            "modality": "audio" if state.get("channel") == "voice" else "text",
            "audio_ref": audio_refs.get("client") or state.get("audio_ref"),
            "transcript": state.get("client_input_text", ""),
            "asr_confidence": state.get("transcript_confidence"),
            "language": state.get("locale", "es-MX"),
        },
        "profile_snapshot": profile.model_dump(mode="json") if profile else None,
        "entitlements": (
            state["entitlements"].model_dump(mode="json") if state.get("entitlements") else None
        ),
        "tool_calls": [
            {
                "name": r.name,
                "args_hash": r.args_hash,
                "result_hash": r.result_hash,
                "latency_ms": r.latency_ms,
                "status": "ok" if r.ok else f"error:{r.error}",
                "cache_hit": r.cache_hit,
                "as_of": r.as_of.isoformat() if r.as_of else None,
                "classification": r.classification,
            }
            for r in state.get("tool_results", {}).values()
        ],
        "candidate_products": [p.product_id for p in state.get("candidate_products", [])],
        "stripped_products": [p.product_id for p in state.get("stripped_products", [])],
        "suitability": (
            {
                "ruleset_version": suitability.ruleset_version,
                "verdict_id": suitability.verdict_id,
                "profile_id": suitability.profile_id,
                "profile_version": suitability.profile_version,
                "amount": suitability.amount,
                "evaluated_at": suitability.evaluated_at.isoformat(),
                "evaluations": [e.model_dump(mode="json") for e in suitability.evaluations],
                "verdict_signature": suitability.signature,
                "signing_key_version": suitability.signing_key_version,
            }
            if suitability
            else None
        ),
        "model": {
            "provider": (model_meta or {}).get("provider", "none"),
            "model": (model_meta or {}).get("model"),
            "prompt_version": prompt_version,
            "temperature": (model_meta or {}).get("temperature"),
            "seed": (model_meta or {}).get("seed"),
            "input_tokens": (model_meta or {}).get("input_tokens", 0),
            "output_tokens": (model_meta or {}).get("output_tokens", 0),
            "ttft_ms": (model_meta or {}).get("ttft_ms"),
            "router_model": (model_meta or {}).get("router_model"),
            "safety_verdicts": {"blocked": bool((model_meta or {}).get("safety_blocked", False))},
        },
        "ruleset_version": ruleset_version,
        "guardrails": {
            "input": (gi.model_dump(mode="json") if (gi := state.get("guardrail_input")) else None),
            "output": (
                go.model_dump(mode="json") if (go := state.get("guardrail_output")) else None
            ),
            "rewrite_attempts": state.get("rewrite_attempts", 0),
        },
        "response": {
            "speech": state.get("speech"),
            "speech_audio_ref": audio_refs.get("avatar"),
            "ui_payload_hash": hash_payload(ui_payload),
            "ui_payload": ui_payload,
            "citations": [c.model_dump(mode="json") for c in state.get("citations", [])],
            "disclosures": dict(disclosures_shown or state.get("disclosures_shown", {}) or {}),
            "error": error.model_dump(mode="json") if error else None,
            "refused": error is not None,
        },
        "form_spec": form_spec.model_dump(mode="json") if form_spec else None,
        "submission": state.get("submission"),
        "receipt": state.get("receipt"),
        "timing": {
            "started_at": state.get("started_at"),
            "elapsed_ms": int(
                (time.time() - datetime.fromisoformat(state["started_at"]).timestamp()) * 1000
            )
            if state.get("started_at")
            else None,
        },
        "retention": retention_for(now, years=retention_years),
    }
    return record


def product_ids_in(record: dict[str, Any]) -> list[str]:
    ids: list[str] = list(record.get("candidate_products") or [])
    suitability = record.get("suitability") or {}
    for e in suitability.get("evaluations", []):
        if e["product_id"] not in ids:
            ids.append(e["product_id"])
    spec = record.get("form_spec") or {}
    if spec.get("product", {}).get("id") and spec["product"]["id"] not in ids:
        ids.append(spec["product"]["id"])
    return ids

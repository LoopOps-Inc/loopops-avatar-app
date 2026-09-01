"""Telemetry bootstrap (ADR-0016).

Attribute discipline is structural: the ``_drop_content`` processor redacts
known content field names from every log line regardless of what a caller
passes, and ``span_attributes`` filters span attributes the same way.
``client_id`` appears only as a salted hash. Prompts and responses live in
Langfuse inside the perimeter, never in OTel spans.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from collections.abc import Iterator, Mapping, MutableMapping
from contextlib import contextmanager
from typing import Any

import structlog
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_FORBIDDEN_KEYS = frozenset(
    {
        "prompt",
        "response",
        "speech",
        "transcript",
        "client_id",
        "message",
        "text",
        "content",
        "values",
        "first_name",
        "email",
        "phone",
        "rfc",
        "curp",
        "clabe",
        "audio",
        "ui_payload",
        "form_values",
    }
)

_client_hash_salt: bytes = b"unsalted-local"


def configure_logging(level: str = "INFO") -> None:
    numeric = logging.getLevelName(level.upper())
    if not isinstance(numeric, int):
        numeric = logging.INFO
    logging.basicConfig(level=numeric, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _drop_content,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric),
        cache_logger_on_first_use=False,
    )


def configure_tracing(service_name: str, otlp_endpoint: str) -> None:
    resource = Resource.create({"service.name": service_name})
    tracer_provider = TracerProvider(resource=resource)
    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True))
        )
        metrics.set_meter_provider(
            MeterProvider(
                resource=resource,
                metric_readers=[
                    PeriodicExportingMetricReader(
                        OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True)
                    )
                ],
            )
        )
    else:
        metrics.set_meter_provider(MeterProvider(resource=resource))
    trace.set_tracer_provider(tracer_provider)


def set_client_hash_salt(salt: bytes) -> None:
    global _client_hash_salt
    _client_hash_salt = salt


def client_hash(client_id: str) -> str:
    """Salted hash: the only form in which a client identifier may appear in
    telemetry (docs/04-backend/05 §3)."""
    return hmac.new(_client_hash_salt, client_id.encode(), hashlib.sha256).hexdigest()[:16]


def _drop_content(
    _logger: Any, _name: str, event: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key in _FORBIDDEN_KEYS & event.keys():
        event[key] = "[REDACTED]"
    return event


def span_attributes(attrs: Mapping[str, Any]) -> dict[str, Any]:
    """Keep identifiers, categories, durations and counts; drop content."""
    clean: dict[str, Any] = {}
    for key, value in attrs.items():
        if key in _FORBIDDEN_KEYS or value is None:
            continue
        if isinstance(value, (str, bool, int, float)):
            clean[key] = value
        elif isinstance(value, (list, tuple)):
            clean[key] = [str(v) for v in value][:20]
        else:
            clean[key] = str(value)
    return clean


@contextmanager
def node_span(name: str, **attrs: Any) -> Iterator[trace.Span]:
    """One span per graph node, named per the ADR-0016 instrumentation contract."""
    tracer = trace.get_tracer("actinver_agent")
    with tracer.start_as_current_span(name, attributes=span_attributes(attrs)) as span:
        yield span


class Metrics:
    """Golden signals from docs/04-backend/05 and ADR-0016."""

    def __init__(self) -> None:
        meter = metrics.get_meter("actinver_agent")
        self.turn_latency_first_audio_ms = meter.create_histogram(
            "turn.latency.first_audio_ms", unit="ms"
        )
        self.turn_latency_first_token_ms = meter.create_histogram(
            "turn.latency.first_token_ms", unit="ms"
        )
        self.turn_total_ms = meter.create_histogram("turn.latency.total_ms", unit="ms")
        self.turns = meter.create_counter("turn.count")
        self.guardrail_blocks = meter.create_counter("guardrail.block_count")
        self.guardrail_rewrites = meter.create_counter("guardrail.rewrite_count")
        self.suitability_outcomes = meter.create_counter("suitability.outcome_count")
        self.tool_calls = meter.create_counter("tool.call_count")
        self.tool_errors = meter.create_counter("tool.error_count")
        self.tool_latency_ms = meter.create_histogram("tool.latency_ms", unit="ms")
        self.escalations = meter.create_counter("escalation.count")
        self.evidence_write_failures = meter.create_counter("evidence.write_failure")
        self.evidence_write_ms = meter.create_histogram("evidence.write_ms", unit="ms")
        self.model_tokens = meter.create_counter("model.tokens")
        self.model_ttft_ms = meter.create_histogram("model.ttft_ms", unit="ms")
        self.asr_confidence = meter.create_histogram("asr.confidence")
        self.avatar_session_duration_s = meter.create_histogram(
            "avatar.session.duration_seconds", unit="s"
        )
        self.avatar_session_speaking_s = meter.create_histogram(
            "avatar.session.speaking_seconds", unit="s"
        )
        self.avatar_first_frame_ms = meter.create_histogram("avatar.first_frame_ms", unit="ms")
        self.avatar_session_starts = meter.create_counter("avatar.session.start_count")
        self.avatar_session_start_failures = meter.create_counter(
            "avatar.session.start_failure_count"
        )
        self.avatar_credits = meter.create_counter("avatar.credits_consumed")
        self.barge_ins = meter.create_counter("voice.barge_in_count")
        self.dlp_hits = meter.create_counter("egress.dlp_hit_count")
        self.auth_failures = meter.create_counter("auth.failure_count")
        self.rate_limited = meter.create_counter("ingress.rate_limited_count")
        self.kill_switch_refusals = meter.create_counter("kill_switch.refusal_count")


_metrics: Metrics | None = None


def get_metrics() -> Metrics:
    global _metrics
    if _metrics is None:
        _metrics = Metrics()
    return _metrics

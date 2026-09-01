"""Shared HTTP client discipline for tool-gateway clients (docs/04-backend/02 §3).

* Retry only idempotent reads, only on transport errors, two attempts with
  exponential backoff and jitter. A 4xx is never retried.
* Every await has a timeout.
* Every response is validated by a Pydantic model at the boundary; a raw
  ``.json()`` never leaves ``clients/``.
* Separate connection pools per upstream (bulkheads): the core-banking pool is
  never shared with news or market data.
"""

from __future__ import annotations

import ssl
from typing import Any, TypeVar

import httpx
import structlog
from pydantic import BaseModel
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

log = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class UpstreamError(RuntimeError):
    def __init__(self, upstream: str, status: int | None, detail: str) -> None:
        super().__init__(f"{upstream}: {detail}")
        self.upstream = upstream
        self.status = status


class UpstreamUnavailable(UpstreamError):
    pass


def mtls_context(cert_path: str, key_path: str, ca_path: str) -> ssl.SSLContext:
    ctx = ssl.create_default_context(cafile=ca_path)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
    ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
    return ctx


class JsonClient:
    def __init__(
        self,
        *,
        name: str,
        base_url: str,
        timeout_s: float = 3.0,
        verify: ssl.SSLContext | bool = True,
        headers: dict[str, str] | None = None,
        max_connections: int = 20,
    ) -> None:
        self.name = name
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_s, connect=min(timeout_s, 1.0)),
            verify=verify,
            headers=headers or {},
            limits=httpx.Limits(
                max_connections=max_connections, max_keepalive_connections=max_connections // 2
            ),
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def get_model(
        self, path: str, model: type[T], *, params: dict[str, Any] | None = None
    ) -> T:
        response = await self._request("GET", path, params=params, retry=True)
        return model.model_validate(response.json())

    async def post_model(
        self,
        path: str,
        model: type[T],
        *,
        json: dict[str, Any],
        retry: bool = False,
        headers: dict[str, str] | None = None,
    ) -> T:
        response = await self._request("POST", path, json=json, retry=retry, headers=headers)
        return model.model_validate(response.json())

    async def _request(
        self,
        method: str,
        path: str,
        *,
        retry: bool,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        attempts = 2 if retry else 1
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(attempts),
                wait=wait_exponential_jitter(initial=0.2, max=1.0),
                retry=retry_if_exception_type(httpx.TransportError),
                reraise=True,
            ):
                with attempt:
                    response = await self._http.request(
                        method, path, params=params, json=json, headers=headers
                    )
                    if response.status_code >= 500:
                        raise UpstreamUnavailable(self.name, response.status_code, "upstream 5xx")
                    if response.status_code >= 400:
                        # Never retried; never log the body (it may echo the request).
                        raise UpstreamError(self.name, response.status_code, "upstream 4xx")
                    return response
        except httpx.TransportError as exc:
            log.warning("upstream.transport_error", upstream=self.name, error=type(exc).__name__)
            raise UpstreamUnavailable(self.name, None, type(exc).__name__) from exc
        raise UpstreamUnavailable(self.name, None, "no response")  # pragma: no cover

    async def health(self, path: str = "/healthz") -> bool:
        try:
            response = await self._http.get(path, timeout=1.0)
        except httpx.HTTPError:
            return False
        return response.is_success

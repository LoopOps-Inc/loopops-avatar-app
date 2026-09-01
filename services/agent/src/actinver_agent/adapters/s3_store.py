"""S3-compatible object store adapter (ADR-0011 ``ObjectStore`` interface).

WORM tier: ``put_immutable`` sets an object-lock retention at write time
(COMPLIANCE in production, GOVERNANCE in staging/local - ADR-0012). Locally the
endpoint is floci (``http://localhost:4566``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import aioboto3
import structlog
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

log = structlog.get_logger(__name__)


class S3ObjectStore:
    def __init__(
        self,
        *,
        endpoint: str,
        region: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        lock_mode: str = "GOVERNANCE",
        timeout_s: float = 5.0,
    ) -> None:
        self._endpoint = endpoint or None
        self._region = region
        self._bucket = bucket
        self._access_key = access_key
        self._secret_key = secret_key
        self._lock_mode = lock_mode
        self._session = aioboto3.Session()
        self._config = Config(
            connect_timeout=timeout_s,
            read_timeout=timeout_s,
            retries={"max_attempts": 2},
            s3={"addressing_style": "path"},
        )

    def _client(self) -> Any:
        return self._session.client(
            "s3",
            endpoint_url=self._endpoint,
            region_name=self._region,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            config=self._config,
        )

    async def ensure_bucket(self, *, object_lock: bool = True) -> None:
        """Create the bucket with object lock enabled (idempotent). Used by the
        local init script and integration tests, never on the request path."""
        async with self._client() as s3:
            try:
                await s3.head_bucket(Bucket=self._bucket)
                return
            except ClientError:
                pass
            params: dict[str, Any] = {"Bucket": self._bucket}
            if object_lock:
                params["ObjectLockEnabledForBucket"] = True
            if self._region != "us-east-1":
                params["CreateBucketConfiguration"] = {"LocationConstraint": self._region}
            await s3.create_bucket(**params)
            if object_lock:
                try:
                    await s3.put_bucket_versioning(
                        Bucket=self._bucket, VersioningConfiguration={"Status": "Enabled"}
                    )
                    await s3.put_object_lock_configuration(
                        Bucket=self._bucket,
                        ObjectLockConfiguration={
                            "ObjectLockEnabled": "Enabled",
                            "Rule": {"DefaultRetention": {"Mode": self._lock_mode, "Years": 5}},
                        },
                    )
                except ClientError as exc:  # emulators differ in coverage
                    log.warning(
                        "s3.object_lock_config_unsupported",
                        error=str(exc.response.get("Error", {}).get("Code")),
                    )

    async def put_immutable(
        self, key: str, body: bytes, *, retain_until: datetime, content_type: str
    ) -> None:
        if retain_until.tzinfo is None:
            retain_until = retain_until.replace(tzinfo=UTC)
        async with self._client() as s3:
            await s3.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
                ObjectLockMode=self._lock_mode,
                ObjectLockRetainUntilDate=retain_until,
                Metadata={"retention-class": "DCGSI_ART26"},
            )

    async def put_expiring(
        self, key: str, body: bytes, *, expires_at: datetime, content_type: str
    ) -> None:
        async with self._client() as s3:
            await s3.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
                Expires=expires_at,
                Tagging=f"expires_at={expires_at.strftime('%Y-%m-%dT%H-%M-%SZ')}",
            )

    async def get(self, key: str) -> bytes | None:
        async with self._client() as s3:
            try:
                response = await s3.get_object(Bucket=self._bucket, Key=key)
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "404"}:
                    return None
                raise
            async with response["Body"] as stream:
                data: bytes = await stream.read()
                return data

    async def list_keys(self, prefix: str) -> list[str]:
        keys: list[str] = []
        async with self._client() as s3:
            paginator = s3.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                keys.extend(obj["Key"] for obj in page.get("Contents", []))
        return sorted(keys)

    async def set_legal_hold(self, key: str, *, on: bool) -> None:
        async with self._client() as s3:
            await s3.put_object_legal_hold(
                Bucket=self._bucket, Key=key, LegalHold={"Status": "ON" if on else "OFF"}
            )

    async def presign_get(self, key: str, *, ttl_s: int) -> str:
        async with self._client() as s3:
            url: str = await s3.generate_presigned_url(
                "get_object", Params={"Bucket": self._bucket, "Key": key}, ExpiresIn=ttl_s
            )
            return url

    async def health(self) -> bool:
        try:
            async with self._client() as s3:
                await s3.head_bucket(Bucket=self._bucket)
            return True
        except (ClientError, BotoCoreError, OSError):
            return False

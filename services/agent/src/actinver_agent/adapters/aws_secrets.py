"""AWS Secrets Manager adapter (floci locally; the real service or the
External Secrets Operator's source in Kubernetes)."""

from __future__ import annotations

from typing import Any

import aioboto3
from botocore.config import Config
from botocore.exceptions import ClientError


class AwsSecretsManager:
    def __init__(
        self,
        *,
        endpoint: str,
        region: str,
        access_key: str,
        secret_key: str,
        timeout_s: float = 5.0,
    ) -> None:
        self._endpoint = endpoint or None
        self._region = region
        self._access_key = access_key
        self._secret_key = secret_key
        self._session = aioboto3.Session()
        self._config = Config(
            connect_timeout=timeout_s, read_timeout=timeout_s, retries={"max_attempts": 2}
        )

    def _client(self) -> Any:
        return self._session.client(
            "secretsmanager",
            endpoint_url=self._endpoint,
            region_name=self._region,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            config=self._config,
        )

    async def get(self, name: str) -> str:
        async with self._client() as sm:
            response = await sm.get_secret_value(SecretId=name)
        if "SecretString" in response:
            return str(response["SecretString"])
        binary: bytes = response["SecretBinary"]
        return binary.decode("utf-8")

    async def put_secret(self, name: str, value: str) -> None:
        """Create or update (seed scripts only; never on the request path)."""
        async with self._client() as sm:
            try:
                await sm.create_secret(Name=name, SecretString=value)
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") != "ResourceExistsException":
                    raise
                await sm.put_secret_value(SecretId=name, SecretString=value)

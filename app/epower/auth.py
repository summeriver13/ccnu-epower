"""SM2-signed JWT login for the JSON API."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import time
from typing import Any, Optional

import requests
from gmssl import sm2

from .config import API_BASE, REQUEST_TIMEOUT_SECONDS, Credentials
from .errors import AuthError, NetworkError, ParseError

logger = logging.getLogger("ccnu_epower")

# Uncompressed public key published by the platform (04 || x || y).
# gmssl expects the 64-byte key without the 04 prefix.
SM2_PUBLIC_KEY_HEX = (
    "b238b7d42c87a25e1a4eaddca81e8f33fd95773ccd471408e4195db62aa4085f"
    "6e0a3b695cad8d60acece1af348f534b7f72d312f2966b144248c9c590c930fc"
)

JWT_EXPIRY_MARGIN_SECONDS = 60


def decode_jwt_payload(token: str) -> dict[str, Any]:
    """Decode the payload section of a JWT without verifying its signature."""
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except (ValueError, TypeError, AttributeError):
        logger.debug("Failed to decode JWT payload", exc_info=True)
        return {}


class SM2Auth:
    """Obtains and caches the bearer token required by the JSON API."""

    def __init__(self, session: requests.Session, credentials: Credentials) -> None:
        self._session = session
        self._credentials = credentials
        self._jwt: Optional[str] = None
        self._shared: Optional[tuple[str, str]] = None
        self._sm2 = sm2.CryptSM2(
            public_key=SM2_PUBLIC_KEY_HEX,
            private_key="",
            mode=1,  # C1C3C2 cipher format required by the platform
        )

    def generate_signature(self) -> str:
        """Build the signed query string for the login endpoint."""
        account_id, account_pass = self._login_credentials()
        timestamp = int(time.time())
        digest = hashlib.md5(account_pass.encode()).hexdigest()
        sys_id = self._credentials.sys_id
        query = f"p1={account_id}&p2={digest}&p3={sys_id}&t={timestamp}"
        cipher_bytes = self._sm2.encrypt(query.encode())
        if cipher_bytes is None:
            raise AuthError("SM2 加密失败：encrypt() 返回 None")
        return f"{query}&s={cipher_bytes.hex()}"

    def _login_credentials(self) -> tuple[str, str]:
        """Return the account that signs in, loading the shared one on demand."""
        if self._credentials.account_pass:
            return self._credentials.account_id, self._credentials.account_pass
        if self._shared is None:
            self._shared = self._fetch_shared_account()
        return self._shared

    def _fetch_shared_account(self) -> tuple[str, str]:
        """Read the platform-wide account that the web frontend logs in with."""
        url = f"{API_BASE}/v1/Authentication/GetAP?id={self._credentials.sys_id}"
        try:
            response = self._session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise NetworkError(f"获取共享账号失败：{exc}") from exc
        except ValueError as exc:
            raise ParseError(f"共享账号响应解析失败：{exc}") from exc

        data = payload.get("Data")
        if not isinstance(data, dict):
            raise ParseError(f"共享账号响应 Data 字段类型异常：{type(data).__name__}")
        decryptor = sm2.CryptSM2(
            private_key=self._credentials.app_private_key, public_key="", mode=1
        )
        try:
            account_id = decryptor.decrypt(bytes.fromhex(data["P1"])).decode()
            account_pass = decryptor.decrypt(bytes.fromhex(data["P2"])).decode()
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ParseError(f"共享账号解密失败：{exc}") from exc
        if not account_id or not account_pass:
            raise AuthError("共享账号解密结果为空：请检查平台返回的数据")
        logger.info("Shared platform account loaded")
        return account_id, account_pass

    def get_jwt(self) -> str:
        """Return a valid token, logging in again when the cached one expired."""
        if self._is_cache_valid():
            assert self._jwt is not None
            return self._jwt
        signed_query = self.generate_signature()
        url = f"{API_BASE}/v3/XINTFLg/SpecialSignIn?{signed_query}"
        try:
            response = self._session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise NetworkError(f"JWT 认证请求失败：{exc}") from exc
        except ValueError as exc:
            raise ParseError(f"JWT 响应解析失败：{exc}") from exc

        code = payload.get("Code")
        if code != 0:
            raise AuthError(
                f"JWT 认证失败：Code={code}，{payload.get('Mess', '未知错误')}"
            )

        data = payload.get("Data", {})
        if isinstance(data, dict):
            token = data.get("access_Jwt", "")
        elif isinstance(data, str):
            token = data
        else:
            raise ParseError(f"JWT 认证响应 Data 字段类型异常：{type(data).__name__}")
        if not token:
            reason = data.get("Msg") if isinstance(data, dict) else ""
            raise AuthError(f"JWT 认证失败：{reason or '响应中未找到 access_Jwt'}")
        self._jwt = token
        logger.info("JWT obtained successfully")
        return token

    def get_auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.get_jwt()}"}

    def refresh_jwt(self) -> str:
        self._jwt = None
        return self.get_jwt()

    def _is_cache_valid(self) -> bool:
        if not self._jwt:
            return False
        expires_at = decode_jwt_payload(self._jwt).get("exp", 0)
        if not expires_at:
            return False
        if time.time() < (expires_at - JWT_EXPIRY_MARGIN_SECONDS):
            return True
        logger.info("Cached JWT expired or expiring soon, re-authenticating")
        return False

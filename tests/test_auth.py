import base64
import json

import pytest

from epower import auth
from epower.auth import SM2Auth, decode_jwt_payload
from epower.config import Credentials
from epower.errors import AuthError


def make_token(payload: dict) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"header.{body}.signature"


def test_decode_jwt_payload_roundtrip():
    assert decode_jwt_payload(make_token({"exp": 123})) == {"exp": 123}


def test_decode_invalid_token_returns_empty():
    assert decode_jwt_payload("not-a-token") == {}
    assert decode_jwt_payload("") == {}


def credentials() -> Credentials:
    return Credentials(sys_id="999", account_id="user", account_pass="secret")


def test_signature_contains_query_and_hex_signature():
    signer = SM2Auth(session=None, credentials=credentials())  # type: ignore[arg-type]
    signed = signer.generate_signature()
    query, signature = signed.split("&s=")
    assert query.startswith("p1=user&p2=")
    assert "&p3=999&t=" in query
    assert signature
    int(signature, 16)


def test_signature_requires_encryption(monkeypatch):
    signer = SM2Auth(session=None, credentials=credentials())  # type: ignore[arg-type]
    monkeypatch.setattr(signer._sm2, "encrypt", lambda _data: None)
    with pytest.raises(AuthError):
        signer.generate_signature()


def test_cache_invalid_without_token():
    signer = SM2Auth(session=None, credentials=credentials())  # type: ignore[arg-type]
    assert signer._is_cache_valid() is False


def test_cache_valid_before_expiry(monkeypatch):
    signer = SM2Auth(session=None, credentials=credentials())  # type: ignore[arg-type]
    signer._jwt = make_token({"exp": 1000})
    monkeypatch.setattr(auth.time, "time", lambda: 100)
    assert signer._is_cache_valid() is True


def test_cache_invalid_inside_margin(monkeypatch):
    signer = SM2Auth(session=None, credentials=credentials())  # type: ignore[arg-type]
    signer._jwt = make_token({"exp": 1000})
    monkeypatch.setattr(auth.time, "time", lambda: 1000 - 30)
    assert signer._is_cache_valid() is False

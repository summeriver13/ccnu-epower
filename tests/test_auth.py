import base64
import json

import pytest
from gmssl import sm2

from epower import auth
from epower.auth import SM2Auth, decode_jwt_payload
from epower.config import Credentials
from epower.errors import AuthError, ParseError


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


SHARED_PRIVATE_KEY = "3945208f7b2144b13f36e38ac6d39f958893957e5c25d1c25d1c25d1c25d1c25"


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class FakeSession:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.urls: list[str] = []

    def get(self, url: str, timeout: float = 0) -> FakeResponse:
        self.urls.append(url)
        return FakeResponse(self.payload)


def encrypted_shared_account(name: str, password: str) -> dict:
    box = sm2.CryptSM2(private_key=SHARED_PRIVATE_KEY, public_key="", mode=1)
    public_key = box._kg(int(SHARED_PRIVATE_KEY, 16), sm2.default_ecc_table["g"])
    sealer = sm2.CryptSM2(public_key=public_key, private_key="", mode=1)
    return {
        "Code": 0,
        "Data": {
            "P1": sealer.encrypt(name.encode()).hex(),
            "P2": sealer.encrypt(password.encode()).hex(),
        },
    }


def shared_credentials() -> Credentials:
    return Credentials(sys_id="999", app_private_key=SHARED_PRIVATE_KEY)


def test_shared_account_is_decrypted_from_the_frontend_endpoint():
    session = FakeSession(encrypted_shared_account("ph", "shared-secret"))
    signer = SM2Auth(session=session, credentials=shared_credentials())  # type: ignore[arg-type]
    assert signer._fetch_shared_account() == ("ph", "shared-secret")
    assert session.urls == [
        "https://jnb.ccnu.edu.cn/ICBS_V2_Server/v1/Authentication/GetAP?id=999"
    ]


def test_signature_uses_the_shared_account_when_password_is_missing():
    signer = SM2Auth(session=None, credentials=shared_credentials())  # type: ignore[arg-type]
    signer._shared = ("ph", "shared-secret")
    assert signer.generate_signature().startswith("p1=ph&p2=")


def test_shared_account_is_fetched_only_once():
    session = FakeSession(encrypted_shared_account("ph", "shared-secret"))
    signer = SM2Auth(session=session, credentials=shared_credentials())  # type: ignore[arg-type]
    signer._login_credentials()
    signer._login_credentials()
    assert len(session.urls) == 1


def test_broken_shared_account_payload_raises_parse_error():
    signer = SM2Auth(  # type: ignore[arg-type]
        session=FakeSession({"Code": 0, "Data": {"P1": "zz", "P2": "zz"}}),
        credentials=shared_credentials(),
    )
    with pytest.raises(ParseError):
        signer._fetch_shared_account()


def test_login_error_reports_the_server_message():
    payload = {"Code": 0, "Mess": "成功", "Data": {"Result": 1, "Msg": "用户ID错误"}}
    signer = SM2Auth(session=FakeSession(payload), credentials=credentials())  # type: ignore[arg-type]
    with pytest.raises(AuthError) as excinfo:
        signer.get_jwt()
    assert "用户ID错误" in str(excinfo.value)

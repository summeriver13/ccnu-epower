import time

import pytest
import requests

from epower import client
from epower.client import RateLimiter, parse_retry_after, retry_on_transient
from epower.errors import APIError, AuthError, NetworkError


def test_retry_recovers_after_transient_error(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise NetworkError("boom")
        return "ok"

    assert retry_on_transient(flaky) == "ok"
    assert len(calls) == 3


def test_retry_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    def always_fail():
        raise NetworkError("boom")

    with pytest.raises(NetworkError):
        retry_on_transient(always_fail, max_retries=2)


def test_retry_does_not_retry_api_error(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    calls = []

    def fail():
        calls.append(1)
        raise APIError("bad code")

    with pytest.raises(APIError):
        retry_on_transient(fail)
    assert len(calls) == 1


def test_parse_retry_after():
    response = requests.Response()
    response.headers["Retry-After"] = "7"
    assert parse_retry_after(response) == 7.0
    assert parse_retry_after(None) == client.DEFAULT_RETRY_AFTER_SECONDS
    response.headers["Retry-After"] = "soon"
    assert parse_retry_after(response) == client.DEFAULT_RETRY_AFTER_SECONDS


def test_rate_limiter_sleeps(monkeypatch):
    slept = []
    monkeypatch.setattr(time, "sleep", slept.append)
    limiter = RateLimiter(min_interval=10.0)
    limiter.wait()
    limiter.wait()
    assert slept
    assert slept[0] > 0


def test_handle_429_raises_network_error(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    api = client.NewAPI(session=None, auth=None)  # type: ignore[arg-type]
    response = requests.Response()
    response.status_code = 429
    response.headers["Retry-After"] = "0"
    error = requests.HTTPError(response=response)
    with pytest.raises(NetworkError):
        api._handle_http_error(error, "ep", {}, retry_auth=False)


def test_handle_401_without_retry_raises_auth_error():
    api = client.NewAPI(session=None, auth=None)  # type: ignore[arg-type]
    response = requests.Response()
    response.status_code = 401
    error = requests.HTTPError(response=response)
    with pytest.raises(AuthError):
        api._handle_http_error(error, "ep", {}, retry_auth=False)

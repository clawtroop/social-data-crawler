import os

from linkedin_url.auth.proxy import (
    playwright_proxy_from_url,
    resolve_playwright_proxy,
)


def test_playwright_proxy_http():
    c = playwright_proxy_from_url("http://127.0.0.1:7890")
    assert c == {"server": "http://127.0.0.1:7890"}


def test_playwright_proxy_socks5():
    c = playwright_proxy_from_url("socks5://127.0.0.1:1080")
    assert c["server"] == "socks5://127.0.0.1:1080"


def test_playwright_proxy_auth():
    c = playwright_proxy_from_url("http://user:p%40ss@127.0.0.1:7890")
    assert c["server"] == "http://127.0.0.1:7890"
    assert c["username"] == "user"
    assert c["password"] == "p@ss"


def test_resolve_explicit_over_env(monkeypatch):
    monkeypatch.delenv("LINKEDIN_PROXY", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    assert resolve_playwright_proxy(explicit="http://10.0.0.1:8888") == {
        "server": "http://10.0.0.1:8888"
    }


def test_resolve_from_env(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7890")
    monkeypatch.delenv("LINKEDIN_PROXY", raising=False)
    assert resolve_playwright_proxy(explicit=None) == {"server": "http://127.0.0.1:7890"}


def test_linkedin_proxy_wins(monkeypatch):
    monkeypatch.setenv("LINKEDIN_PROXY", "http://10.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:2")
    r = resolve_playwright_proxy(explicit=None)
    assert r["server"] == "http://10.0.0.1:1"

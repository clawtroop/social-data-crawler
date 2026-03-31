from __future__ import annotations

import json
from pathlib import Path

from crawler.fetch.session_store import SessionStore


def test_session_store_round_trip(workspace_tmp_path: Path) -> None:
    store = SessionStore(workspace_tmp_path / "sessions")
    payload = {"cookies": [{"name": "li_at", "value": "secret"}]}
    store.save("linkedin", payload)

    assert store.load("linkedin") == payload


def test_session_store_imports_cookie_json_as_storage_state(workspace_tmp_path: Path) -> None:
    cookies_path = workspace_tmp_path / "cookies.json"
    cookies_path.write_text(
        '[{"name":"li_at","value":"secret","domain":".linkedin.com","path":"/"}]',
        encoding="utf-8",
    )
    store = SessionStore(workspace_tmp_path / "sessions")

    saved_path = store.import_cookies("linkedin", cookies_path)
    restored = store.load("linkedin")

    assert saved_path.exists()
    assert restored == {
        "cookies": [{"name": "li_at", "value": "secret", "domain": ".linkedin.com", "path": "/"}],
        "origins": [],
    }


def test_session_store_imports_simple_cookie_mapping(workspace_tmp_path: Path) -> None:
    cookies_path = workspace_tmp_path / "cookies.json"
    cookies_path.write_text(
        '{"li_at":"secret-token","JSESSIONID":"\\"ajax:123\\""}',
        encoding="utf-8",
    )
    store = SessionStore(workspace_tmp_path / "sessions")

    store.import_cookies("linkedin", cookies_path)
    restored = store.load("linkedin")

    assert restored == {
        "cookies": [
            {"name": "li_at", "value": "secret-token", "domain": ".linkedin.com", "path": "/"},
            {"name": "JSESSIONID", "value": '"ajax:123"', "domain": ".linkedin.com", "path": "/"},
        ],
        "origins": [],
    }


def test_session_store_imports_wrapped_storage_state_export(workspace_tmp_path: Path) -> None:
    cookies_path = workspace_tmp_path / "auto-browser-session.json"
    cookies_path.write_text(
        """
        {
          "platform": "linkedin",
          "source": "auto-browser",
          "storage_state": {
            "cookies": [
              {"name": "li_at", "value": "secret", "domain": ".linkedin.com", "path": "/"}
            ],
            "origins": []
          }
        }
        """.strip(),
        encoding="utf-8",
    )
    store = SessionStore(workspace_tmp_path / "sessions")

    saved_path = store.import_cookies("linkedin", cookies_path)
    restored = store.load("linkedin")

    assert saved_path.exists()
    assert restored == {
        "cookies": [{"name": "li_at", "value": "secret", "domain": ".linkedin.com", "path": "/"}],
        "origins": [],
    }


def test_session_store_preserves_wrapped_storage_state_for_non_linkedin_platform(workspace_tmp_path: Path) -> None:
    cookies_path = workspace_tmp_path / "base-session.json"
    cookies_path.write_text(
        """
        {
          "platform": "base",
          "source": "auto-browser",
          "storage_state": {
            "cookies": [
              {"name": "wallet", "value": "secret", "domain": ".base.org", "path": "/"}
            ],
            "origins": []
          }
        }
        """.strip(),
        encoding="utf-8",
    )
    store = SessionStore(workspace_tmp_path / "sessions")

    saved_path = store.import_cookies("base", cookies_path)
    restored = store.load("base")

    assert saved_path.exists()
    assert restored == {
        "cookies": [{"name": "wallet", "value": "secret", "domain": ".base.org", "path": "/"}],
        "origins": [],
    }


def test_session_store_imports_cookie_header_string(workspace_tmp_path: Path) -> None:
    cookies_path = workspace_tmp_path / "headers.json"
    cookies_path.write_text(
        json.dumps(
            {
                "cookie_header": 'li_at=secret-token; JSESSIONID="ajax:123"; lang=v=2&lang=zh-cn'
            }
        ),
        encoding="utf-8",
    )
    store = SessionStore(workspace_tmp_path / "sessions")

    saved_path = store.import_cookies("linkedin", cookies_path)
    restored = store.load("linkedin")

    assert saved_path.exists()
    assert restored == {
        "cookies": [
            {"name": "li_at", "value": "secret-token", "domain": ".linkedin.com", "path": "/"},
            {"name": "JSESSIONID", "value": '"ajax:123"', "domain": ".linkedin.com", "path": "/"},
            {"name": "lang", "value": "v=2&lang=zh-cn", "domain": ".linkedin.com", "path": "/"},
        ],
        "origins": [],
    }

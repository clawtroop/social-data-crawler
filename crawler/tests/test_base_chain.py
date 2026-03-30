from __future__ import annotations

from crawler.platforms.base_chain import _extract_base, _fetch_base_api


def test_extract_base_serializes_result_payload() -> None:
    extracted = _extract_base(
        {"resource_type": "address"},
        {"json_data": {"result": {"balance": "10"}}, "content_type": "application/json", "url": "https://base.org"},
    )

    assert '"balance": "10"' in extracted["plain_text"]


def test_fetch_base_api_supports_contract(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_fetch_api_get(*, canonical_url, api_endpoint, headers=None):
        calls.append((canonical_url, api_endpoint))
        return {
            "url": canonical_url,
            "json_data": {"result": [{"SourceCode": "contract C {}"}]},
            "content_type": "application/json",
        }

    monkeypatch.setattr("crawler.platforms.base_chain.fetch_api_get", fake_fetch_api_get)

    result = _fetch_base_api(
        {"resource_type": "contract"},
        {"canonical_url": "https://basescan.org/address/0xabc#code", "fields": {"contract_address": "0xabc"}},
        None,
    )

    assert result["json_data"]["result"][0]["SourceCode"] == "contract C {}"
    assert "getsourcecode" in calls[0][1]

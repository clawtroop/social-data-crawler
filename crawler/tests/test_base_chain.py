from __future__ import annotations

from crawler.platforms.base_chain import _extract_base, _fetch_base_api
from crawler.extract.structured.json_extractor import JsonExtractor


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


def test_fetch_base_api_uses_etherscan_v2_for_token(monkeypatch) -> None:
    calls: list[str] = []

    def fake_fetch_api_get(*, canonical_url, api_endpoint, headers=None):
        calls.append(api_endpoint)
        return {
            "url": canonical_url,
            "json_data": {"result": [{"tokenName": "Wrapped Ether"}]},
            "content_type": "application/json",
        }

    monkeypatch.setattr("crawler.platforms.base_chain.fetch_api_get", fake_fetch_api_get)
    monkeypatch.setenv("ETHERSCAN_API_KEY", "test-key")
    monkeypatch.delenv("BASESCAN_API_KEY", raising=False)

    result = _fetch_base_api(
        {"resource_type": "token"},
        {"canonical_url": "https://basescan.org/token/0x4200000000000000000000000000000000000006", "fields": {"contract_address": "0x4200000000000000000000000000000000000006"}},
        None,
    )

    assert result["json_data"]["result"][0]["tokenName"] == "Wrapped Ether"
    assert calls
    assert calls[0].startswith("https://api.etherscan.io/v2/api?")
    assert "chainid=8453" in calls[0]
    assert "module=token" in calls[0]
    assert "action=tokeninfo" in calls[0]
    assert "apikey=test-key" in calls[0]


def test_extract_base_html_parses_token_meta_without_name_error() -> None:
    extractor = JsonExtractor()
    html = """
    <html>
      <head>
        <title>Wrapped Ether (WETH) Token Tracker | BaseScan</title>
        <meta name="description" content="Wrapped Ether (WETH) Token Tracker on Base. Token Rep: Blue Chip | Price: $1,234.56 | Onchain Market Cap: $9.9B | Holders: 123,456 | Contract: Verified | Transactions: 999,999">
      </head>
      <body>
        <main><h1>Wrapped Ether</h1></main>
      </body>
    </html>
    """

    result = extractor.extract_from_html(
        html=html,
        platform="base",
        resource_type="token",
        url="https://basescan.org/token/0x4200000000000000000000000000000000000006",
    )

    assert result.title == "Wrapped Ether"
    assert result.description.startswith("Wrapped Ether (WETH) Token Tracker")
    assert result.platform_fields["token_reputation"] == "Blue Chip"
    assert result.platform_fields["price_usd"] == "$1,234.56"
    assert result.platform_fields["market_cap"] == "$9.9B"
    assert result.platform_fields["holders"] == "123,456"
    assert result.platform_fields["contract_status"] == "Verified"
    assert result.platform_fields["transactions"] == "999,999"

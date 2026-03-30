from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile


def _load_vrd_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "vrd.py"
    spec = importlib.util.spec_from_file_location("auto_browser_vrd", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_export_session_writes_wrapped_storage_state(monkeypatch) -> None:
    vrd = _load_vrd_module()
    temp_dir = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / ".pytest-tmp")
    output_path = Path(temp_dir.name) / "linkedin.session.json"

    monkeypatch.setattr(vrd, "_load", lambda: {"CDP_PORT": "9222"})

    class FakeContext:
        def storage_state(self) -> dict:
            return {
                "cookies": [{"name": "li_at", "value": "secret", "domain": ".linkedin.com", "path": "/"}],
                "origins": [],
            }

    class FakeBrowser:
        contexts = [FakeContext()]

    class FakeChromium:
        def connect_over_cdp(self, endpoint: str) -> FakeBrowser:
            assert endpoint == "http://127.0.0.1:9222"
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakePlaywrightManager:
        def __enter__(self) -> FakePlaywright:
            return FakePlaywright()

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr(vrd, "sync_playwright", lambda: FakePlaywrightManager(), raising=False)

    result = vrd.export_session("linkedin", str(output_path))

    assert result["ok"] is True
    assert result["path"] == str(output_path)
    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "platform": "linkedin",
        "source": "auto-browser",
        "storage_state": {
            "cookies": [{"name": "li_at", "value": "secret", "domain": ".linkedin.com", "path": "/"}],
            "origins": [],
        },
    }
    temp_dir.cleanup()

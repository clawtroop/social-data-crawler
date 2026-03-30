from __future__ import annotations

import json
from pathlib import Path

from crawler.integrations.linkedin_auth import LinkedInAutoBrowserBridge


def test_linkedin_auto_browser_bridge_exports_session(monkeypatch, workspace_tmp_path: Path) -> None:
    workdir = workspace_tmp_path / "vrd"
    output_dir = workspace_tmp_path / "out"
    state_path = workdir / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "CDP_PORT": "9222",
                "PUBLIC_URL": "https://vrd.example/vnc_mode.html?token=abc",
                "SWITCH_TOKEN": "abc",
            }
        ),
        encoding="utf-8",
    )
    exported: dict[str, Path | None] = {"path": None}

    bridge = LinkedInAutoBrowserBridge(
        script_path=workspace_tmp_path / "vrd.py",
        workdir=workdir,
        wait_timeout_seconds=1,
    )

    monkeypatch.setattr(LinkedInAutoBrowserBridge, "_ensure_script_exists", lambda self: None)
    monkeypatch.setattr(LinkedInAutoBrowserBridge, "_ensure_vrd_running", lambda self: None)
    monkeypatch.setattr(
        LinkedInAutoBrowserBridge,
        "_request_json",
        lambda self, path, **kwargs: {"ok": True, "signaled": True, "ts": 1.0} if path.startswith("/continue/poll") else {"ok": True},
    )

    def fake_export(session_path: Path) -> None:
        exported["path"] = session_path
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session_path.write_text(
            json.dumps(
                {
                    "platform": "linkedin",
                    "source": "auto-browser",
                    "storage_state": {"cookies": [{"name": "li_at", "value": "secret"}], "origins": []},
                }
            ),
            encoding="utf-8",
        )

    monkeypatch.setattr(LinkedInAutoBrowserBridge, "_export_session", lambda self, session_path: fake_export(session_path))

    session_path = bridge.ensure_exported_session(output_dir)

    assert exported["path"] == session_path
    assert session_path.exists()
    assert json.loads(session_path.read_text(encoding="utf-8"))["storage_state"]["cookies"][0]["name"] == "li_at"

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def get_default_auto_browser_script() -> Path:
    return Path(__file__).resolve().parents[2] / "auto-browser" / "scripts" / "vrd.py"


def _default_workdir() -> Path:
    return Path(os.environ.get("WORKDIR", Path.home() / ".openclaw" / "vrd-data"))


@dataclass(frozen=True, slots=True)
class LinkedInAutoBrowserBridge:
    script_path: Path
    workdir: Path
    login_url: str = "https://www.linkedin.com/login"
    wait_timeout_seconds: int = 300

    def ensure_exported_session(self, output_dir: Path) -> Path:
        self._ensure_script_exists()
        self._ensure_vrd_running()
        state = self._wait_for_state()
        public_url = str(state.get("PUBLIC_URL", "")).strip()
        switch_token = str(state.get("SWITCH_TOKEN", "")).strip()
        if not public_url or not switch_token:
            raise RuntimeError("auto-browser 已启动，但未拿到 PUBLIC_URL 或 SWITCH_TOKEN")

        self._show_login_guide(public_url, switch_token)
        session_path = output_dir / ".sessions" / "linkedin.auto-browser.json"
        self._export_session(session_path)
        return session_path

    def _ensure_script_exists(self) -> None:
        if not self.script_path.exists():
            raise RuntimeError(f"auto-browser 脚本不存在: {self.script_path}")

    def _base_env(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        env = os.environ.copy()
        env["WORKDIR"] = str(self.workdir)
        if extra:
            env.update(extra)
        return env

    def _run_vrd(self, *args: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self.script_path), *args],
            capture_output=True,
            text=True,
            env=self._base_env(extra_env),
        )

    def _ensure_vrd_running(self) -> None:
        status = self._run_vrd("status")
        if status.returncode == 0:
            return

        start = self._run_vrd(
            "start",
            extra_env={
                "AUTO_LAUNCH_URL": self.login_url,
                "AUTO_LAUNCH_CHROME": "1",
            },
        )
        if start.returncode != 0:
            raise RuntimeError(
                "auto-browser 启动失败: "
                + (start.stderr.strip() or start.stdout.strip() or "未知错误")
            )

    def _wait_for_state(self) -> dict[str, Any]:
        state_path = self.workdir / "state.json"
        deadline = time.time() + 45
        last_error = "状态文件不存在"
        while time.time() < deadline:
            try:
                if state_path.exists():
                    state = json.loads(state_path.read_text(encoding="utf-8"))
                    if isinstance(state, dict) and state.get("CDP_PORT"):
                        return state
            except Exception as exc:  # pragma: no cover - defensive runtime path
                last_error = str(exc)
            time.sleep(1)
        raise RuntimeError(f"等待 auto-browser 状态超时: {last_error}")

    def _request_json(
        self,
        path: str,
        *,
        token: str,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        url = f"http://127.0.0.1:6090{path}"
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{urlencode({'token': token})}"
        data: bytes | None = None
        headers: dict[str, str] = {}
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = response.read().decode("utf-8")
        except URLError as exc:  # pragma: no cover - runtime network path
            raise RuntimeError(f"调用 auto-browser 控制面失败: {exc}") from exc
        parsed = json.loads(payload)
        if not isinstance(parsed, dict):
            raise RuntimeError("auto-browser 控制面返回了非法 JSON")
        return parsed

    def _show_login_guide(self, public_url: str, switch_token: str) -> None:
        self._request_json(
            "/guide",
            token=switch_token,
            method="POST",
            body={"text": "请在远程浏览器中完成 LinkedIn 登录，完成后点击“已完成，继续”", "kind": "action"},
        )
        print("请打开以下地址完成 LinkedIn 登录：")
        print(public_url)
        try:
            self._poll_continue_signal(switch_token)
        finally:
            self._request_json("/guide", token=switch_token, method="DELETE")

    def _poll_continue_signal(self, switch_token: str) -> None:
        after = 0.0
        deadline = time.time() + self.wait_timeout_seconds
        while time.time() < deadline:
            payload = self._request_json(
                f"/continue/poll?after={after}&timeout=5",
                token=switch_token,
                method="GET",
                timeout=8.0,
            )
            after = float(payload.get("ts", after) or after)
            if payload.get("signaled") is True:
                return
        raise RuntimeError("等待用户完成 LinkedIn 登录超时")

    def _export_session(self, session_path: Path) -> None:
        export = self._run_vrd("export-session", "linkedin", str(session_path))
        if export.returncode != 0:
            raise RuntimeError(
                "导出 LinkedIn 会话失败: "
                + (export.stderr.strip() or export.stdout.strip() or "未知错误")
            )

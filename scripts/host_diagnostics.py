from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from typing import Any


LINUX_PLAYWRIGHT_LIBS = (
    "libnss3.so",
    "libnspr4.so",
    "libatk-1.0.so",
    "libatk-bridge-2.0.so",
    "libcups.so.2",
    "libdrm.so.2",
    "libdbus-1.so.3",
    "libxkbcommon.so.0",
    "libxcomposite.so.1",
    "libxdamage.so.1",
    "libxfixes.so.3",
    "libxrandr.so.2",
    "libgbm.so.1",
    "libpango-1.0.so.0",
    "libcairo.so.2",
    "libasound.so.2",
    "libatspi.so.0",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose host prerequisites for crawler bootstrap.")
    parser.add_argument("--json", action="store_true", help="Print diagnostics as JSON.")
    return parser.parse_args()


def _base_payload() -> dict[str, Any]:
    return {
        "ok": True,
        "platform_family": _platform_family(),
        "platform": platform.platform(),
        "checks": [],
        "guidance": [],
    }


def _platform_family() -> str:
    system = platform.system().lower()
    if system.startswith("linux"):
        return "linux"
    if system.startswith("darwin"):
        return "darwin"
    if system.startswith("windows"):
        return "windows"
    return "unknown"


def _record(payload: dict[str, Any], *, name: str, ok: bool, severity: str, detail: str) -> None:
    payload["checks"].append(
        {
            "name": name,
            "ok": ok,
            "severity": severity,
            "detail": detail,
        }
    )
    if not ok and severity == "error":
        payload["ok"] = False


def _diagnose_linux(payload: dict[str, Any]) -> None:
    payload["guidance"].append(
        "Install the Playwright system libraries before expecting browser-backed crawling to work."
    )
    payload["guidance"].append(
        "Example: sudo apt-get update && sudo apt-get install -y libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0"
    )
    ldconfig_path = shutil.which("ldconfig")
    if not ldconfig_path:
        _record(
            payload,
            name="ldconfig",
            ok=False,
            severity="warning",
            detail="ldconfig not found; cannot verify Linux shared libraries automatically.",
        )
        return

    result = subprocess.run([ldconfig_path, "-p"], text=True, capture_output=True, check=False)
    if result.returncode != 0:
        _record(
            payload,
            name="ldconfig",
            ok=False,
            severity="warning",
            detail=f"ldconfig -p failed with exit code {result.returncode}.",
        )
        return

    missing = [lib for lib in LINUX_PLAYWRIGHT_LIBS if lib not in result.stdout]
    _record(
        payload,
        name="linux_playwright_libs",
        ok=not missing,
        severity="warning",
        detail="all expected libraries found" if not missing else "missing: " + ", ".join(missing),
    )


def _diagnose_darwin(payload: dict[str, Any]) -> None:
    payload["guidance"].append("Install Xcode Command Line Tools before browser-backed crawling: xcode-select --install")
    xcode_select = shutil.which("xcode-select")
    if not xcode_select:
        _record(
            payload,
            name="xcode-select",
            ok=False,
            severity="warning",
            detail="xcode-select not found; Xcode Command Line Tools may be missing.",
        )
        return

    result = subprocess.run([xcode_select, "-p"], text=True, capture_output=True, check=False)
    _record(
        payload,
        name="xcode-select",
        ok=result.returncode == 0,
        severity="warning",
        detail=result.stdout.strip() if result.returncode == 0 else "Xcode Command Line Tools do not appear installed.",
    )


def _diagnose_windows(payload: dict[str, Any]) -> None:
    payload["guidance"].append("Ensure Microsoft Visual C++ Redistributable is installed.")
    payload["guidance"].append("Ensure Playwright browser downloads are allowed and the user profile directory is writable.")
    home = os.path.expanduser("~")
    if not os.path.exists(home):
        _record(
            payload,
            name="home_directory",
            ok=False,
            severity="warning",
            detail=f"home directory does not exist: {home}",
        )
        return

    writable = os.access(home, os.W_OK)
    _record(
        payload,
        name="home_directory",
        ok=writable,
        severity="warning",
        detail=f"writable home directory: {home}" if writable else f"home directory is not writable: {home}",
    )


def _diagnose_unknown(payload: dict[str, Any]) -> None:
    payload["guidance"].append("Host OS is not explicitly supported; continue with best-effort setup.")
    _record(
        payload,
        name="platform_family",
        ok=False,
        severity="warning",
        detail=f"unrecognized platform: {payload['platform']}",
    )


def build_payload() -> dict[str, Any]:
    payload = _base_payload()
    family = payload["platform_family"]
    if family == "linux":
        _diagnose_linux(payload)
    elif family == "darwin":
        _diagnose_darwin(payload)
    elif family == "windows":
        _diagnose_windows(payload)
    else:
        _diagnose_unknown(payload)
    return payload


def main() -> int:
    args = parse_args()
    payload = build_payload()
    if args.json:
        print(json.dumps(payload, ensure_ascii=True))
    else:
        print(f"host diagnostics for {payload['platform_family']}: ok={payload['ok']}")
        for check in payload["checks"]:
            status = "ok" if check["ok"] else check["severity"]
            print(f"- {check['name']}: {status} - {check['detail']}")
        if payload["guidance"]:
            print("guidance:")
            for item in payload["guidance"]:
                print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import importlib
import json
import platform
import sys
from pathlib import Path

from host_diagnostics import build_payload as build_host_diagnostics


ROOT = Path(__file__).resolve().parents[1]

PROFILE_MODULES = {
    "minimal": ("pydantic", "httpx", "typer", "crawl4ai", "bs4", "lxml", "markdownify"),
    "browser": (
        "pydantic",
        "httpx",
        "typer",
        "crawl4ai",
        "bs4",
        "lxml",
        "markdownify",
        "playwright",
        "camoufox",
    ),
    "full": (
        "pydantic",
        "httpx",
        "typer",
        "crawl4ai",
        "bs4",
        "lxml",
        "markdownify",
        "playwright",
        "camoufox",
        "pytest",
    ),
}


def _import_module(name: str) -> None:
    try:
        importlib.import_module(name)
    except Exception as exc:  # pragma: no cover - surfaced as script failure
        raise SystemExit(f"required module import failed: {name}: {exc}") from exc


def _verify_playwright_browsers() -> dict[str, str]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - surfaced as script failure
        raise SystemExit(f"playwright runtime import failed: {exc}") from exc

    missing: list[str] = []
    executables: dict[str, str] = {}
    with sync_playwright() as playwright:
        executables = {
            "chromium": playwright.chromium.executable_path,
            "firefox": playwright.firefox.executable_path,
            "webkit": playwright.webkit.executable_path,
        }
        for name, path in executables.items():
            if not path or not Path(path).exists():
                missing.append(f"{name} ({path or 'missing path'})")

    if missing:
        raise SystemExit(
            "playwright browser binaries not ready: "
            + ", ".join(missing)
            + ". Run `python -m playwright install`."
        )
    return executables


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify bootstrap-installed crawler environment.")
    parser.add_argument(
        "--profile",
        choices=("minimal", "browser", "full"),
        default="full",
        help="Installation profile to verify.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable JSON result.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = {
        "ok": False,
        "profile": args.profile,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "modules": [],
        "playwright_browsers": {},
        "host_diagnostics": build_host_diagnostics(),
    }

    try:
        if sys.version_info < (3, 11):
            raise SystemExit("python 3.11+ is required")

        sys.path.insert(0, str(ROOT))

        for module_name in PROFILE_MODULES[args.profile]:
            _import_module(module_name)
            payload["modules"].append(module_name)

        if args.profile in {"browser", "full"}:
            payload["playwright_browsers"] = _verify_playwright_browsers()

        payload["ok"] = True
        if args.json:
            print(json.dumps(payload, ensure_ascii=True))
        else:
            print(f"environment verification passed for profile: {args.profile}")
        return 0
    except SystemExit as exc:
        message = str(exc)
        if args.json:
            payload["error"] = message
            print(json.dumps(payload, ensure_ascii=True))
            return 1
        raise


if __name__ == "__main__":
    raise SystemExit(main())

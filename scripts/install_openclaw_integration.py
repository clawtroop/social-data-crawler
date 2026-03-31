from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from build_openclaw_plugin import DIST_DIR, build_archives, build_plugin_dist


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ID = "social-crawler-agent"
SKILL_NAME = "social-data-crawler"
DEFAULT_GATEWAY_URL = "http://127.0.0.1:18789/v1"
# OpenClaw modern installs schema expects values like {"source": "path"} or {"source": "archive"}.
PLUGIN_SOURCE_PATH = "path"
PLUGIN_SOURCE_ARCHIVE = "archive"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install the single-repo OpenClaw integration for social-data-crawler.")
    parser.add_argument("--crawler-root", default=str(ROOT), help="Path to the social-data-crawler repository root.")
    parser.add_argument("--python-bin", default=os.environ.get("PYTHON_BIN", "python"), help="Python executable for crawler and plugin runtime.")
    parser.add_argument("--platform-base-url", default=os.environ.get("PLATFORM_BASE_URL", ""), help="Platform Service base URL.")
    parser.add_argument("--platform-token", default=os.environ.get("PLATFORM_TOKEN", ""), help="Optional Platform Service bearer token.")
    parser.add_argument("--miner-id", default=os.environ.get("MINER_ID", ""), help="Mining client identifier.")
    parser.add_argument("--gateway-base-url", default=os.environ.get("OPENCLAW_GATEWAY_BASE_URL", DEFAULT_GATEWAY_URL), help="OpenClaw Gateway base URL for enrich traffic.")
    parser.add_argument("--openclaw-home", default=os.environ.get("OPENCLAW_HOME", str(Path.home() / ".openclaw")), help="OpenClaw home directory.")
    parser.add_argument("--openclaw-config-path", default=os.environ.get("OPENCLAW_CONFIG_PATH", ""), help="Explicit path to openclaw.json.")
    parser.add_argument("--awp-wallet-bin", default=os.environ.get("AWP_WALLET_BIN", "awp-wallet"), help="awp-wallet executable name or path.")
    parser.add_argument("--awp-wallet-token", default=os.environ.get("AWP_WALLET_TOKEN", ""), help="Pre-existing awp-wallet session token.")
    parser.add_argument("--awp-wallet-token-env", default="AWP_WALLET_TOKEN", help="Environment variable name used by awpWalletTokenRef.")
    parser.add_argument("--skip-wallet", action="store_true", help="Do not install or unlock awp-wallet.")
    parser.add_argument("--skip-skill", action="store_true", help="Do not install the workspace skill wrapper.")
    parser.add_argument("--skip-archive", action="store_true", help="Do not emit plugin zip/tar.gz archives.")
    parser.add_argument("--force-build", action="store_true", help="Rebuild dist/openclaw-plugin even when it already exists.")
    parser.add_argument(
        "--plugin-source",
        choices=(PLUGIN_SOURCE_PATH, PLUGIN_SOURCE_ARCHIVE),
        default=PLUGIN_SOURCE_PATH,
        help="OpenClaw plugin install source type. 'path' uses dist/openclaw-plugin, 'archive' uses the packaged tar.gz.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_checked(command: list[str], *, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if not env.get("HOME") and env.get("USERPROFILE"):
        env["HOME"] = env["USERPROFILE"]
    return subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        capture_output=capture_output,
        check=True,
        env=env,
    )


def resolve_openclaw_config_path(args: argparse.Namespace) -> Path:
    if args.openclaw_config_path:
        return Path(args.openclaw_config_path).expanduser()
    return Path(args.openclaw_home).expanduser() / "openclaw.json"


def install_skill_wrapper(openclaw_home: Path, crawler_root: Path) -> Path:
    skill_dir = openclaw_home / "workspace" / "skills" / SKILL_NAME
    if skill_dir.exists():
        shutil.rmtree(skill_dir)
    skill_dir.mkdir(parents=True, exist_ok=True)
    wrapper = f"""---
name: social-data-crawler
description: Wrapper skill that delegates to the checked-out social-data-crawler repository.
---

# Social Data Crawler

Canonical repo root: `{crawler_root}`

When you need the full instructions, open:

- `{crawler_root / "SKILL.md"}`
- `{crawler_root / "README.md"}`

Bootstrap from the repo checkout:

- `{crawler_root / "scripts" / "bootstrap.sh"}`
- `{crawler_root / "scripts" / "bootstrap.ps1"}`

OpenClaw integration install entry:

- `{crawler_root / "scripts" / "install_openclaw_integration.sh"}`
- `{crawler_root / "scripts" / "install_openclaw_integration.ps1"}`
"""
    (skill_dir / "SKILL.md").write_text(wrapper, encoding="utf-8")
    return skill_dir


def resolve_wallet_bin(wallet_bin: str) -> str:
    candidate = wallet_bin.strip() or "awp-wallet"
    resolved = shutil.which(candidate)
    if resolved:
        return resolved
    if os.name == "nt":
        for suffix in (".cmd", ".exe", ".bat"):
            resolved = shutil.which(candidate + suffix)
            if resolved:
                return resolved
    return candidate


def try_install_awp_wallet(wallet_bin: str) -> None:
    if shutil.which(wallet_bin) or shutil.which(resolve_wallet_bin(wallet_bin)):
        return
    sibling_installer = ROOT.parent / "awp-wallet" / "install.sh"
    if sibling_installer.exists():
        run_checked(["bash", str(sibling_installer), "--no-init"])
        return
    if shutil.which("npm"):
        run_checked(["npm", "install", "-g", "awp-wallet"])


def ensure_wallet_token(wallet_bin: str, provided_token: str, token_env_name: str) -> str:
    token = provided_token.strip() or os.environ.get(token_env_name, "").strip()
    if token:
        return token
    wallet_bin = resolve_wallet_bin(wallet_bin)
    if not shutil.which(wallet_bin) and not Path(wallet_bin).exists():
        return ""
    env = os.environ.copy()
    if not env.get("HOME") and env.get("USERPROFILE"):
        env["HOME"] = env["USERPROFILE"]
    completed = subprocess.run(
        [wallet_bin, "unlock", "--duration", "3600"],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        env=env,
    )
    if completed.returncode != 0:
        return ""
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return ""
    token = str(payload.get("sessionToken", "")).strip()
    if token:
        os.environ[token_env_name] = token
    return token


def update_openclaw_config(
    *,
    config_path: Path,
    crawler_root: Path,
    plugin_root: Path,
    args: argparse.Namespace,
    awp_wallet_token: str,
) -> dict[str, Any]:
    config = load_json(config_path)
    plugins = config.setdefault("plugins", {})
    installs = plugins.setdefault("installs", {})
    plugin_config: dict[str, Any] = {
        "crawlerRoot": str(crawler_root),
        "pythonBin": args.python_bin,
        "platformBaseUrl": args.platform_base_url,
        "platformToken": args.platform_token,
        "minerId": args.miner_id,
        "outputRoot": str(crawler_root / "output" / "agent-runs"),
        "workerStateRoot": str(crawler_root / "output" / "agent-runs" / "_worker_state"),
        "awpWalletBin": args.awp_wallet_bin,
    }
    if awp_wallet_token:
        plugin_config["awpWalletToken"] = awp_wallet_token
    else:
        plugin_config["awpWalletTokenRef"] = {
            "source": "env",
            "provider": "processenv",
            "id": args.awp_wallet_token_env,
        }

    plugin_path = str(plugin_root)
    if args.plugin_source == PLUGIN_SOURCE_ARCHIVE:
        plugin_path = str((ROOT / "dist" / "social-data-crawler-openclaw-plugin.tar.gz").resolve())

    installs[PLUGIN_ID] = {
        "source": args.plugin_source,
        "path": plugin_path,
        "config": plugin_config,
    }
    if "entries" in plugins:
        plugins.pop("entries", None)

    gateway = config.setdefault("gateway", {})
    auth = gateway.setdefault("auth", {})
    auth.setdefault("baseUrl", args.gateway_base_url)
    write_json(config_path, config)
    return config


def main() -> int:
    args = parse_args()
    crawler_root = Path(args.crawler_root).resolve()
    openclaw_home = Path(args.openclaw_home).expanduser()
    config_path = resolve_openclaw_config_path(args)

    if args.force_build or not DIST_DIR.exists():
        build_plugin_dist()
        if not args.skip_archive:
            build_archives()

    if not args.skip_wallet:
        try_install_awp_wallet(args.awp_wallet_bin)
    wallet_token = ""
    if not args.skip_wallet:
        wallet_token = ensure_wallet_token(args.awp_wallet_bin, args.awp_wallet_token, args.awp_wallet_token_env)

    skill_dir = None if args.skip_skill else install_skill_wrapper(openclaw_home, crawler_root)
    config = update_openclaw_config(
        config_path=config_path,
        crawler_root=crawler_root,
        plugin_root=DIST_DIR.resolve(),
        args=args,
        awp_wallet_token=wallet_token,
    )

    payload = {
        "plugin_dist": str(DIST_DIR.resolve()),
        "plugin_source": args.plugin_source,
        "openclaw_config_path": str(config_path),
        "skill_dir": str(skill_dir) if skill_dir else "",
        "wallet_token_env": args.awp_wallet_token_env if not wallet_token else "",
        "plugin_installed": PLUGIN_ID in (((config.get("plugins") or {}).get("installs")) or {}),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

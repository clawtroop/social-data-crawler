from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_layered_requirement_files_exist() -> None:
    for name in (
        "requirements.txt",
        "requirements-core.txt",
        "requirements-browser.txt",
        "requirements-dev.txt",
    ):
        assert (ROOT / name).exists(), f"missing {name}"


def test_aggregate_requirements_references_all_layers() -> None:
    content = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "-r requirements-core.txt" in content
    assert "-r requirements-browser.txt" in content
    assert "-r requirements-dev.txt" in content


def test_bootstrap_shell_script_supports_profiles_and_smoke_test() -> None:
    content = (ROOT / "scripts" / "bootstrap.sh").read_text(encoding="utf-8")
    assert 'INSTALL_PROFILE="${INSTALL_PROFILE:-full}"' in content
    assert "reusing existing virtualenv" in content
    assert 'uv venv --seed "$VENV_DIR"' in content
    assert "host_diagnostics.py" in content
    assert "requirements-core.txt" in content
    assert "requirements-browser.txt" in content
    assert "requirements-dev.txt" in content
    assert "verify_env.py" in content
    assert "smoke_test.py" in content
    assert "check_host_dependencies" in content


def test_bootstrap_powershell_script_supports_profiles_and_smoke_test() -> None:
    content = (ROOT / "scripts" / "bootstrap.ps1").read_text(encoding="utf-8")
    assert '$InstallProfile = if ($env:INSTALL_PROFILE)' in content
    assert ".Trim()" in content
    assert "Invoke-CheckedExternal" in content
    assert "reusing existing virtualenv" in content
    assert '${LASTEXITCODE}' in content or '-f $LASTEXITCODE' in content
    assert '"venv" "--seed" $VenvDir' in content
    assert "host_diagnostics.py" in content
    assert "requirements-core.txt" in content
    assert "requirements-browser.txt" in content
    assert "requirements-dev.txt" in content
    assert "verify_env.py" in content
    assert "smoke_test.py" in content
    assert "Test-HostDependencies" in content


def test_bootstrap_cmd_wrapper_exists_for_windows_entrypoint() -> None:
    content = (ROOT / "scripts" / "bootstrap.cmd").read_text(encoding="utf-8")
    assert "bootstrap.ps1" in content
    assert "ExecutionPolicy Bypass" in content


def test_verify_env_script_covers_profiles_and_browser_runtime() -> None:
    content = (ROOT / "scripts" / "verify_env.py").read_text(encoding="utf-8")
    assert '"minimal"' in content
    assert '"browser"' in content
    assert '"full"' in content
    assert "--json" in content
    assert "sync_playwright" in content
    assert "playwright browser binaries not ready" in content


def test_verify_env_supports_json_output() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_env.py"), "--profile", "minimal", "--json"],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["profile"] == "minimal"
    assert payload["python_version"]
    assert "pydantic" in payload["modules"]
    assert "host_diagnostics" in payload
    assert payload["host_diagnostics"]["platform_family"] in {"linux", "darwin", "windows", "unknown"}
    assert isinstance(payload["host_diagnostics"]["checks"], list)


def test_host_diagnostics_script_covers_os_checks() -> None:
    content = (ROOT / "scripts" / "host_diagnostics.py").read_text(encoding="utf-8")
    assert "--json" in content
    assert '"linux"' in content
    assert '"darwin"' in content
    assert '"windows"' in content
    assert "libnss3.so" in content
    assert "xcode-select" in content
    assert "Visual C++ Redistributable" in content


def test_host_diagnostics_supports_json_output() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "host_diagnostics.py"), "--json"],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] in {True, False}
    assert payload["platform_family"] in {"linux", "darwin", "windows", "unknown"}
    assert isinstance(payload["checks"], list)
    assert isinstance(payload["guidance"], list)


def test_skill_metadata_mentions_bootstrap_and_requires() -> None:
    content = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "bootstrap: ./scripts/bootstrap.sh" in content
    assert "windows_bootstrap: ./scripts/bootstrap.ps1" in content
    assert "smoke_test: ./scripts/smoke_test.py" in content
    assert "bins:" in content
    assert "- python3" in content
    assert "anyBins:" in content


def test_docs_mention_generic_input_and_windows_bootstrap_cmd() -> None:
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert '`generic`' in skill or '"platform":"generic"' in skill
    assert '`generic/page`' in readme
    assert "bootstrap.cmd" in readme
    assert "host_diagnostics.py" in readme


def test_single_repo_openclaw_install_assets_exist() -> None:
    assert (ROOT / "integrations" / "openclaw-plugin-src").is_dir()
    assert (ROOT / "scripts" / "build_openclaw_plugin.py").exists()
    assert (ROOT / "scripts" / "install_openclaw_integration.ps1").exists()
    assert (ROOT / "scripts" / "install_openclaw_integration.sh").exists()


def test_openclaw_plugin_source_in_repo_keeps_runtime_boundary() -> None:
    manifest = (ROOT / "integrations" / "openclaw-plugin-src" / "openclaw.plugin.json").read_text(encoding="utf-8")
    package_json = (ROOT / "integrations" / "openclaw-plugin-src" / "package.json").read_text(encoding="utf-8")
    run_tool = (ROOT / "integrations" / "openclaw-plugin-src" / "scripts" / "run_tool.py").read_text(encoding="utf-8")
    assert '"id": "social-crawler-agent"' in manifest
    assert '"name": "social-crawler-agent"' in package_json
    assert '"run-worker"' in run_tool


def test_openclaw_packaging_script_excludes_dev_only_files() -> None:
    content = (ROOT / "scripts" / "build_openclaw_plugin.py").read_text(encoding="utf-8")
    assert "integrations/openclaw-plugin-src" in content or "integrations\\openclaw-plugin-src" in content
    assert "dist/openclaw-plugin" in content or "dist\\openclaw-plugin" in content
    assert "tests" in content
    assert "__pycache__" in content
    assert ".pytest_cache" in content
    assert ".gitignore" in content


def test_openclaw_installers_cover_cross_platform_entrypoints_and_wallet_setup() -> None:
    shell = (ROOT / "scripts" / "install_openclaw_integration.sh").read_text(encoding="utf-8")
    powershell = (ROOT / "scripts" / "install_openclaw_integration.ps1").read_text(encoding="utf-8")
    for content in (shell, powershell):
        assert "build_openclaw_plugin.py" in content
        assert "awp-wallet" in content
        assert "OPENCLAW_CONFIG_PATH" in content or ".openclaw" in content
        assert "SecretRef" in content or "awpWalletTokenRef" in content
        assert "openclaw-plugin" in content


def test_docs_describe_single_repo_openclaw_install_flow() -> None:
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "single-repo" in readme or "single repo" in readme
    assert "install_openclaw_integration" in readme
    assert "awp-wallet" in readme
    assert "OpenClaw" in skill

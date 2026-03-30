#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"
INSTALL_PROFILE="${INSTALL_PROFILE:-full}"

log() {
  printf '[bootstrap] %s\n' "$*"
}

warn() {
  printf '[bootstrap][warn] %s\n' "$*" >&2
}

die() {
  printf '[bootstrap][error] %s\n' "$*" >&2
  exit 1
}

require_bin() {
  local bin="$1"
  command -v "$bin" >/dev/null 2>&1 || die "missing required binary: ${bin}"
}

check_python_version() {
  "$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("python 3.11+ is required")
print(f"python version ok: {sys.version.split()[0]}")
PY
}

print_host_dependency_guidance() {
  log "host dependency guidance:"
  "$PYTHON_BIN" "${ROOT_DIR}/scripts/host_diagnostics.py"
}

check_host_dependencies() {
  "$PYTHON_BIN" "${ROOT_DIR}/scripts/host_diagnostics.py" --json >/dev/null
}

create_venv() {
  if [[ -x "${VENV_DIR}/Scripts/python.exe" || -x "${VENV_DIR}/bin/python" ]]; then
    log "reusing existing virtualenv at ${VENV_DIR}"
    return
  fi
  if command -v uv >/dev/null 2>&1; then
    log "creating virtualenv with uv"
    uv venv --seed "$VENV_DIR"
  else
    warn "uv not found; falling back to python -m venv"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi
}

venv_python() {
  if [[ -x "${VENV_DIR}/Scripts/python.exe" ]]; then
    printf '%s\n' "${VENV_DIR}/Scripts/python.exe"
  else
    printf '%s\n' "${VENV_DIR}/bin/python"
  fi
}

install_python_deps() {
  local vpy
  vpy="$(venv_python)"
  log "upgrading pip"
  "$vpy" -m pip install --upgrade pip
  log "installing python dependencies for profile: ${INSTALL_PROFILE}"
  "$vpy" -m pip install -r "${ROOT_DIR}/requirements-core.txt"
  case "$INSTALL_PROFILE" in
    minimal)
      ;;
    browser)
      "$vpy" -m pip install -r "${ROOT_DIR}/requirements-browser.txt"
      ;;
    full)
      "$vpy" -m pip install -r "${ROOT_DIR}/requirements-browser.txt"
      "$vpy" -m pip install -r "${ROOT_DIR}/requirements-ocr.txt"
      "$vpy" -m pip install -r "${ROOT_DIR}/requirements-dev.txt"
      ;;
    *)
      die "unsupported INSTALL_PROFILE: ${INSTALL_PROFILE} (expected minimal|browser|full)"
      ;;
  esac
}

install_browser_deps() {
  local vpy
  vpy="$(venv_python)"
  if [[ "$INSTALL_PROFILE" == "minimal" ]]; then
    log "skipping browser bundle install for minimal profile"
    return
  fi
  log "installing Playwright browser binaries"
  "$vpy" -m playwright install
  log "fetching Camoufox browser bundle"
  "$vpy" -m camoufox fetch
}

run_env_verification() {
  local vpy
  vpy="$(venv_python)"
  log "verifying installed environment"
  "$vpy" "${ROOT_DIR}/scripts/verify_env.py" --profile "$INSTALL_PROFILE"
}

run_smoke_test() {
  local vpy
  vpy="$(venv_python)"
  log "running smoke test"
  "$vpy" "${ROOT_DIR}/scripts/smoke_test.py"
}

main() {
  require_bin bash
  require_bin "$PYTHON_BIN"
  check_python_version
  print_host_dependency_guidance
  check_host_dependencies
  create_venv
  install_python_deps
  install_browser_deps
  run_env_verification
  run_smoke_test
  log "bootstrap completed successfully"
}

main "$@"

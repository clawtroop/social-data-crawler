#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
OPENCLAW_CONFIG_PATH="${OPENCLAW_CONFIG_PATH:-}"
AWP_WALLET_BIN="${AWP_WALLET_BIN:-awp-wallet}"
# If no direct token is present, install_openclaw_integration.py writes awpWalletTokenRef
# using env SecretRef semantics into OPENCLAW_CONFIG_PATH / ~/.openclaw/openclaw.json.
# The packaged runtime lives under dist/openclaw-plugin.

"${PYTHON_BIN}" "${ROOT_DIR}/scripts/build_openclaw_plugin.py"
"${PYTHON_BIN}" "${ROOT_DIR}/scripts/install_openclaw_integration.py" \
  --crawler-root "${ROOT_DIR}" \
  --python-bin "${PYTHON_BIN}" \
  --openclaw-config-path "${OPENCLAW_CONFIG_PATH}" \
  --awp-wallet-bin "${AWP_WALLET_BIN}" \
  "$@"

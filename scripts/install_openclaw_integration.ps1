$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN.Trim() } else { "python" }
$OpenClawConfigPath = if ($env:OPENCLAW_CONFIG_PATH) { $env:OPENCLAW_CONFIG_PATH.Trim() } else { "" }
$AwpWalletBin = if ($env:AWP_WALLET_BIN) { $env:AWP_WALLET_BIN.Trim() } else { "awp-wallet" }
# If no direct token is present, install_openclaw_integration.py writes awpWalletTokenRef
# using env SecretRef semantics into OPENCLAW_CONFIG_PATH / ~/.openclaw/openclaw.json.
# The packaged runtime lives under dist/openclaw-plugin.

& $PythonBin (Join-Path $RootDir "scripts\build_openclaw_plugin.py")
if ($LASTEXITCODE -ne 0) {
  throw "build_openclaw_plugin.py failed with exit code $LASTEXITCODE"
}

& $PythonBin (Join-Path $RootDir "scripts\install_openclaw_integration.py") `
  --crawler-root $RootDir `
  --python-bin $PythonBin `
  --openclaw-config-path $OpenClawConfigPath `
  --awp-wallet-bin $AwpWalletBin `
  @args

if ($LASTEXITCODE -ne 0) {
  throw "install_openclaw_integration.py failed with exit code $LASTEXITCODE"
}

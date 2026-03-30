$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$VenvDir = Join-Path $RootDir ".venv"
$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN.Trim() } else { "python" }
$InstallProfile = if ($env:INSTALL_PROFILE) { $env:INSTALL_PROFILE.Trim() } else { "full" }

function Write-Log {
  param([string]$Message)
  Write-Host "[bootstrap] $Message"
}

function Write-Warn {
  param([string]$Message)
  Write-Warning $Message
}

function Invoke-CheckedExternal {
  param(
    [Parameter(Mandatory = $true)][string]$FilePath,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments
  )

  & $FilePath @Arguments | Out-Host
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
  }
}

function Require-Bin {
  param([string]$Bin)
  if (-not (Get-Command $Bin -ErrorAction SilentlyContinue)) {
    throw "Missing required binary: $Bin"
  }
}

function Test-PythonVersion {
  Invoke-CheckedExternal $PythonBin "-c" "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
}

function Show-HostDependencyGuidance {
  Write-Log "host dependency guidance:"
  Invoke-CheckedExternal $PythonBin (Join-Path $RootDir "scripts\host_diagnostics.py")
}

function Test-HostDependencies {
  Invoke-CheckedExternal $PythonBin (Join-Path $RootDir "scripts\host_diagnostics.py") "--json"
}

function Get-VenvPython {
  $candidate = Join-Path $VenvDir "Scripts\python.exe"
  if (Test-Path $candidate) {
    return $candidate
  }
  return (Join-Path $VenvDir "bin/python")
}

function New-Venv {
  $ExistingPython = Get-VenvPython
  if (Test-Path $ExistingPython) {
    Write-Log "reusing existing virtualenv at $VenvDir"
    return
  }
  if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Log "creating virtualenv with uv"
    Invoke-CheckedExternal "uv" "venv" "--seed" $VenvDir
  } else {
    Write-Warn "uv not found; falling back to python -m venv"
    Invoke-CheckedExternal $PythonBin "-m" "venv" $VenvDir
  }
}

function Install-PythonDeps {
  $Vpy = Get-VenvPython
  Write-Log "upgrading pip"
  Invoke-CheckedExternal $Vpy "-m" "pip" "install" "--upgrade" "pip"
  Write-Log "installing python dependencies for profile: $InstallProfile"
  Invoke-CheckedExternal $Vpy "-m" "pip" "install" "-r" (Join-Path $RootDir "requirements-core.txt")
  switch ($InstallProfile) {
    "minimal" { }
    "browser" {
      Invoke-CheckedExternal $Vpy "-m" "pip" "install" "-r" (Join-Path $RootDir "requirements-browser.txt")
    }
    "full" {
      Invoke-CheckedExternal $Vpy "-m" "pip" "install" "-r" (Join-Path $RootDir "requirements-browser.txt")
      Invoke-CheckedExternal $Vpy "-m" "pip" "install" "-r" (Join-Path $RootDir "requirements-ocr.txt")
      Invoke-CheckedExternal $Vpy "-m" "pip" "install" "-r" (Join-Path $RootDir "requirements-dev.txt")
    }
    default {
      throw "Unsupported INSTALL_PROFILE: $InstallProfile (expected minimal|browser|full)"
    }
  }
}

function Install-BrowserDeps {
  if ($InstallProfile -eq "minimal") {
    Write-Log "skipping browser bundle install for minimal profile"
    return
  }
  $Vpy = Get-VenvPython
  Write-Log "installing Playwright browser binaries"
  Invoke-CheckedExternal $Vpy "-m" "playwright" "install"
  Write-Log "fetching Camoufox browser bundle"
  Invoke-CheckedExternal $Vpy "-m" "camoufox" "fetch"
}

function Invoke-EnvVerification {
  $Vpy = Get-VenvPython
  Write-Log "verifying installed environment"
  Invoke-CheckedExternal $Vpy (Join-Path $RootDir "scripts\verify_env.py") "--profile" $InstallProfile
}

function Invoke-SmokeTest {
  $Vpy = Get-VenvPython
  Write-Log "running smoke test"
  Invoke-CheckedExternal $Vpy (Join-Path $RootDir "scripts\smoke_test.py")
}

Require-Bin $PythonBin
Test-PythonVersion
Show-HostDependencyGuidance
Test-HostDependencies
New-Venv
Install-PythonDeps
Install-BrowserDeps
Invoke-EnvVerification
Invoke-SmokeTest
Write-Log "bootstrap completed successfully"

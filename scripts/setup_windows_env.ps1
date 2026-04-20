param(
    [string]$PythonVersion = "3.14",
    [string]$VenvDir = ".venv314",
    [switch]$SkipWingetInstall
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step {
    param([string]$Message)
    Write-Host "[setup] $Message"
}

function Resolve-RepoRoot {
    $scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
    return (Resolve-Path (Join-Path $scriptRoot "..")).Path
}

function Get-PythonLauncher {
    param([string]$Version)

    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -eq $launcher) {
        return $null
    }

    & $launcher.Source "-$Version" --version *> $null
    if ($LASTEXITCODE -eq 0) {
        return $launcher.Source
    }

    return $null
}

function Get-WingetCommand {
    return Get-Command winget -ErrorAction SilentlyContinue
}

function Install-PythonWithWinget {
    param([string]$Version)

    $winget = Get-WingetCommand
    if ($null -eq $winget) {
        throw "winget 을 찾을 수 없습니다. Python 3.14를 수동 설치한 뒤 스크립트를 다시 실행하세요."
    }

    Write-Step "Python $Version 이 없어 winget 설치를 시도합니다."
    & $winget.Source install --exact --id Python.Python.3.14 --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "winget 으로 Python $Version 설치에 실패했습니다. 공식 설치 파일로 Python 3.14를 설치한 뒤 다시 실행하세요."
    }
}

function Ensure-PythonLauncher {
    param(
        [string]$Version,
        [switch]$SkipInstall
    )

    $launcher = Get-PythonLauncher -Version $Version
    if ($null -ne $launcher) {
        return $launcher
    }

    if ($SkipInstall) {
        throw "py -$Version 실행기를 찾지 못했습니다. Python 3.14를 수동 설치한 뒤 다시 실행하세요."
    }

    Install-PythonWithWinget -Version $Version
    $launcher = Get-PythonLauncher -Version $Version
    if ($null -eq $launcher) {
        throw "Python $Version 설치 후에도 py -$Version 이 보이지 않습니다. 새 PowerShell을 열어 다시 실행하거나 Python Launcher 포함 여부를 확인하세요."
    }
    return $launcher
}

function Invoke-Checked {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$FailureMessage
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

try {
    $repoRoot = Resolve-RepoRoot
    Set-Location $repoRoot

    Write-Step "저장소 루트: $repoRoot"
    $pythonLauncher = Ensure-PythonLauncher -Version $PythonVersion -SkipInstall:$SkipWingetInstall
    Write-Step "Python $PythonVersion 실행기를 확인했습니다."

    $venvPath = Join-Path $repoRoot $VenvDir
    $venvPython = Join-Path $venvPath "Scripts\python.exe"

    if (-not (Test-Path $venvPython)) {
        Write-Step "가상환경 $VenvDir 를 생성합니다."
        Invoke-Checked -FilePath $pythonLauncher -Arguments @("-$PythonVersion", "-m", "venv", $VenvDir) -FailureMessage "가상환경 생성에 실패했습니다."
    }
    else {
        Write-Step "기존 가상환경 $VenvDir 를 재사용합니다."
    }

    Write-Step "pip 을 최신으로 업그레이드합니다."
    Invoke-Checked -FilePath $venvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip") -FailureMessage "pip 업그레이드에 실패했습니다."

    Write-Step "프로젝트 의존성을 설치합니다."
    Invoke-Checked -FilePath $venvPython -Arguments @("-m", "pip", "install", "-e", ".[dev]") -FailureMessage "프로젝트 의존성 설치에 실패했습니다."

    Write-Step "pdf2md 설치를 검증합니다."
    Invoke-Checked -FilePath $venvPython -Arguments @("-m", "pdf2md", "--help") -FailureMessage "pdf2md --help 검증에 실패했습니다."

    Write-Host ""
    Write-Host "완료되었습니다."
    Write-Host "PowerShell 활성화: .\$VenvDir\Scripts\Activate.ps1"
    Write-Host "CMD 활성화: .\$VenvDir\Scripts\activate.bat"
    Write-Host "OCR 기능이 필요하면 별도로 Tesseract 를 설치하고 PATH 를 확인하세요."
    exit 0
}
catch {
    Write-Error $_.Exception.Message
    Write-Host ""
    Write-Host "수동 fallback:"
    Write-Host "1. Python 3.14 설치: https://www.python.org/downloads/windows/"
    Write-Host "2. 새 PowerShell 실행"
    Write-Host "3. py -3.14 -m venv $VenvDir"
    Write-Host "4. .\$VenvDir\Scripts\python.exe -m pip install --upgrade pip"
    Write-Host "5. .\$VenvDir\Scripts\python.exe -m pip install -e .[dev]"
    exit 1
}

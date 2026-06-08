param(
    [string]$PythonVersion = "3.14",
    [string]$VenvDir = "",
    [switch]$SkipWingetInstall,
    [switch]$RecreateVenv
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step {
    param([string]$Message)
    Write-Host "[setup] $Message"
}

function Write-ManualPythonInstallHelp {
    param(
        [string]$Version,
        [string]$TargetVenvDir,
        [switch]$IncludeWinget
    )

    if ([string]::IsNullOrWhiteSpace($TargetVenvDir) -and $Version -match '^\d+\.\d+$') {
        $TargetVenvDir = Get-DefaultVenvDir -Version $Version
    }

    Write-Host ""
    Write-Host "Python $Version 설치 안내:"
    if ($IncludeWinget) {
        Write-Host "자동 설치를 직접 시도하려면:"
        Write-Host "   winget install --exact --id Python.Python.$Version --accept-source-agreements --accept-package-agreements"
    }
    Write-Host "수동 설치가 필요하면:"
    Write-Host "1. https://www.python.org/downloads/windows/ 에서 Python $Version.x 설치 파일을 받으세요."
    Write-Host "2. 설치 화면에서 Add python.exe to PATH 와 Python Launcher 옵션을 켜세요."
    Write-Host "3. 설치 후 새 PowerShell을 열고 py -$Version --version 을 확인하세요."
    Write-Host ""
    Write-Host "수동 fallback:"
    Write-Host "1. py -$Version -m venv $TargetVenvDir"
    Write-Host "2. .\$TargetVenvDir\Scripts\python.exe -m pip install --upgrade pip"
    Write-Host "3. .\$TargetVenvDir\Scripts\python.exe -m pip install -e `".[dev]`""
    Write-Host "4. .\$TargetVenvDir\Scripts\python.exe -m pdf2md --help"
}

function Resolve-RepoRoot {
    $scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
    return (Resolve-Path (Join-Path $scriptRoot "..")).Path
}

function Get-DefaultVenvDir {
    param([string]$Version)

    return ".venv$($Version -replace '\.', '')"
}

function Get-PythonVersionText {
    param([string]$FilePath)

    if (-not (Test-Path $FilePath)) {
        return $null
    }

    $output = & $FilePath --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        return $null
    }

    return ($output | Select-Object -First 1).ToString()
}

function Test-PythonVersionMatches {
    param(
        [string]$VersionText,
        [string]$ExpectedVersion
    )

    if ([string]::IsNullOrWhiteSpace($VersionText)) {
        return $false
    }

    $pattern = '^Python\s+' + [regex]::Escape($ExpectedVersion) + '(\.|$)'
    return $VersionText -match $pattern
}

function New-PythonCommandSpec {
    param(
        [string]$Source,
        [string[]]$Prefix,
        [string]$Label
    )

    return [pscustomobject]@{
        Source = $Source
        Prefix = $Prefix
        Label = $Label
    }
}

function Get-PythonCommand {
    param([string]$Version)

    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $launcher) {
        & $launcher.Source "-$Version" --version *> $null
        if ($LASTEXITCODE -eq 0) {
            return New-PythonCommandSpec -Source $launcher.Source -Prefix @("-$Version") -Label "py -$Version"
        }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $python) {
        $versionText = Get-PythonVersionText -FilePath $python.Source
        if (Test-PythonVersionMatches -VersionText $versionText -ExpectedVersion $Version) {
            return New-PythonCommandSpec -Source $python.Source -Prefix @() -Label $python.Source
        }
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
        throw "winget 을 찾을 수 없습니다. Python $Version 를 수동 설치한 뒤 스크립트를 다시 실행하세요."
    }

    Write-Step "Python $Version 이 없어 winget 설치를 시도합니다."
    $packageId = "Python.Python.$Version"
    Write-Step "winget package id: $packageId"
    & $winget.Source install --exact --id $packageId --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "winget 으로 Python $Version 설치에 실패했습니다. 공식 설치 파일을 사용하거나 회사 표준 배포 경로로 설치하세요."
    }
}

function Ensure-PythonCommand {
    param(
        [string]$Version,
        [switch]$SkipInstall
    )

    $pythonCommand = Get-PythonCommand -Version $Version
    if ($null -ne $pythonCommand) {
        return $pythonCommand
    }

    if ($SkipInstall) {
        throw "Python $Version 실행기를 찾지 못했습니다. py -$Version 또는 Python $Version.x 를 가리키는 python 명령을 확인하세요."
    }

    Install-PythonWithWinget -Version $Version
    $pythonCommand = Get-PythonCommand -Version $Version
    if ($null -eq $pythonCommand) {
        throw "Python $Version 설치 후에도 실행기를 찾지 못했습니다. 새 PowerShell을 열어 다시 실행하거나 Python Launcher 포함 여부를 확인하세요."
    }
    return $pythonCommand
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

function Invoke-PythonCommandChecked {
    param(
        [pscustomobject]$Command,
        [string[]]$Arguments,
        [string]$FailureMessage
    )

    $allArgs = @()
    if ($null -ne $Command.Prefix) {
        $allArgs += @($Command.Prefix)
    }
    $allArgs += $Arguments
    Invoke-Checked -FilePath $Command.Source -Arguments $allArgs -FailureMessage $FailureMessage
}

try {
    if ($PythonVersion -notmatch '^\d+\.\d+$') {
        throw "PythonVersion 은 3.14 처럼 major.minor 형식이어야 합니다: $PythonVersion"
    }
    if ([string]::IsNullOrWhiteSpace($VenvDir)) {
        $VenvDir = Get-DefaultVenvDir -Version $PythonVersion
    }

    $repoRoot = Resolve-RepoRoot
    Set-Location $repoRoot

    Write-Step "저장소 루트: $repoRoot"
    $pythonCommand = Ensure-PythonCommand -Version $PythonVersion -SkipInstall:$SkipWingetInstall
    Write-Step "Python $PythonVersion 실행기를 확인했습니다: $($pythonCommand.Label)"

    $venvPath = Join-Path $repoRoot $VenvDir
    $venvPython = Join-Path $venvPath "Scripts\python.exe"

    if ((Test-Path $venvPath) -and $RecreateVenv) {
        Write-Step "기존 가상환경 $VenvDir 를 삭제하고 다시 생성합니다."
        Remove-Item -Recurse -Force $venvPath
    }

    if (Test-Path $venvPython) {
        $venvVersion = Get-PythonVersionText -FilePath $venvPython
        if (-not (Test-PythonVersionMatches -VersionText $venvVersion -ExpectedVersion $PythonVersion)) {
            throw "기존 가상환경 $VenvDir 의 Python 버전($venvVersion)이 요청한 Python $PythonVersion 과 다릅니다. 다른 -VenvDir 를 쓰거나 -RecreateVenv 로 재생성하세요."
        }
        Write-Step "기존 가상환경 $VenvDir 를 재사용합니다. ($venvVersion)"
    }
    else {
        Write-Step "가상환경 $VenvDir 를 생성합니다."
        Invoke-PythonCommandChecked -Command $pythonCommand -Arguments @("-m", "venv", $VenvDir) -FailureMessage "가상환경 생성에 실패했습니다."
    }

    $venvVersion = Get-PythonVersionText -FilePath $venvPython
    if (-not (Test-PythonVersionMatches -VersionText $venvVersion -ExpectedVersion $PythonVersion)) {
        throw "가상환경 $VenvDir 의 Python 버전($venvVersion)이 요청한 Python $PythonVersion 과 다릅니다."
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
    Write-ManualPythonInstallHelp -Version $PythonVersion -TargetVenvDir $VenvDir -IncludeWinget:(-not $SkipWingetInstall)
    exit 1
}

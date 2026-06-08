param(
    [Parameter(Mandatory = $true)]
    [string]$InputDir,
    [string]$PythonVersion = "3.14",
    [string]$VenvDir = "",
    [switch]$SkipWingetInstall,
    [switch]$RecreateVenv,
    [string]$Pages,
    [switch]$SkipExisting,
    [ValidateSet("auto", "html", "markdown")]
    [string]$TableMode = "auto",
    [ValidateSet("referenced", "embedded", "placeholder")]
    [string]$ImageMode = "referenced",
    [switch]$ForceOcr,
    [switch]$KeepPageMarkers,
    [switch]$NoPageMarkers
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step {
    param([string]$Message)
    Write-Host "[batch] $Message"
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

function Get-ResolvedInputDir {
    param([string]$PathValue)

    try {
        return (Resolve-Path $PathValue).Path
    }
    catch {
        throw "입력 폴더를 찾을 수 없습니다: $PathValue"
    }
}

try {
    if ($PythonVersion -notmatch '^\d+\.\d+$') {
        throw "PythonVersion 은 3.14 처럼 major.minor 형식이어야 합니다: $PythonVersion"
    }
    if ([string]::IsNullOrWhiteSpace($VenvDir)) {
        $VenvDir = Get-DefaultVenvDir -Version $PythonVersion
    }
    if ($KeepPageMarkers -and $NoPageMarkers) {
        throw "-KeepPageMarkers 와 -NoPageMarkers 는 동시에 사용할 수 없습니다."
    }

    $repoRoot = Resolve-RepoRoot
    Set-Location $repoRoot

    $venvPython = Join-Path $repoRoot "$VenvDir\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        Write-Step "가상환경이 없어 setup_windows_env.ps1 를 먼저 실행합니다."
        $setupScript = Join-Path $repoRoot "scripts\setup_windows_env.ps1"
        $setupArgs = @("-PythonVersion", $PythonVersion, "-VenvDir", $VenvDir)
        if ($SkipWingetInstall) {
            $setupArgs += "-SkipWingetInstall"
        }
        if ($RecreateVenv) {
            $setupArgs += "-RecreateVenv"
        }
        & $setupScript @setupArgs
        if ($LASTEXITCODE -ne 0) {
            throw "환경 준비 스크립트 실행에 실패했습니다."
        }
    }
    else {
        $venvVersion = Get-PythonVersionText -FilePath $venvPython
        if (-not (Test-PythonVersionMatches -VersionText $venvVersion -ExpectedVersion $PythonVersion)) {
            throw "가상환경 $VenvDir 의 Python 버전($venvVersion)이 요청한 Python $PythonVersion 과 다릅니다. 다른 -VenvDir 를 쓰거나 setup_windows_env.ps1 -RecreateVenv 를 실행하세요."
        }
    }

    $resolvedInputDir = Get-ResolvedInputDir -PathValue $InputDir
    if (-not (Test-Path $resolvedInputDir -PathType Container)) {
        throw "입력 경로가 폴더가 아닙니다: $resolvedInputDir"
    }

    $pdfFiles = Get-ChildItem -Path $resolvedInputDir -File | Where-Object { $_.Extension -ieq ".pdf" } | Sort-Object Name
    if ($pdfFiles.Count -eq 0) {
        throw "입력 폴더 바로 아래에 PDF 파일이 없습니다: $resolvedInputDir"
    }

    $args = @(
        "-m", "pdf2md",
        "--input-dir", $resolvedInputDir,
        "--table-mode", $TableMode,
        "--image-mode", $ImageMode
    )

    if ($SkipExisting) {
        $args += "--skip-existing"
    }
    if ($Pages) {
        $args += @("--pages", $Pages)
    }
    if ($ForceOcr) {
        $args += "--force-ocr"
    }
    if ($KeepPageMarkers) {
        $args += "--keep-page-markers"
    }
    if ($NoPageMarkers) {
        $args += "--no-page-markers"
    }

    Write-Step "입력 폴더: $resolvedInputDir"
    Write-Step "배치 결과는 $resolvedInputDir\output 아래에 생성됩니다."
    Write-Step "지정 폴더 바로 아래 PDF 파일만 처리합니다."

    & $venvPython @args
    $exitCode = $LASTEXITCODE

    Write-Host ""
    Write-Host "결과 요약:"
    Write-Host "- output 루트: $resolvedInputDir\output"
    Write-Host "- 문서별 산출물: <stem>\<stem>.md, <stem>_manifest.json, <stem>_report.json"
    Write-Host "- 배치 리포트: output\batch_report.json"
    Write-Host "- 종료 코드: $exitCode"
    Write-Host "- 참고: 종료 코드 2는 부분 성공 또는 일부 fallback 을 의미할 수 있습니다."

    exit $exitCode
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}

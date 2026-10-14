param(
    [string]$ProjectRoot = "D:\YouTubeTools\AI_Video_Editor",
    [string]$VoiceId = "en_US-lessac-medium"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = [System.IO.Path]::GetFullPath($ProjectRoot)
$RuntimeRoot = Join-Path $ProjectRoot "runtime\piper"
$VenvRoot = Join-Path $RuntimeRoot ".venv"
$VenvPython = Join-Path $VenvRoot "Scripts\python.exe"
$VoicesRoot = Join-Path $RuntimeRoot "voices"
$TestRoot = Join-Path $RuntimeRoot "test"
$TestWav = Join-Path $TestRoot "piper_test.wav"

Write-Host ""
Write-Host "============================================================"
Write-Host "AI VIDEO EDITOR - PIPER LOCAL SETUP"
Write-Host "============================================================"
Write-Host "Project : $ProjectRoot"
Write-Host "Runtime : $RuntimeRoot"
Write-Host "Voice   : $VoiceId"
Write-Host ""

New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
New-Item -ItemType Directory -Force -Path $VoicesRoot | Out-Null
New-Item -ItemType Directory -Force -Path $TestRoot | Out-Null

if (-not (Test-Path $VenvPython)) {
    Write-Host "[1/5] Creating isolated Piper virtual environment..."
    python -m venv $VenvRoot
}
else {
    Write-Host "[1/5] Piper virtual environment already exists."
}

Write-Host "[2/5] Updating pip..."
& $VenvPython -m pip install --upgrade pip

Write-Host "[3/5] Installing Piper 1.8.0..."
& $VenvPython -m pip install "piper-tts==1.8.0"

Write-Host "[4/5] Downloading voice: $VoiceId"
& $VenvPython -m piper.download_voices --data-dir $VoicesRoot $VoiceId

Write-Host "[5/5] Generating a test WAV..."
& $VenvPython -m piper `
    --data-dir $VoicesRoot `
    -m $VoiceId `
    -f $TestWav `
    -- "Hello. This is a Piper voice test for AI Video Editor."

if (-not (Test-Path $TestWav)) {
    throw "Piper setup completed but test WAV was not created."
}

Write-Host ""
Write-Host "============================================================"
Write-Host "PIPER SETUP SUCCESS"
Write-Host "============================================================"
Write-Host "Python : $VenvPython"
Write-Host "Voices : $VoicesRoot"
Write-Host "Test   : $TestWav"
Write-Host ""
Write-Host "Open the test file with:"
Write-Host "Start-Process `"$TestWav`""

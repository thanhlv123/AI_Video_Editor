$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "============================================================"
Write-Host "AI VIDEO EDITOR - VOICESTUDIO LOCAL DIAGNOSTICS M104.4.2"
Write-Host "============================================================"

Write-Host "`n[1/4] VoiceStudio Start Menu entries"
Get-StartApps |
    Where-Object { $_.Name -match "VoiceStudio|Voice Studio" } |
    Format-Table -AutoSize

Write-Host "`n[2/4] VoiceStudio processes"
Get-Process -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessName -match "VoiceStudio|Voice Studio" } |
    Select-Object ProcessName, Id, Path |
    Format-Table -AutoSize

Write-Host "`n[3/4] Scan VoiceStudio Electron loopback ports"
$ports = 0..16 | ForEach-Object { 3900 + ($_ * 1000) }
$found = @()
foreach ($port in $ports) {
    $url = "http://127.0.0.1:$port"
    try {
        $discovery = Invoke-RestMethod -Uri "$url/.well-known/voicestudio-speech" -TimeoutSec 1
        $json = $discovery | ConvertTo-Json -Depth 8 -Compress
        if ($json -match "voicestudio\.speech\.v1") {
            Write-Host "FOUND: $url" -ForegroundColor Green
            $found += $url
            continue
        }
    }
    catch {}

    try {
        $voices = Invoke-RestMethod -Uri "$url/v1/audio/voices" -TimeoutSec 1
        if ($null -ne $voices.voices -and $null -ne $voices.engines) {
            Write-Host "FOUND (compat): $url" -ForegroundColor Green
            $found += $url
        }
    }
    catch {}
}

if ($found.Count -eq 0) {
    Write-Host "No VoiceStudio backend found on 3900/4900/.../19900." -ForegroundColor Yellow
}

Write-Host "`n[4/4] Health of discovered backend(s)"
foreach ($url in $found | Select-Object -Unique) {
    Write-Host "--- $url/health"
    try {
        Invoke-RestMethod -Uri "$url/health" -TimeoutSec 5 | ConvertTo-Json -Depth 8
    }
    catch {
        Write-Host "Health failed: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

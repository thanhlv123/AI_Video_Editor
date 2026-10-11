# ============================================================
# AI VIDEO CREATOR STUDIO
# Git Baseline Safety Check
# ============================================================

$ErrorActionPreference = "Stop"

$ProjectRoot = "D:\YouTubeTools\AI_Video_Editor"

Set-Location $ProjectRoot

Write-Host ""
Write-Host "============================================================"
Write-Host " AI VIDEO CREATOR STUDIO - GIT SAFETY CHECK"
Write-Host "============================================================"
Write-Host ""

# ------------------------------------------------------------
# Get files currently staged in Git
# ------------------------------------------------------------

$stagedFiles = git diff --cached --name-only --diff-filter=ACMR

if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: Could not read staged Git files."
    exit 1
}

if (-not $stagedFiles) {
    Write-Host "FAIL: No staged files found."
    Write-Host "Run: git add ."
    exit 1
}

Write-Host "Staged files found: $($stagedFiles.Count)"
Write-Host ""

# ------------------------------------------------------------
# Text extensions that are safe to inspect
# ------------------------------------------------------------

$textExtensions = @(
    ".py",
    ".json",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".md",
    ".ps1",
    ".bat",
    ".cmd"
)

# ------------------------------------------------------------
# Secret detection patterns
#
# IMPORTANT:
# The script NEVER prints the suspected secret value.
# It prints only:
# file name
# line number
# category
# ------------------------------------------------------------

$secretPatterns = @(
    @{
        Name  = "OpenAI-style key"
        Regex = "sk-[A-Za-z0-9_-]{15,}"
    },
    @{
        Name  = "Bearer token"
        Regex = "(?i)Bearer\s+[A-Za-z0-9._-]{20,}"
    },
    @{
        Name  = "Google API key"
        Regex = "AIza[A-Za-z0-9_-]{20,}"
    },
    @{
        Name  = "GitHub token"
        Regex = "(ghp_|github_pat_)[A-Za-z0-9_-]{20,}"
    },
    @{
        Name  = "AWS access key"
        Regex = "AKIA[A-Z0-9]{16}"
    },
    @{
        Name  = "Possible hard-coded API key/token/secret"
        Regex = "(?i)(api[_-]?key|token|secret).{0,20}[=:].{0,5}[A-Za-z0-9._-]{20,}"
    }
)

$possibleSecrets = @()

Write-Host "------------------------------------------------------------"
Write-Host "1. SCANNING STAGED SOURCE FILES FOR POSSIBLE SECRETS"
Write-Host "------------------------------------------------------------"
Write-Host ""

foreach ($relativeFile in $stagedFiles) {

    $fullPath = Join-Path $ProjectRoot $relativeFile

    if (-not (Test-Path -LiteralPath $fullPath)) {
        continue
    }

    $extension = [System.IO.Path]::GetExtension($fullPath).ToLowerInvariant()

    if ($textExtensions -notcontains $extension) {
        continue
    }

    try {
        $lines = Get-Content -LiteralPath $fullPath -ErrorAction Stop
    }
    catch {
        Write-Host "WARNING: Could not read $relativeFile"
        continue
    }

    for ($i = 0; $i -lt $lines.Count; $i++) {

        $line = $lines[$i]

        foreach ($pattern in $secretPatterns) {

            if ($line -match $pattern.Regex) {

                $result = [PSCustomObject]@{
                    File     = $relativeFile
                    Line     = $i + 1
                    Category = $pattern.Name
                }

                $possibleSecrets += $result

                Write-Host (
                    "POSSIBLE_SECRET  {0}:{1}  [{2}]" -f `
                    $relativeFile,
                    ($i + 1),
                    $pattern.Name
                )
            }
        }
    }
}

Write-Host ""

if ($possibleSecrets.Count -eq 0) {

    Write-Host "SECRET SCAN: PASS"
    Write-Host "No obvious hard-coded secrets were detected."

}
else {

    Write-Host "SECRET SCAN: REVIEW REQUIRED"
    Write-Host ""
    Write-Host "Possible secret locations found: $($possibleSecrets.Count)"
    Write-Host ""
    Write-Host "IMPORTANT:"
    Write-Host "Do NOT paste secret values into ChatGPT."
    Write-Host "Only report the file name and line number."
}

Write-Host ""

# ------------------------------------------------------------
# Check staged files larger than 10 MB
# ------------------------------------------------------------

Write-Host "------------------------------------------------------------"
Write-Host "2. CHECKING STAGED FILE SIZE"
Write-Host "------------------------------------------------------------"
Write-Host ""

$largeFiles = @()

foreach ($relativeFile in $stagedFiles) {

    $fullPath = Join-Path $ProjectRoot $relativeFile

    if (-not (Test-Path -LiteralPath $fullPath)) {
        continue
    }

    $item = Get-Item -LiteralPath $fullPath

    if ($item.Length -gt 10MB) {

        $largeFiles += [PSCustomObject]@{
            File = $relativeFile
            MB   = [math]::Round($item.Length / 1MB, 2)
        }
    }
}

if ($largeFiles.Count -eq 0) {

    Write-Host "LARGE FILE CHECK: PASS"
    Write-Host "No staged file is larger than 10 MB."

}
else {

    Write-Host "LARGE FILE CHECK: REVIEW REQUIRED"
    Write-Host ""

    foreach ($file in $largeFiles) {
        Write-Host ("{0} MB   {1}" -f $file.MB, $file.File)
    }
}

Write-Host ""

# ------------------------------------------------------------
# Protected production file check
# ------------------------------------------------------------

Write-Host "------------------------------------------------------------"
Write-Host "3. IMPORTANT PRODUCTION FILES IN BASELINE"
Write-Host "------------------------------------------------------------"
Write-Host ""

$protectedFiles = @(
    "pipeline/scene_pipeline.py",
    "pipeline/full_video_pipeline.py",
    "pipeline/context_geo.py",
    "pipeline/visual_strategy.py",
    "stock/balanced_search_manager.py",
    "stock/search_manager.py",
    "stock/ranker.py",
    "stock/visual_ranker.py",
    "stock/selector.py",
    "stock/validator.py",
    "config/api_key_manager.py",
    "api_keys_dialog.py"
)

foreach ($protectedFile in $protectedFiles) {

    if ($stagedFiles -contains $protectedFile) {
        Write-Host "BASELINE OK: $protectedFile"
    }
    else {
        Write-Host "NOT STAGED:  $protectedFile"
    }
}

Write-Host ""

# ------------------------------------------------------------
# Final result
# ------------------------------------------------------------

Write-Host "============================================================"
Write-Host " FINAL RESULT"
Write-Host "============================================================"
Write-Host ""

if (($possibleSecrets.Count -eq 0) -and ($largeFiles.Count -eq 0)) {

    Write-Host "PASS"
    Write-Host ""
    Write-Host "The staged baseline passed the automatic safety checks."
    Write-Host ""
    Write-Host "Next command after review:"
    Write-Host ""
    Write-Host 'git commit -m "Baseline before AI Video Creator Studio development"'

}
else {

    Write-Host "REVIEW REQUIRED"
    Write-Host ""
    Write-Host "Do NOT commit yet."
    Write-Host "Review the warnings above first."
}

Write-Host ""
Write-Host "============================================================"
Write-Host ""
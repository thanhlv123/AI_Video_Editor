param(
    [ValidateSet("compile", "import", "full")]
    [string]$Mode = "full",
    [int]$Verbosity = 1
)

$ErrorActionPreference = "Stop"
$Repo = "D:\\YouTubeTools\\AI_Video_Editor"

if (-not (Test-Path $Repo)) { throw "Repository not found: $Repo" }

$Candidates = @(
    (Join-Path $Repo ".venv\\Scripts\\python.exe"),
    (Join-Path $Repo "venv\\Scripts\\python.exe"),
    "C:\\Users\\pc\\AppData\\Local\\Programs\\Python\\Python312\\python.exe"
)
$Python = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Python) {
    $Command = Get-Command python -ErrorAction SilentlyContinue
    if ($Command) { $Python = $Command.Source }
}
if (-not $Python) { throw "Python 3.12 was not found." }

$ReportDir = Join-Path $Repo ".automation"
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
$Report = Join-Path $ReportDir ("m116_release_gate_" + $Mode + ".json")

Push-Location $Repo
try {
    & $Python "scripts\\m116_release_gate.py" $Mode "--verbosity" $Verbosity "--report" $Report
    exit $LASTEXITCODE
}
finally { Pop-Location }

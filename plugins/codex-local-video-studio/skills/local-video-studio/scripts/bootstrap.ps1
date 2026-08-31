param(
    [string]$RuntimeDir = "",
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$arguments = @((Join-Path $PSScriptRoot "bootstrap.py"))
if (-not [string]::IsNullOrWhiteSpace($RuntimeDir)) {
    $arguments += @("--runtime-dir", $RuntimeDir)
}
& $Python @arguments
if ($LASTEXITCODE -ne 0) { throw "Cross-platform bootstrap failed" }

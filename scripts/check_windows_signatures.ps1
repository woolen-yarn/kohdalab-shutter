[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Directory,
    [string]$ReportPath,
    [switch]$RequireSigned,
    [string]$ExpectedSubject
)
$ErrorActionPreference = 'Stop'
if ($RequireSigned -and [string]::IsNullOrWhiteSpace($ExpectedSubject)) {
    throw 'RequireSigned also requires the exact approved ExpectedSubject.'
}
$files = @('kohdalab-shutter-gui.exe', 'kohdalab-shutter.exe')
$results = @()
foreach ($name in $files) {
    $path = Join-Path $Directory $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing first-party binary: $name" }
    $signature = Get-AuthenticodeSignature -LiteralPath $path
    $subject = if ($signature.SignerCertificate) { $signature.SignerCertificate.Subject } else { $null }
    $thumbprint = if ($signature.SignerCertificate) { $signature.SignerCertificate.Thumbprint } else { $null }
    $timestamped = $null -ne $signature.TimeStamperCertificate
    $publisherMatches = -not [string]::IsNullOrWhiteSpace($ExpectedSubject) -and $subject -ceq $ExpectedSubject
    $valid = $signature.Status -eq 'Valid' -and $timestamped -and $publisherMatches
    $results += [pscustomobject]@{
        file = $name; status = [string]$signature.Status; subject = $subject
        thumbprint = $thumbprint; timestamped = $timestamped
        expectedPublisherMatched = $publisherMatches; validForPublication = $valid
        sha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
$report = [ordered]@{
    allSignedAndPublisherVerified = @($results | Where-Object { -not $_.validForPublication }).Count -eq 0
    requireSigned = [bool]$RequireSigned
    files = $results
}
if ($ReportPath) {
    $parent = Split-Path -Parent $ReportPath
    if ($parent) { New-Item -ItemType Directory -Force $parent | Out-Null }
    $report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ReportPath -Encoding utf8
}
if ($RequireSigned -and -not $report.allSignedAndPublisherVerified) {
    throw 'Release requires valid timestamped Authenticode signatures from the approved publisher on both executables.'
}
Write-Host "Recorded Authenticode status for $($results.Count) first-party files."

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Directory,

    [Parameter(Mandatory = $true)]
    [string]$Version,

    [string]$ReportPath
)

$ErrorActionPreference = 'Stop'

$expectedFiles = @(
    @{ Name = 'kohdalab-shutter.exe'; Description = 'KohdaLab Shutter CLI'; InternalName = 'kohdalab-shutter' },
    @{ Name = 'kohdalab-shutter-gui.exe'; Description = 'KohdaLab Shutter'; InternalName = 'kohdalab-shutter-gui' }
)

$results = @()
$errors = @()

foreach ($expected in $expectedFiles) {
    $path = Join-Path -Path $Directory -ChildPath $expected.Name
    $result = [ordered]@{
        path = $path
        exists = Test-Path -LiteralPath $path -PathType Leaf
        expected = [ordered]@{
            CompanyName = 'Kohdalab'
            FileDescription = $expected.Description
            FileVersion = $Version
            InternalName = $expected.InternalName
            OriginalFilename = $expected.Name
            ProductName = 'KohdaLab Shutter'
            ProductVersion = $Version
        }
        actual = $null
        valid = $false
        mismatches = @()
    }

    if (-not $result.exists) {
        $result.mismatches = @('file is missing')
        $errors += "$($expected.Name): file is missing"
        $results += [pscustomobject]$result
        continue
    }

    $info = (Get-Item -LiteralPath $path).VersionInfo
    $actual = [ordered]@{
        CompanyName = $info.CompanyName
        FileDescription = $info.FileDescription
        FileVersion = $info.FileVersion
        InternalName = $info.InternalName
        OriginalFilename = $info.OriginalFilename
        ProductName = $info.ProductName
        ProductVersion = $info.ProductVersion
    }
    $mismatches = @()
    foreach ($property in $result.expected.Keys) {
        if ($actual[$property] -ne $result.expected[$property]) {
            $mismatches += "$property expected '$($result.expected[$property])' but found '$($actual[$property])'"
        }
    }
    $result.actual = $actual
    $result.mismatches = $mismatches
    $result.valid = $mismatches.Count -eq 0
    if (-not $result.valid) {
        $errors += "$($expected.Name): $($mismatches -join '; ')"
    }
    $results += [pscustomobject]$result
}

$report = [ordered]@{
    directory = (Resolve-Path -LiteralPath $Directory -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Path)
    version = $Version
    valid = $errors.Count -eq 0
    files = $results
}

if ($ReportPath) {
    $reportDirectory = Split-Path -Parent $ReportPath
    if ($reportDirectory) {
        New-Item -ItemType Directory -Force -Path $reportDirectory | Out-Null
    }
    $report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ReportPath -Encoding utf8
}

if ($errors.Count -gt 0) {
    throw "Windows metadata validation failed:`n$($errors -join "`n")"
}

Write-Host "Windows metadata validation passed for $($expectedFiles.Count) executable(s)."

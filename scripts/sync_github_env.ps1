param(
    [string]$Repo = "Samaresh-16/NotifyAgent",
    [string]$EnvPath = ".env"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "GitHub CLI is not installed. Install it, then run: gh auth login"
}

if (-not (Test-Path -LiteralPath $EnvPath)) {
    Write-Error "Could not find $EnvPath"
}

$secretNames = @(
    "NVIDIA_API_KEY",
    "EMAIL_ADDRESS",
    "EMAIL_PASSWORD",
    "EMAIL_TO"
)

$envValues = @{}

Get-Content -LiteralPath $EnvPath | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
        return
    }

    $parts = $line.Split("=", 2)
    $key = $parts[0].Trim()
    $value = $parts[1].Trim()

    if (
        $value.Length -ge 2 -and
        (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))
    ) {
        $value = $value.Substring(1, $value.Length - 2)
    }

    $envValues[$key] = $value
}

foreach ($key in $envValues.Keys) {
    $value = $envValues[$key]
    if ([string]::IsNullOrWhiteSpace($value)) {
        Write-Host "Skipping empty value: $key"
        continue
    }

    if ($secretNames -contains $key) {
        $value | gh secret set $key --repo $Repo --body-file -
        Write-Host "Uploaded secret: $key"
    }
    else {
        gh variable set $key --repo $Repo --body "$value"
        Write-Host "Uploaded variable: $key"
    }
}

Write-Host "Done syncing .env to GitHub Actions for $Repo"

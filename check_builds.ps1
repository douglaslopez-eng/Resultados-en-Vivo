$cfg = Get-Content 'dist\config.json' -Raw | ConvertFrom-Json
$headers = @{
    "Authorization" = "Bearer " + $cfg.github_token
    "Accept" = "application/vnd.github+json"
}
$builds = Invoke-RestMethod -Uri "https://api.github.com/repos/douglaslopez-eng/Resultados-en-Vivo/pages/builds" -Headers $headers
$builds | ConvertTo-Json -Depth 3

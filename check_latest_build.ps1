$cfg = Get-Content 'dist\config.json' -Raw | ConvertFrom-Json
$headers = @{
    "Authorization" = "Bearer " + $cfg.github_token
    "Accept" = "application/vnd.github+json"
}
$latest = Invoke-RestMethod -Uri "https://api.github.com/repos/douglaslopez-eng/Resultados-en-Vivo/pages/builds/latest" -Headers $headers
$latest | ConvertTo-Json -Depth 4

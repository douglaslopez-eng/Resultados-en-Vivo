$json = Get-Content 'dist\config.json' -Raw | ConvertFrom-Json
$token = $json.github_token
$headers = @{
    "Authorization" = "Bearer $token"
    "Accept" = "application/vnd.github+json"
}
$commits = Invoke-RestMethod -Uri "https://api.github.com/repos/douglaslopez-eng/Resultados-en-Vivo/commits?per_page=5" -Headers $headers
foreach ($c in $commits) {
    Write-Output ($c.sha.Substring(0,7) + " " + $c.commit.message)
}

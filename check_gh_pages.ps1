$json = Get-Content 'dist\config.json' -Raw | ConvertFrom-Json
$token = $json.github_token
$headers = @{
    "Authorization" = "Bearer $token"
    "Accept" = "application/vnd.github+json"
}
$res = Invoke-RestMethod -Uri "https://api.github.com/repos/douglaslopez-eng/Resultados-en-Vivo/pages" -Headers $headers
$res | ConvertTo-Json
